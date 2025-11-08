from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

import numpy as np
import pandas as pd


@dataclass(slots=True)
class StressScenario:
    name: str
    shocks_bps: Dict[str, float]
    correlation_shift: float = 0.0


def parametric_shock(
    returns: pd.DataFrame,
    scenario: StressScenario,
) -> pd.Series:
    shocked = returns.copy()
    for column, bps in scenario.shocks_bps.items():
        if column in shocked:
            shocked[column] = shocked[column] + bps / 10000.0
    if scenario.correlation_shift:
        corr = shocked.corr()
        adjusted = corr + scenario.correlation_shift
        np.fill_diagonal(adjusted.values, 1.0)
        shocked = shocked @ np.linalg.cholesky(adjusted)
    return shocked.sum(axis=1)


def historical_stress_test(
    returns: pd.DataFrame,
    periods: Iterable[slice],
) -> pd.Series:
    losses = {}
    for period in periods:
        window = returns.loc[period]
        loss = window.sum(axis=1).quantile(0.05)
        losses[str(period)] = loss
    return pd.Series(losses)

