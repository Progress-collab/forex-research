from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class CarryMomentumStrategy(Strategy):
    strategy_id: str = "carry_momentum"
    atr_multiplier: float = 1.5
    min_adx: float = 18.0
    min_atr: float = 0.0004
    swap_bias_threshold: float = 0.0
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.008, max_notional=180_000.0, min_notional=20_000.0)
    )
    session_windows: Dict[str, tuple[time, time]] = field(
        default_factory=lambda: {
            "USDJPY": (time(0, 0), time(12, 0)),
            "AUDJPY": (time(0, 0), time(10, 0)),
        }
    )

    def generate_signals(self, df: pd.DataFrame, swap_bias: float = 0.0) -> List[Signal]:
        """
        swap_bias > 0 означает предпочтение длинных позиций (положительный своп),
        swap_bias < 0 — коротких.
        """

        if df.empty or len(df) < 100:
            return []

        config = FeatureConfig(
            name="carry",
            window_short=20,
            window_long=50,
            additional_params={"adx_period": 14, "atr_period": 14},
        )
        features = compute_features(df.tail(150), config)

        ema_short = features.get("ema_short")
        ema_long = features.get("ema_long")
        adx = features.get("adx", default=0.0)
        atr = features.get("atr", default=0.0)
        price = float(df["close"].iloc[-1])
        instrument = df.iloc[-1]["instrument"]
        ts_time = df.index[-1].time()

        signals: List[Signal] = []
        if adx < self.min_adx or atr < self.min_atr:
            return signals
        if not self._within_session(instrument, ts_time):
            return signals

        notional = compute_position_size(instrument, self.atr_multiplier * atr, self.risk)
        confidence = adjust_confidence(adx, self.min_adx)

        if ema_short > ema_long and swap_bias >= self.swap_bias_threshold:
            stop = price - self.atr_multiplier * atr
            take = price + self.atr_multiplier * atr * 2
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="LONG",
                    entry_price=price,
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=confidence,
                )
            )
        elif ema_short < ema_long and swap_bias <= -self.swap_bias_threshold:
            stop = price + self.atr_multiplier * atr
            take = price - self.atr_multiplier * atr * 2
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=price,
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

