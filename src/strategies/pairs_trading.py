from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from .base import Signal, Strategy
from .utils import RiskSettings


@dataclass(slots=True)
class PairsTradingStrategy(Strategy):
    """
    Стратегия статистического арбитража на паре инструментов.

    DataFrame ожидает столбцы:
    - price_a, price_b (цены синхронизированных инструментов)
    - instrument_a, instrument_b (строки с тикерами)
    - optional hedge_ratio (иначе используется self.hedge_ratio)
    """

    strategy_id: str = "pairs_trading"
    hedge_ratio: float = 1.0
    entry_z: float = 2.0
    exit_z: float = 0.5
    lookback: int = 200
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.005, max_notional=120_000.0, min_notional=10_000.0)
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        required = {"price_a", "price_b", "instrument_a", "instrument_b"}
        if not required.issubset(df.columns):
            return []
        if len(df) < self.lookback:
            return []

        frame = df.tail(self.lookback).copy()
        hedge_ratio = frame["hedge_ratio"].iloc[-1] if "hedge_ratio" in frame.columns else self.hedge_ratio
        spread = frame["price_a"] - hedge_ratio * frame["price_b"]
        mean = spread.mean()
        std = spread.std()
        if std == 0 or np.isnan(std):
            return []

        zscore = (spread.iloc[-1] - mean) / std
        instrument_pair = f"{frame['instrument_a'].iloc[-1]}/{frame['instrument_b'].iloc[-1]}"
        price = float(frame["price_a"].iloc[-1])

        signals: List[Signal] = []
        if zscore > self.entry_z:
            # Short spread: short A, long B (direction SHORT)
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument_pair,
                    direction="SHORT",
                    entry_price=price,
                    stop_loss=price * 1.02,
                    take_profit=price * (1 - self.exit_z / self.entry_z * 0.01),
                    notional=self.risk.min_notional,
                    confidence=min(abs(zscore) / self.entry_z, 2.0),
                )
            )
        elif zscore < -self.entry_z:
            # Long spread: long A, short B (direction LONG)
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument_pair,
                    direction="LONG",
                    entry_price=price,
                    stop_loss=price * 0.98,
                    take_profit=price * (1 + self.exit_z / self.entry_z * 0.01),
                    notional=self.risk.min_notional,
                    confidence=min(abs(zscore) / self.entry_z, 2.0),
                )
            )

        return signals

