from __future__ import annotations

import numpy as np
import pandas as pd


def risk_parity_weights(cov: pd.DataFrame) -> pd.Series:
    """
    Вычисление весов risk parity по ковариационной матрице доходностей.
    """

    if cov.empty:
        raise ValueError("Пустая ковариационная матрица")

    n = cov.shape[0]
    weights = np.ones(n) / n

    def portfolio_risk(w):
        return np.sqrt(w.T @ cov.values @ w)

    def marginal_risk_contribution(w):
        return (cov.values @ w) / portfolio_risk(w)

    def objective(w):
        mrc = marginal_risk_contribution(w)
        trc = w * mrc
        return ((trc - trc.mean()) ** 2).sum()

    step = 0.01
    for _ in range(5000):
        grad = np.zeros_like(weights)
        for i in range(n):
            perturb = weights.copy()
            perturb[i] += step
            grad[i] = (objective(perturb) - objective(weights)) / step
        weights -= 0.1 * grad
        weights = np.clip(weights, 1e-6, 1.0)
        weights /= weights.sum()

        if objective(weights) < 1e-6:
            break

    return pd.Series(weights, index=cov.index)

