"""
Модуль риск-менеджмента: метрики, стресс-тесты и распределение капитала.
"""

from .metrics import compute_cvar, compute_drawdown, compute_var, rolling_volatility
from .stress import historical_stress_test, parametric_shock
from .capital_allocation import risk_parity_weights

__all__ = [
    "compute_cvar",
    "compute_drawdown",
    "compute_var",
    "rolling_volatility",
    "historical_stress_test",
    "parametric_shock",
    "risk_parity_weights",
]

