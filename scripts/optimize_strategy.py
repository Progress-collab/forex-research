from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner
from src.backtesting.optimization import HyperparameterOptimizer, OptimizationResult
from src.backtesting.genetic_optimization import GeneticOptimizer
from src.strategies import (
    BollingerReversionStrategy,
    CarryMomentumStrategy,
    CombinedMomentumStrategy,
    MACDTrendStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
)

log = logging.getLogger(__name__)


def check_running_optimization() -> bool:
    """Проверяет, запущена ли уже оптимизация."""
    import subprocess
    try:
        # Проверяем процессы Python, связанные с оптимизацией
        result = subprocess.run(
            ["powershell", "-Command", 
             "Get-Process python -ErrorAction SilentlyContinue | "
             "Where-Object { (Get-CimInstance Win32_Process -Filter \"ProcessId = $($_.Id)\" | "
             "Select-Object -ExpandProperty CommandLine) -like '*optimize_strategy*' } | "
             "Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True,
            text=True,
            timeout=5
        )
        count = int(result.stdout.strip())
        return count > 0
    except Exception:
        return False


def optimize_momentum_breakout(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = None
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

    # Уменьшенная сетка для быстрого теста (можно вернуть полную)
    param_grid = {
        "atr_multiplier": [1.8, 2.0, 2.2],
        "adx_threshold": [18, 20, 22],
        "lookback_hours": [20, 24],
        "confirmation_bars": [1, 2],
        "min_pos_di_advantage": [1.0, 2.0],
    }

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="profit_factor",  # Главная цель: Profit Factor > 1
        n_jobs=n_jobs,
        early_stopping_threshold=early_stopping_threshold,
    )


def optimize_mean_reversion(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = None
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
        n_jobs=n_jobs,
        early_stopping_threshold=early_stopping_threshold,
    )


def optimize_carry_momentum_fast(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = 0.1
) -> OptimizationResult:
    """Быстрая оптимизация параметров Carry Momentum с уменьшенной сеткой."""
    
    def strategy_factory(params: Dict) -> CarryMomentumStrategy:
        return CarryMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            min_adx=params.get("min_adx", 20.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            trend_confirmation_bars=params.get("trend_confirmation_bars", 3),
            max_volatility_pct=params.get("max_volatility_pct", 0.15),
            min_volatility_pct=params.get("min_volatility_pct", 0.08),
            # avoid_hours удален - стратегия торгует в любые часы
            min_rsi_long=params.get("min_rsi_long", 50.0),
            max_rsi_short=params.get("max_rsi_short", 50.0),
            enable_short_trades=params.get("enable_short_trades", False),
        )

    # Уменьшенная сетка параметров для быстрого поиска
    param_grid = {
        "atr_multiplier": [1.5, 2.0, 2.5, 3.0],  # 4 значения вместо 7
        "min_adx": [16, 20, 24],  # 3 значения вместо 8
        "min_pos_di_advantage": [1.0, 2.0, 3.0],  # 3 значения вместо 8
        "trend_confirmation_bars": [2, 3, 4],  # 3 значения вместо 6
        "risk_reward_ratio": [1.5, 2.0, 2.5, 3.0],  # 4 значения вместо 8
    }
    # Всего комбинаций: 4 × 3 × 3 × 3 × 4 = 432 (вместо 21,504)

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="recovery_factor",
        n_jobs=n_jobs,
        early_stopping_threshold=early_stopping_threshold,
        stage_info="Этап 1/2",  # Добавляем информацию об этапе
    )


def optimize_carry_momentum_genetic(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12
) -> OptimizationResult:
    """Генетическая оптимизация параметров Carry Momentum стратегии."""
    
    def strategy_factory(params: Dict) -> CarryMomentumStrategy:
        return CarryMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            min_adx=params.get("min_adx", 20.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            trend_confirmation_bars=params.get("trend_confirmation_bars", 3),
            max_volatility_pct=params.get("max_volatility_pct", 0.15),
            min_volatility_pct=params.get("min_volatility_pct", 0.08),
            min_rsi_long=params.get("min_rsi_long", 50.0),
            max_rsi_short=params.get("max_rsi_short", 50.0),
            enable_short_trades=params.get("enable_short_trades", False),
        )
    
    # Сетка параметров для генетического алгоритма
    param_grid = {
        "atr_multiplier": [1.5, 2.0, 2.5, 3.0, 3.5],
        "min_adx": [14, 16, 18, 20, 22, 24, 26],
        "min_pos_di_advantage": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        "trend_confirmation_bars": [2, 3, 4, 5],
        "risk_reward_ratio": [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
    }
    
    optimizer = GeneticOptimizer(runner)
    
    # Путь для промежуточного сохранения результатов
    from pathlib import Path
    output_dir = Path("research/configs/optimized")
    output_dir.mkdir(parents=True, exist_ok=True)
    intermediate_path = output_dir / f"carry_momentum_{instrument}_{period}_all_results.json"
    
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="recovery_factor",
        n_jobs=n_jobs,
        strategy_factory_name="carry_momentum",
        intermediate_save_path=intermediate_path,
    )


