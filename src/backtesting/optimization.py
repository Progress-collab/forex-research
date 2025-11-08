from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
from typing import Callable, Dict, List, Optional

import json
from pathlib import Path

from src.backtesting.full_backtest import FullBacktestResult, FullBacktestRunner
from src.strategies import Strategy

log = logging.getLogger(__name__)


@dataclass(slots=True)
class OptimizationResult:
    """Результат оптимизации параметров."""

    best_params: Dict
    best_score: float
    all_results: List[tuple[Dict, float]]
    optimization_metric: str


class HyperparameterOptimizer:
    """Оптимизация гиперпараметров стратегий через grid search."""

    def __init__(self, runner: FullBacktestRunner):
        self.runner = runner

    def optimize(
        self,
        strategy_factory: Callable[[Dict], Strategy],
        param_grid: Dict[str, List],
        instrument: str,
        period: str = "m15",
        optimization_metric: str = "sharpe_ratio",  # sharpe_ratio, recovery_factor, net_pnl
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> OptimizationResult:
        """
        Выполняет grid search оптимизацию параметров.
        
        Args:
            strategy_factory: Функция, принимающая словарь параметров и возвращающая Strategy
            param_grid: Словарь с параметрами и их возможными значениями
            instrument: Инструмент для тестирования
            period: Период данных
            optimization_metric: Метрика для оптимизации (sharpe_ratio, recovery_factor, net_pnl)
            start_date: Начальная дата
            end_date: Конечная дата
        """
        # Генерируем все комбинации параметров
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))

        log.info("Начинаем оптимизацию: %s комбинаций параметров", len(param_combinations))

        all_results: List[tuple[Dict, float]] = []
        best_score = float("-inf")
        best_params = None

        for i, param_combo in enumerate(param_combinations):
            params = dict(zip(param_names, param_combo))
            log.info("[%s/%s] Тестируем параметры: %s", i + 1, len(param_combinations), params)

            try:
                strategy = strategy_factory(params)
                result = self.runner.run(strategy, instrument, period, start_date, end_date)

                # Извлекаем метрику
                if optimization_metric == "sharpe_ratio":
                    score = result.sharpe_ratio
                elif optimization_metric == "recovery_factor":
                    score = result.recovery_factor if result.recovery_factor != float("inf") else 1000.0
                elif optimization_metric == "net_pnl":
                    score = result.net_pnl
                else:
                    raise ValueError(f"Неизвестная метрика: {optimization_metric}")

                all_results.append((params, score))

                if score > best_score:
                    best_score = score
                    best_params = params
                    log.info("Новый лучший результат: %s = %.4f", optimization_metric, score)

            except Exception as e:  # noqa: BLE001
                log.error("Ошибка при тестировании параметров %s: %s", params, e)
                continue

        log.info("Оптимизация завершена. Лучшие параметры: %s (score=%.4f)", best_params, best_score)

        return OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            all_results=all_results,
            optimization_metric=optimization_metric,
        )

    def save_best_params(self, result: OptimizationResult, output_path: Path) -> None:
        """Сохраняет лучшие параметры в JSON файл."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "optimization_metric": result.optimization_metric,
            "best_score": result.best_score,
            "best_params": result.best_params,
            "optimized_at": datetime.now().isoformat(),
        }
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        log.info("Лучшие параметры сохранены в %s", output_path)

