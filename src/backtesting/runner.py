from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from src.data_pipeline.config import DataPipelineConfig
from src.signals.data_access import CandleLoader
from src.strategies import Strategy


@dataclass(slots=True)
class BacktestResult:
    strategy_id: str
    instrument: str
    trades: int
    pnl: float
    sharpe: float
    max_drawdown: float
    recovery_factor: float


class BacktestRunner:
    def __init__(self, data_config: DataPipelineConfig):
        self.loader = CandleLoader(data_config)

    def run(
        self,
        strategies: Sequence[Strategy],
        instruments: Iterable[str],
        limit: int = 500,
    ) -> List[BacktestResult]:
        results: List[BacktestResult] = []
        data_map: Dict[str, pd.DataFrame] = {
            inst: self.loader.load_recent(inst, limit=limit) for inst in instruments
        }

        for strategy in strategies:
            for instrument, df in data_map.items():
                signals = strategy.generate_signals(df)
                if not signals:
                    continue
                pnl_series = self._simulate(df, signals)
                if pnl_series.empty:
                    continue
                result = self._build_result(strategy.strategy_id, instrument, pnl_series)
                results.append(result)
        return results

    def _simulate(self, df: pd.DataFrame, signals) -> pd.Series:
        """
        Упрощённая симуляция: оценка прибыли как разница между close и стоп/тейк.
        Это прототип для проверки сигналов, не торговая система в продакшне.
        """

        returns: List[float] = []
        for signal in signals:
            price_series = df["close"]
            future = price_series.tail(50)  # грубая оценка
            if signal.direction == "LONG":
                target = min(future.max(), signal.take_profit)
                stop = max(future.min(), signal.stop_loss)
                profit = target - signal.entry_price
                loss = signal.entry_price - stop
            else:
                target = max(future.min(), signal.take_profit)
                stop = min(future.max(), signal.stop_loss)
                profit = signal.entry_price - target
                loss = stop - signal.entry_price

            outcome = profit if profit > loss else -loss
            returns.append(outcome / signal.entry_price)

        return pd.Series(returns)

    def _build_result(self, strategy_id: str, instrument: str, returns: pd.Series) -> BacktestResult:
        pnl = float(returns.sum())
        sharpe = float(np.sqrt(252) * returns.mean() / (returns.std(ddof=1) + 1e-9))
        equity = (1 + returns).cumprod()
        peak = equity.cummax()
        drawdown = equity / peak - 1
        max_drawdown = float(drawdown.min())
        recovery_factor = pnl / abs(max_drawdown) if max_drawdown != 0 else float("inf")

        return BacktestResult(
            strategy_id=strategy_id,
            instrument=instrument,
            trades=len(returns),
            pnl=pnl,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            recovery_factor=recovery_factor,
        )