def optimize_carry_momentum_two_stage(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12
) -> OptimizationResult:
    """Двухэтапная оптимизация: грубый поиск → точный поиск вокруг лучших результатов."""
    
    log.info("Этап 1: Грубый поиск с уменьшенной сеткой")
    # Первый этап: грубый поиск
    coarse_result = optimize_carry_momentum_fast(
        runner=runner,
        instrument=instrument,
        period=period,
        n_jobs=n_jobs,
        early_stopping_threshold=0.1,  # Агрессивный early stopping
    )
    
    if not coarse_result.best_params:
        log.warning("Грубый поиск не дал результатов, возвращаем пустой результат")
        return coarse_result
    
    log.info("Этап 1 завершен. Лучший Recovery Factor: %.4f", coarse_result.best_score)
    log.info("Лучшие параметры: %s", coarse_result.best_params)
    
    # Проверяем валидность результата этапа 1
    if coarse_result.best_score >= 100.0:
        log.warning("⚠ Recovery Factor = %.4f может быть некорректным (inf заменен на 100)", coarse_result.best_score)
        log.warning("  Это может означать отсутствие просадок или недостаточное количество сделок")
        log.warning("  Рекомендуется проверить количество сделок и другие метрики")
    
    # Второй этап: точный поиск вокруг лучших параметров
    log.info("Этап 2: Точный поиск вокруг лучших параметров")
    
    best = coarse_result.best_params
    
    # Создаем узкую сетку вокруг лучших значений
    fine_param_grid = {
        "atr_multiplier": _create_fine_grid(best.get("atr_multiplier", 2.0), step=0.2, count=5),
        "min_adx": _create_fine_grid(best.get("min_adx", 20.0), step=2.0, count=5, is_int=True),
        "min_pos_di_advantage": _create_fine_grid(best.get("min_pos_di_advantage", 2.0), step=0.5, count=5),
        "trend_confirmation_bars": _create_fine_grid(best.get("trend_confirmation_bars", 3), step=1, count=5, is_int=True),
        "risk_reward_ratio": _create_fine_grid(best.get("risk_reward_ratio", 2.0), step=0.3, count=5),
    }
    
    def strategy_factory(params: Dict) -> CarryMomentumStrategy:
        return CarryMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            min_adx=params.get("min_adx", 20.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            trend_confirmation_bars=params.get("trend_confirmation_bars", 3),
            max_volatility_pct=params.get("max_volatility_pct", 0.15),
            min_volatility_pct=params.get("min_volatility_pct", 0.08),
            # avoid_hours удален - стратегия торгует в любые часы
            min_rsi_long=params.get("min_rsi_long", 50.0),
            max_rsi_short=params.get("max_rsi_short", 50.0),
            enable_short_trades=params.get("enable_short_trades", False),
        )
    
    optimizer = HyperparameterOptimizer(runner)
    fine_result = optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=fine_param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="recovery_factor",
        n_jobs=n_jobs,
        early_stopping_threshold=None,  # На втором этапе не используем early stopping
        stage_info="Этап 2/2",  # Добавляем информацию об этапе
    )
    
    # Объединяем результаты обоих этапов
    all_results = coarse_result.all_results + fine_result.all_results
    
    # Выбираем лучший результат из обоих этапов
    if fine_result.best_score > coarse_result.best_score:
        log.info("Этап 2 улучшил результат: %.4f -> %.4f", coarse_result.best_score, fine_result.best_score)
        return OptimizationResult(
            best_params=fine_result.best_params,
            best_score=fine_result.best_score,
            all_results=all_results,
            optimization_metric="recovery_factor",
        )
    else:
        log.info("Этап 2 не улучшил результат, используем результат этапа 1")
        return OptimizationResult(
            best_params=coarse_result.best_params,
            best_score=coarse_result.best_score,
            all_results=all_results,
            optimization_metric="recovery_factor",
        )


def _create_fine_grid(center: float, step: float, count: int, is_int: bool = False) -> List:
    """Создает сетку значений вокруг центрального значения."""
    half = count // 2
    values = []
    for i in range(-half, half + 1):
        val = center + i * step
        if is_int:
            val = int(round(val))
        values.append(val)
    return sorted(set(values))  # Убираем дубликаты и сортируем


