from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class MeanReversionStrategy(Strategy):
    strategy_id: str = "mean_reversion"
    rsi_buy: float = 15.0
    rsi_sell: float = 85.0
    atr_multiplier: float = 1.2
    min_atr: float = 0.00025
    min_deviation_atr: float = 0.5
    max_deviation_atr: float = 2.5
    adx_ceiling: float = 22.0
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.006, max_notional=150_000.0, min_notional=15_000.0)
    )
    session_windows: Dict[str, tuple[time, time]] = field(
        default_factory=lambda: {
            "EURUSD": (time(7, 0), time(22, 0)),
            "USDJPY": (time(1, 0), time(12, 0)),
        }
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        if df.empty or len(df) < 50:
            return []

        features = compute_features(
            df.tail(120),
            FeatureConfig(
                name="mean_reversion",
                window_short=20,
                window_long=50,
                additional_params={"rsi_period": 2, "atr_period": 14, "adx_period": 14},
            ),
        )
        rsi = features.get("rsi", default=50)
        atr = features.get("atr", default=0.0)
        ema_long = features.get("ema_long", default=df["close"].iloc[-1])
        ema_short = features.get("ema_short", default=df["close"].iloc[-1])
        sma_long = features.get("sma_long", default=ema_long)
        adx = features.get("adx", default=0.0)
        price = float(df["close"].iloc[-1])
        instrument = df.iloc[-1]["instrument"]
        ts_time = df.index[-1].time()

        if atr < self.min_atr or adx > self.adx_ceiling:
            return []
        if not self._within_session(instrument, ts_time):
            return []

        deviation = abs(price - ema_long) / max(atr, 1e-6)
        if deviation < self.min_deviation_atr or deviation > self.max_deviation_atr:
            return []

        trend_up = ema_short >= ema_long and ema_long >= sma_long
        trend_down = ema_short <= ema_long and ema_long <= sma_long

        signals: List[Signal] = []
        if rsi < self.rsi_buy and trend_up and atr > 0:
            stop = price - self.atr_multiplier * atr
            take = ema_long
            notional = compute_position_size(instrument, self.atr_multiplier * atr, self.risk)
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="LONG",
                    entry_price=price,
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=adjust_confidence(max(5.0, self.adx_ceiling - adx), threshold=5.0),
                )
            )
        elif rsi > self.rsi_sell and trend_down and atr > 0:
            stop = price + self.atr_multiplier * atr
            take = ema_long
            notional = compute_position_size(instrument, self.atr_multiplier * atr, self.risk)
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=price,
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=adjust_confidence(max(5.0, self.adx_ceiling - adx), threshold=5.0),
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

