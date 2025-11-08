from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

import pandas as pd


@dataclass(slots=True)
class Signal:
    strategy_id: str
    instrument: str
    direction: str  # "LONG" или "SHORT"
    entry_price: float
    stop_loss: float
    take_profit: float
    notional: float
    confidence: float


class Strategy(Protocol):
    strategy_id: str

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        ...

