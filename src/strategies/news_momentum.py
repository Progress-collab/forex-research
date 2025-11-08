from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, compute_position_size


@dataclass(slots=True)
class NewsMomentumStrategy(Strategy):
    """
    Реакция на фундаментальные события.

    DataFrame ожидает столбцы:
    - news_score: агрегированная сила события (-1..1)
    - news_time: timestamp последней новости (UTC)
    """

    strategy_id: str = "news_momentum"
    impact_threshold: float = 0.6
    decay_minutes: int = 90
    atr_multiplier: float = 1.4
    min_atr: float = 0.0003
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.008, max_notional=200_000.0, min_notional=30_000.0)
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        if df.empty or "news_score" not in df.columns or "news_time" not in df.columns:
            return []

        last_row = df.iloc[-1]
        news_score = float(last_row["news_score"])
        if abs(news_score) < self.impact_threshold:
            return []

        news_time = pd.to_datetime(last_row["news_time"], utc=True)
        now = df.index[-1]
        if (now - news_time) > timedelta(minutes=self.decay_minutes):
            return []

        features = compute_features(
            df.tail(120),
            FeatureConfig(
                name="news_momentum",
                window_short=10,
                window_long=30,
                additional_params={"atr_period": 14},
            ),
        )
        atr = features.get("atr", default=0.0)
        if atr < self.min_atr:
            return []

        instrument = last_row["instrument"]
        notional = compute_position_size(instrument, self.atr_multiplier * atr, self.risk)
        direction = "LONG" if news_score > 0 else "SHORT"
        entry_price = float(last_row["close"])
        stop = entry_price - self.atr_multiplier * atr if direction == "LONG" else entry_price + self.atr_multiplier * atr
        take = entry_price + self.atr_multiplier * atr * 2 if direction == "LONG" else entry_price - self.atr_multiplier * atr * 2

        return [
            Signal(
                strategy_id=self.strategy_id,
                instrument=instrument,
                direction=direction,
                entry_price=entry_price,
                stop_loss=float(stop),
                take_profit=float(take),
                notional=notional,
                confidence=min(1.0, abs(news_score)),
            )
        ]

