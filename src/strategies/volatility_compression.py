from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class VolatilityCompressionBreakoutStrategy(Strategy):
    """
    Breakout после волатильностного сжатия (bollinger squeeze).
    """

    strategy_id: str = "volatility_compression"
    squeeze_window: int = 20
    breakout_confirm_window: int = 5
    squeeze_threshold: float = 0.6  # отношение ширины полос к среднему
    atr_multiplier: float = 1.7
    min_atr: float = 0.0002
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.007, max_notional=160_000.0, min_notional=15_000.0)
    )
    session_windows: Dict[str, tuple[time, time]] = field(
        default_factory=lambda: {
            "XAUUSD": (time(11, 0), time(21, 0)),
            "EURUSD": (time(7, 0), time(20, 0)),
        }
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        if df.empty or len(df) < self.squeeze_window + self.breakout_confirm_window:
            return []

        instrument = df.iloc[-1]["instrument"]
        ts_time = df.index[-1].time()
        if not self._within_session(instrument, ts_time):
            return []

        closes = df["close"]
        rolling_mean = closes.rolling(self.squeeze_window).mean()
        rolling_std = closes.rolling(self.squeeze_window).std()
        if rolling_std.isna().iloc[-1]:
            return []

        band_width = (rolling_std * 2) / rolling_mean
        mean_band_width = band_width.rolling(self.squeeze_window).mean()
        if mean_band_width.isna().iloc[-1]:
            return []

        squeeze = band_width.iloc[-1] / mean_band_width.iloc[-1]
        if squeeze > self.squeeze_threshold:
            return []

        confirm = closes.tail(self.breakout_confirm_window)
        high_break = confirm.max()
        low_break = confirm.min()
        last_price = closes.iloc[-1]

        features = compute_features(
            df.tail(max(self.squeeze_window * 2, 60)),
            FeatureConfig(
                name="volatility_compression",
                window_short=10,
                window_long=30,
                additional_params={"atr_period": 14, "adx_period": 14},
            ),
        )
        atr = features.get("atr", default=0.0)
        adx = features.get("adx", default=0.0)
        if atr < self.min_atr:
            return []

        notional = compute_position_size(instrument, self.atr_multiplier * atr, self.risk)
        confidence = adjust_confidence(adx, 14.0)
        signals: List[Signal] = []

        if last_price > high_break:
            stop = last_price - self.atr_multiplier * atr
            take = last_price + self.atr_multiplier * atr * 1.8
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="LONG",
                    entry_price=float(last_price),
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=confidence,
                )
            )
        elif last_price < low_break:
            stop = last_price + self.atr_multiplier * atr
            take = last_price - self.atr_multiplier * atr * 1.8
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=float(last_price),
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=confidence,
                )
            )

        return signals

    def _within_session(self, instrument: str, ts_time: time) -> bool:
        window = self.session_windows.get(instrument.upper())
        if window is None:
            return True
        start, end = window
        if start <= end:
            return start <= ts_time <= end
        return ts_time >= start or ts_time <= end

