from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


PIP_CONFIG: Dict[str, Dict[str, float]] = {
    "EURUSD": {"pip_size": 0.0001, "pip_value": 10.0},
    "GBPUSD": {"pip_size": 0.0001, "pip_value": 10.0},
    "USDJPY": {"pip_size": 0.01, "pip_value": 9.1},
    "XAUUSD": {"pip_size": 0.1, "pip_value": 10.0},
}


@dataclass(slots=True)
class RiskSettings:
    equity: float = 100_000.0
    risk_per_trade_pct: float = 0.006  # 0.6%
    max_notional: float = 150_000.0
    min_notional: float = 25_000.0

    def risk_amount(self) -> float:
        return self.equity * self.risk_per_trade_pct


def compute_position_size(instrument: str, stop_distance: float, settings: RiskSettings) -> float:
    info = PIP_CONFIG.get(instrument.upper())
    if info is None:
        return settings.min_notional

    pip_size = info["pip_size"]
    pip_value = info["pip_value"]
    if stop_distance <= 0:
        return settings.min_notional

    stop_pips = stop_distance / pip_size
    if stop_pips <= 0:
        return settings.min_notional

    notional = settings.risk_amount() / (stop_pips * pip_value)
    notional = max(settings.min_notional, min(settings.max_notional, notional))
    return float(notional)


def adjust_confidence(adx: float, threshold: float = 18.0) -> float:
    if adx <= 0:
        return 0.3
    score = min(1.0, max(0.0, (adx - threshold) / (threshold * 1.5)))
    return 0.4 + 0.6 * score

