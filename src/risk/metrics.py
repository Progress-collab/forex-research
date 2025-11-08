from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_volatility(returns: pd.Series, window: int = 30) -> pd.Series:
    return returns.rolling(window=window, min_periods=window).std(ddof=1)


def compute_var(returns: pd.Series, alpha: float = 0.95) -> float:
    if returns.empty:
        return float("nan")
    return float(np.quantile(returns, 1 - alpha))


def compute_cvar(returns: pd.Series, alpha: float = 0.95) -> float:
    if returns.empty:
        return float("nan")
    threshold = compute_var(returns, alpha)
    tail_losses = returns[returns <= threshold]
    if tail_losses.empty:
        return float(threshold)
    return float(tail_losses.mean())


def compute_drawdown(equity: pd.Series) -> pd.Series:
    running_max = equity.cummax()
    return equity / running_max - 1.0

