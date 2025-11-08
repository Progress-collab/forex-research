from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner
from src.backtesting.optimization import HyperparameterOptimizer, OptimizationResult
from src.strategies import CarryMomentumStrategy, MeanReversionStrategy, MomentumBreakoutStrategy


def optimize_momentum_breakout(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров Momentum Breakout стратегии."""

    def strategy_factory(params: Dict) -> MomentumBreakoutStrategy:
        return MomentumBreakoutStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            adx_threshold=params.get("adx_threshold", 20.0),
            lookback_hours=params.get("lookback_hours", 24),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
        )

    param_grid = {
        "atr_multiplier": [1.8, 2.0, 2.2, 2.5],
        "adx_threshold": [18, 20, 22, 25],
        "lookback_hours": [20, 24, 30, 36],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",  # Главная цель: Profit Factor > 1
    )


def optimize_mean_reversion(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров Mean Reversion стратегии."""

    def strategy_factory(params: Dict) -> MeanReversionStrategy:
        return MeanReversionStrategy(
            rsi_buy=params.get("rsi_buy", 15.0),
            rsi_sell=params.get("rsi_sell", 85.0),
            atr_multiplier=params.get("atr_multiplier", 1.2),
        )

    param_grid = {
        "rsi_buy": [20.0, 25.0, 30.0],
        "rsi_sell": [70.0, 75.0, 80.0],
        "atr_multiplier": [1.0, 1.2, 1.5],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="sharpe_ratio",
    )


def optimize_carry_momentum(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров Carry Momentum стратегии."""

    def strategy_factory(params: Dict) -> CarryMomentumStrategy:
        return CarryMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            min_adx=params.get("min_adx", 20.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
        )

    param_grid = {
        "atr_multiplier": [1.5, 1.8, 2.0, 2.2, 2.5],
        "min_adx": [18, 20, 22, 25],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",  # Главная цель: Profit Factor > 1
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Оптимизация параметров стратегий.")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["mean_reversion", "carry_momentum", "momentum_breakout"],
        help="Стратегия для оптимизации.",
    )
    parser.add_argument(
        "--instrument",
        default="EURUSD",
        help="Инструмент для оптимизации.",
    )
    parser.add_argument(
        "--period",
        default="m15",
        help="Период данных.",
    )
    parser.add_argument(
        "--output-dir",
        default="research/configs/optimized",
        help="Каталог для сохранения результатов.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    runner = FullBacktestRunner()

    if args.strategy == "mean_reversion":
        result = optimize_mean_reversion(runner, args.instrument, args.period)
    elif args.strategy == "carry_momentum":
        result = optimize_carry_momentum(runner, args.instrument, args.period)
    elif args.strategy == "momentum_breakout":
        result = optimize_momentum_breakout(runner, args.instrument, args.period)
    else:
        raise ValueError(f"Неизвестная стратегия: {args.strategy}")

    # Сохраняем результаты
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.strategy}_{args.instrument}_{args.period}.json"
    optimizer = HyperparameterOptimizer(runner)
    optimizer.save_best_params(result, output_path)

    logging.info("Оптимизация завершена. Лучшие параметры:")
    logging.info("  %s", json.dumps(result.best_params, indent=2))
    logging.info("  Score (%s): %.4f", result.optimization_metric, result.best_score)


if __name__ == "__main__":
    main()

