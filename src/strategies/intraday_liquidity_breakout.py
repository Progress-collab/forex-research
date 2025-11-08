from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class IntradayLiquidityBreakoutStrategy(Strategy):
    """
    Intraday breakout, усиливающий сигналы объёмом и сессионной ликвидностью.
    """

    strategy_id: str = "intraday_liquidity_breakout"
    lookback_bars: int = 16  # при M15 ≈ 4 часа
    volume_multiplier: float = 1.4
    atr_multiplier: float = 1.6
    adx_threshold: float = 18.0
    min_atr: float = 0.00025
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.007, max_notional=180_000.0, min_notional=25_000.0)
    )
    session_windows: Dict[str, tuple[time, time]] = field(
        default_factory=lambda: {
            "EURUSD": (time(6, 0), time(20, 0)),
            "GBPUSD": (time(7, 0), time(20, 0)),
            "XAUUSD": (time(10, 0), time(21, 0)),
        }
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        if df.empty or len(df) < self.lookback_bars + 10:
            return []

        recent = df.tail(self.lookback_bars)
        last_row = df.iloc[-1]
        instrument = last_row["instrument"]
        ts_time = df.index[-1].time()

        if not self._within_session(instrument, ts_time):
            return []

        rolling_volume = recent["volume"].mean()
        if rolling_volume == 0:
            return []
        volume_ratio = last_row["volume"] / rolling_volume
        if volume_ratio < self.volume_multiplier:
            return []

        features = compute_features(
            df.tail(max(self.lookback_bars * 2, 60)),
            FeatureConfig(
                name="intraday_breakout",
                window_short=5,
                window_long=20,
                additional_params={"atr_period": 14, "adx_period": 14},
            ),
        )
        atr = features.get("atr", default=0.0)
        adx = features.get("adx", default=0.0)
        if atr < self.min_atr or adx < self.adx_threshold:
            return []

        high_break = recent["high"].max()
        low_break = recent["low"].min()
        signals: List[Signal] = []
        notional = compute_position_size(instrument, self.atr_multiplier * atr, self.risk)
        confidence = adjust_confidence(adx, self.adx_threshold) * min(volume_ratio / self.volume_multiplier, 2.0)

        if last_row["close"] > high_break:
            stop = last_row["close"] - self.atr_multiplier * atr
            take = last_row["close"] + self.atr_multiplier * atr * 1.6
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="LONG",
                    entry_price=float(last_row["close"]),
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=min(confidence, 1.0),
                )
            )
        elif last_row["close"] < low_break:
            stop = last_row["close"] + self.atr_multiplier * atr
            take = last_row["close"] - self.atr_multiplier * atr * 1.6
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=float(last_row["close"]),
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=min(confidence, 1.0),
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