def optimize_carry_momentum(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = None
) -> OptimizationResult:
    """Оптимизация параметров Carry Momentum стратегии с расширенными диапазонами."""

    def strategy_factory(params: Dict) -> CarryMomentumStrategy:
        return CarryMomentumStrategy(
            atr_multiplier=params.get("atr_multiplier", 2.0),
            min_adx=params.get("min_adx", 20.0),
            risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
            min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
            trend_confirmation_bars=params.get("trend_confirmation_bars", 3),
            max_volatility_pct=params.get("max_volatility_pct", 0.15),
            min_volatility_pct=params.get("min_volatility_pct", 0.08),
            # avoid_hours удален - стратегия торгует в любые часы
            min_rsi_long=params.get("min_rsi_long", 50.0),
            max_rsi_short=params.get("max_rsi_short", 50.0),
            enable_short_trades=params.get("enable_short_trades", False),
        )

    # Расширенная сетка параметров для полного поиска
    param_grid = {
        "atr_multiplier": [1.5, 1.8, 2.1, 2.4, 2.7, 3.0, 3.3],  # 7 значений, шаг 0.3
        "min_adx": [14, 16, 18, 20, 22, 24, 26, 28],  # 8 значений, расширено
        "min_pos_di_advantage": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],  # 8 значений, расширено
        "trend_confirmation_bars": [1, 2, 3, 4, 5, 6],  # 6 значений, расширено
        "risk_reward_ratio": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],  # 8 значений, шаг 0.5
    }
    # Всего комбинаций: 7 × 8 × 8 × 6 × 8 = 21,504

    optimizer = HyperparameterOptimizer(runner)
    return optimizer.optimize(
        strategy_factory=strategy_factory,
        param_grid=param_grid,
        instrument=instrument,
        period=period,
        optimization_metric="recovery_factor",  # Изменено на Recovery Factor
        n_jobs=n_jobs,
        early_stopping_threshold=early_stopping_threshold,
    )


def optimize_combined_momentum(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = None
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
        n_jobs=n_jobs,
    )


def optimize_macd_trend(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = None
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
        n_jobs=n_jobs,
    )


def optimize_bollinger_reversion(
    runner: FullBacktestRunner, instrument: str, period: str, n_jobs: int = 12, early_stopping_threshold: Optional[float] = None
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
        n_jobs=n_jobs,
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
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=12,
        help="Количество параллельных процессов для оптимизации (по умолчанию 12 для ускорения).",
    )
    parser.add_argument(
        "--save-all-results",
        action="store_true",
        help="Сохранять все результаты оптимизации, а не только лучшие параметры.",
    )
    parser.add_argument(
        "--early-stopping-threshold",
        type=float,
        default=None,
        help="Порог для раннего прекращения (например, 0.5 означает пропускать результаты < 0.5 * best_score).",
    )
    parser.add_argument(
        "--use-genetic",
        action="store_true",
        help="Использовать генетический алгоритм вместо grid search (только для carry_momentum).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Проверяем, не запущена ли уже оптимизация
    if check_running_optimization():
        log.warning("Обнаружена уже запущенная оптимизация! Завершите её перед запуском новой.")
        log.warning("Используйте скрипт scripts/stop_optimization.py для остановки всех процессов.")
        return

    runner = FullBacktestRunner()

    if args.strategy == "mean_reversion":
        result = optimize_mean_reversion(runner, args.instrument, args.period, args.n_jobs, args.early_stopping_threshold)
    elif args.strategy == "carry_momentum":
        if args.use_genetic:
            result = optimize_carry_momentum_genetic(runner, args.instrument, args.period, args.n_jobs)
        else:
            result = optimize_carry_momentum(runner, args.instrument, args.period, args.n_jobs, args.early_stopping_threshold)
    elif args.strategy == "momentum_breakout":
        result = optimize_momentum_breakout(runner, args.instrument, args.period, args.n_jobs, args.early_stopping_threshold)
    elif args.strategy == "combined_momentum":
        result = optimize_combined_momentum(runner, args.instrument, args.period, args.n_jobs, args.early_stopping_threshold)
    elif args.strategy == "macd_trend":
        result = optimize_macd_trend(runner, args.instrument, args.period, args.n_jobs, args.early_stopping_threshold)
    elif args.strategy == "bollinger_reversion":
        result = optimize_bollinger_reversion(runner, args.instrument, args.period, args.n_jobs, args.early_stopping_threshold)
    else:
        raise ValueError(f"Неизвестная стратегия: {args.strategy}")

    # Сохраняем результаты
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.strategy}_{args.instrument}_{args.period}.json"
    optimizer = HyperparameterOptimizer(runner)
    optimizer.save_best_params(result, output_path)
    
    # Сохраняем все результаты если запрошено
    if args.save_all_results:
        all_results_path = output_dir / f"{args.strategy}_{args.instrument}_{args.period}_all_results.json"
        optimizer.save_all_results(result, all_results_path)

    logging.info("Оптимизация завершена. Лучшие параметры:")
    logging.info("  %s", json.dumps(result.best_params, indent=2))
    logging.info("  Score (%s): %.4f", result.optimization_metric, result.best_score)
    logging.info("  Всего протестировано комбинаций: %s", len(result.all_results))


if __name__ == "__main__":
    main()

