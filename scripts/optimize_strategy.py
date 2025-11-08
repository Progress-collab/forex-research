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
from src.strategies import (
    CarryMomentumStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
    CombinedMomentumStrategy,
    MACDTrendStrategy,
    BollingerReversionStrategy,
)


def optimize_momentum_breakout(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров Momentum Breakout стратегии (улучшенная версия)."""

    def strategy_factory(params: Dict) -> MomentumBreakoutStrategy:
        return MomentumBreakoutStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            adx_threshold=params.get("adx_threshold", 20.0),
            lookback_hours=params.get("lookback_hours", 24),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
            confirmation_bars=params.get("confirmation_bars", 2),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            use_support_resistance=params.get("use_support_resistance", True),
        )

    param_grid = {
        "atr_multiplier": [1.8, 2.0, 2.2, 2.5],
        "adx_threshold": [18, 20, 22, 25],
        "lookback_hours": [20, 24, 30, 36],
        "confirmation_bars": [1, 2, 3],
        "min_pos_di_advantage": [1.0, 2.0, 3.0],
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
    """Оптимизация параметров Carry Momentum стратегии (улучшенная версия)."""

    def strategy_factory(params: Dict) -> CarryMomentumStrategy:
        return CarryMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            min_adx=params.get("min_adx", 20.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            trend_confirmation_bars=params.get("trend_confirmation_bars", 3),
            max_volatility_pct=params.get("max_volatility_pct", 5.0),
        )

    param_grid = {
        "atr_multiplier": [1.5, 1.8, 2.0, 2.2, 2.5],
        "min_adx": [18, 20, 22, 25],
        "min_pos_di_advantage": [1.0, 2.0, 3.0],
        "trend_confirmation_bars": [2, 3, 4],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",  # Главная цель: Profit Factor > 1
    )


def optimize_combined_momentum(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров Combined Momentum стратегии."""

    def strategy_factory(params: Dict) -> CombinedMomentumStrategy:
        return CombinedMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            adx_threshold=params.get("adx_threshold", 20.0),
            min_adx_carry=params.get("min_adx_carry", 20.0),
            confirmation_bars=params.get("confirmation_bars", 2),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            min_confidence=params.get("min_confidence", 0.6),
        )

    param_grid = {
        "atr_multiplier": [1.8, 2.0, 2.2],
        "adx_threshold": [18, 20, 22],
        "min_adx_carry": [18, 20, 22],
        "confirmation_bars": [1, 2],
        "min_confidence": [0.5, 0.6, 0.7],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",
    )


def optimize_macd_trend(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров MACD Trend стратегии."""

    def strategy_factory(params: Dict) -> MACDTrendStrategy:
        return MACDTrendStrategy(
            macd_fast=params.get("macd_fast", 12),
            macd_slow=params.get("macd_slow", 26),
            macd_signal=params.get("macd_signal", 9),
            adx_threshold=params.get("adx_threshold", 20.0),
            atr_multiplier=params.get("atr_multiplier", 2.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
        )

    param_grid = {
        "adx_threshold": [18, 20, 22, 25],
        "atr_multiplier": [1.5, 2.0, 2.5],
        "risk_reward_ratio": [1.5, 2.0, 2.5],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",
    )


def optimize_bollinger_reversion(
    runner: FullBacktestRunner, instrument: str, period: str
) -> OptimizationResult:
    """Оптимизация параметров Bollinger Reversion стратегии."""

    def strategy_factory(params: Dict) -> BollingerReversionStrategy:
        return BollingerReversionStrategy(
            bb_period=params.get("bb_period", 20),
            bb_std=params.get("bb_std", 2.0),
            rsi_oversold=params.get("rsi_oversold", 30.0),
            rsi_overbought=params.get("rsi_overbought", 70.0),
            adx_ceiling=params.get("adx_ceiling", 25.0),
            atr_multiplier=params.get("atr_multiplier", 1.5),
            risk_reward_ratio=params.get("risk_reward_ratio", 1.5),
        )

    param_grid = {
        "bb_std": [1.5, 2.0, 2.5],
        "rsi_oversold": [25.0, 30.0, 35.0],
        "rsi_overbought": [65.0, 70.0, 75.0],
        "adx_ceiling": [20.0, 25.0, 30.0],
        "atr_multiplier": [1.2, 1.5, 1.8],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Оптимизация параметров стратегий.")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["mean_reversion", "carry_momentum", "momentum_breakout", "combined_momentum", "macd_trend", "bollinger_reversion"],
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
    elif args.strategy == "combined_momentum":
        result = optimize_combined_momentum(runner, args.instrument, args.period)
    elif args.strategy == "macd_trend":
        result = optimize_macd_trend(runner, args.instrument, args.period)
    elif args.strategy == "bollinger_reversion":
        result = optimize_bollinger_reversion(runner, args.instrument, args.period)
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

