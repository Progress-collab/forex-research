from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from src.backtesting.full_backtest import FullBacktestResult, FullBacktestRunner
from src.strategies import Strategy

log = logging.getLogger(__name__)


@dataclass(slots=True)
class WalkForwardResult:
    """Результаты walk-forward тестирования."""

    train_results: List[FullBacktestResult]
    test_results: List[FullBacktestResult]
    parameter_stability: dict
    degradation_metrics: dict


class WalkForwardTester:
    """Walk-forward тестирование стратегий."""

    def __init__(self, runner: FullBacktestRunner):
        self.runner = runner

    def run(
        self,
        strategy_factory: callable,  # Функция, создающая стратегию с параметрами
        instrument: str,
        period: str = "m15",
        train_months: int = 6,
        test_months: int = 3,
        step_months: int = 1,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> WalkForwardResult:
        """
        Выполняет walk-forward тестирование.
        
        Args:
            strategy_factory: Функция, принимающая параметры и возвращающая Strategy
            instrument: Инструмент для тестирования
            period: Период данных
            train_months: Количество месяцев для тренировки
            test_months: Количество месяцев для тестирования
            step_months: Шаг сдвига окна (в месяцах)
            start_date: Начальная дата (если None, берется из данных)
            end_date: Конечная дата (если None, берется из данных)
        """
        # Загружаем данные для определения диапазона
        data_path = self.runner.curated_dir / f"{instrument}_{period}.parquet"
        df = pd.read_parquet(data_path)
        df["utc_time"] = pd.to_datetime(df["utc_time"])
        df = df.set_index("utc_time").sort_index()

        if start_date is None:
            start_date = df.index[0]
        if end_date is None:
            end_date = df.index[-1]

        train_results: List[FullBacktestResult] = []
        test_results: List[FullBacktestResult] = []

        current_start = start_date
        fold = 0

        while current_start < end_date:
            train_end = current_start + timedelta(days=train_months * 30)
            test_start = train_end
            test_end = test_start + timedelta(days=test_months * 30)

            if test_end > end_date:
                break

            log.info(
                "Fold %s: Train [%s - %s], Test [%s - %s]",
                fold,
                current_start.date(),
                train_end.date(),
                test_start.date(),
                test_end.date(),
            )

            # Тренировка (здесь можно добавить оптимизацию параметров)
            # Пока используем стратегию с дефолтными параметрами
            strategy = strategy_factory()
            train_result = self.runner.run(strategy, instrument, period, current_start, train_end)
            train_results.append(train_result)

            # Тестирование на out-of-sample данных
            test_result = self.runner.run(strategy, instrument, period, test_start, test_end)
            test_results.append(test_result)

            # Сдвигаем окно
            current_start += timedelta(days=step_months * 30)
            fold += 1

        # Анализ стабильности параметров и деградации
        parameter_stability = self._analyze_parameter_stability(train_results, test_results)
        degradation_metrics = self._analyze_degradation(train_results, test_results)

        return WalkForwardResult(
            train_results=train_results,
            test_results=test_results,
            parameter_stability=parameter_stability,
            degradation_metrics=degradation_metrics,
        )

    def _analyze_parameter_stability(
        self, train_results: List[FullBacktestResult], test_results: List[FullBacktestResult]
    ) -> dict:
        """Анализирует стабильность параметров между train и test."""
        if not train_results or not test_results:
            return {}

        # Сравниваем метрики между train и test
        train_sharpe = [r.sharpe_ratio for r in train_results]
        test_sharpe = [r.sharpe_ratio for r in test_results]

        train_recovery = [r.recovery_factor for r in train_results]
        test_recovery = [r.recovery_factor for r in test_results]

        return {
            "sharpe_correlation": float(pd.Series(train_sharpe).corr(pd.Series(test_sharpe))) if len(train_sharpe) > 1 else 0.0,
            "recovery_correlation": float(pd.Series(train_recovery).corr(pd.Series(test_recovery))) if len(train_recovery) > 1 else 0.0,
            "avg_train_sharpe": float(np.mean(train_sharpe)) if train_sharpe else 0.0,
            "avg_test_sharpe": float(np.mean(test_sharpe)) if test_sharpe else 0.0,
        }

    def _analyze_degradation(
        self, train_results: List[FullBacktestResult], test_results: List[FullBacktestResult]
    ) -> dict:
        """Анализирует деградацию производительности на тестовых данных."""
        if not train_results or not test_results:
            return {}

        train_sharpe = np.mean([r.sharpe_ratio for r in train_results])
        test_sharpe = np.mean([r.sharpe_ratio for r in test_results])

        train_recovery = np.mean([r.recovery_factor for r in train_results])
        test_recovery = np.mean([r.recovery_factor for r in test_results])

        sharpe_degradation = (train_sharpe - test_sharpe) / train_sharpe if train_sharpe != 0 else 0.0
        recovery_degradation = (train_recovery - test_recovery) / train_recovery if train_recovery != 0 else 0.0

        return {
            "sharpe_degradation_pct": float(sharpe_degradation * 100),
            "recovery_degradation_pct": float(recovery_degradation * 100),
            "acceptable_degradation": abs(sharpe_degradation) < 0.3 and abs(recovery_degradation) < 0.3,
        }

