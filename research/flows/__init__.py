"""
Prefect-потоки для автоматического бэктеста стратегий.
"""

from .daily_backtests import build_flow, daily_backtest_flow

__all__ = ["build_flow", "daily_backtest_flow"]

