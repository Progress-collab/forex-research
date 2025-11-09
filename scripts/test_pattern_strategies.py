"""Скрипт для тестирования стратегий на основе паттернов."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта модулей
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding

setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner
from src.strategies import PatternReversalStrategy, PatternBreakoutStrategy, PatternHeadShouldersStrategy
from src.patterns.candlestick import detect_hammer, detect_engulfing, detect_doji
from src.patterns.chart import detect_double_top, detect_double_bottom, detect_head_shoulders_top, detect_head_shoulders_bottom
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def test_pattern_detection():
    """Тестирует обнаружение паттернов на реальных данных."""
    log.info("=" * 80)
    log.info("ТЕСТИРОВАНИЕ ОБНАРУЖЕНИЯ ПАТТЕРНОВ")
    log.info("=" * 80)

    curated_dir = Path("data/v1/curated/ctrader")
    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    period = "m15"

    for instrument in instruments:
        log.info("\n" + "-" * 80)
        log.info("Инструмент: %s", instrument)
        log.info("-" * 80)

        try:
            data_path = curated_dir / f"{instrument}_{period}.parquet"
            if not data_path.exists():
                log.warning("Данные не найдены: %s", data_path)
                continue
            
            df = pd.read_parquet(data_path)
            df["utc_time"] = pd.to_datetime(df["utc_time"])
            df = df.set_index("utc_time").sort_index()
            
            # Берем последние 500 баров
            df = df.tail(500)
            
            # Убеждаемся, что есть колонка instrument
            if "instrument" not in df.columns:
                df["instrument"] = instrument

            # Проверяем наличие необходимых колонок
            required_cols = ["open", "high", "low", "close"]
            if not all(col in df.columns for col in required_cols):
                log.warning("Отсутствуют необходимые колонки для %s", instrument)
                continue

            # Тестируем свечные паттерны
            hammer_idx = detect_hammer(df)
            bullish_engulfing_idx = detect_engulfing(df, bullish=True)
            bearish_engulfing_idx = detect_engulfing(df, bullish=False)
            doji_idx = detect_doji(df)

            log.info("Свечные паттерны:")
            log.info("  Hammer: %s", hammer_idx if hammer_idx else "не найден")
            log.info("  Bullish Engulfing: %s", bullish_engulfing_idx if bullish_engulfing_idx else "не найден")
            log.info("  Bearish Engulfing: %s", bearish_engulfing_idx if bearish_engulfing_idx else "не найден")
            log.info("  Doji: %s", doji_idx if doji_idx else "не найден")

            # Тестируем графические паттерны
            double_top = detect_double_top(df)
            double_bottom = detect_double_bottom(df)

            log.info("Графические паттерны:")
            log.info("  Double Top: %s", double_top if double_top else "не найден")
            log.info("  Double Bottom: %s", double_bottom if double_bottom else "не найден")
            
            # Тестируем Head & Shoulders
            hst = detect_head_shoulders_top(df)
            hsb = detect_head_shoulders_bottom(df)
            
            log.info("Head & Shoulders:")
            log.info("  HST (Top): %s", hst if hst else "не найден")
            log.info("  HSB (Bottom): %s", hsb if hsb else "не найден")

        except Exception as e:
            log.error("Ошибка при тестировании %s: %s", instrument, e, exc_info=True)


def test_strategies():
    """Тестирует стратегии на основе паттернов через бэктест."""
    log.info("\n" + "=" * 80)
    log.info("ТЕСТИРОВАНИЕ СТРАТЕГИЙ НА ОСНОВЕ ПАТТЕРНОВ")
    log.info("=" * 80)

    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    periods = ["m15", "h1"]

    runner = FullBacktestRunner()

    strategies = [
        ("Pattern Reversal", PatternReversalStrategy()),
        ("Pattern Breakout", PatternBreakoutStrategy()),
        ("Pattern Head & Shoulders", PatternHeadShouldersStrategy()),
    ]

    results_summary = []

    for strategy_name, strategy in strategies:
        log.info("\n" + "-" * 80)
        log.info("Стратегия: %s", strategy_name)
        log.info("-" * 80)

        for instrument in instruments:
            for period in periods:
                log.info("\nТестирование: %s %s", instrument, period)

                try:
                    result = runner.run(strategy, instrument, period)

                    log.info("Результаты:")
                    log.info("  Всего сделок: %s", result.total_trades)
                    log.info("  Прибыльных: %s (%.1f%%)", result.winning_trades, result.win_rate * 100)
                    log.info("  Убыточных: %s", result.losing_trades)
                    log.info("  Net PnL: %.2f", result.net_pnl)
                    log.info("  Recovery Factor: %.4f", result.recovery_factor)
                    log.info("  Profit Factor: %.4f", result.profit_factor)
                    log.info("  Sharpe Ratio: %.4f", result.sharpe_ratio)
                    log.info("  Max Drawdown: %.2f%%", result.max_drawdown * 100)

                    results_summary.append(
                        {
                            "strategy": strategy_name,
                            "instrument": instrument,
                            "period": period,
                            "total_trades": result.total_trades,
                            "win_rate": result.win_rate,
                            "net_pnl": result.net_pnl,
                            "recovery_factor": result.recovery_factor,
                            "profit_factor": result.profit_factor,
                            "sharpe_ratio": result.sharpe_ratio,
                            "max_drawdown": result.max_drawdown,
                        }
                    )

                except Exception as e:
                    log.error("Ошибка при тестировании %s %s %s: %s", strategy_name, instrument, period, e, exc_info=True)
                    results_summary.append(
                        {
                            "strategy": strategy_name,
                            "instrument": instrument,
                            "period": period,
                            "status": "error",
                            "error": str(e),
                        }
                    )

    # Выводим сводку
    log.info("\n" + "=" * 80)
    log.info("СВОДКА ТЕСТИРОВАНИЯ СТРАТЕГИЙ")
    log.info("=" * 80)

    completed = [r for r in results_summary if "status" not in r or r["status"] != "error"]
    if completed:
        log.info("\nУспешно протестировано: %s комбинаций", len(completed))

        # Группируем по стратегиям
        for strategy_name in set(r["strategy"] for r in completed):
            strategy_results = [r for r in completed if r["strategy"] == strategy_name]
            log.info("\n%s:", strategy_name)
            log.info("  Всего комбинаций: %s", len(strategy_results))
            log.info("  Средний Win Rate: %.1f%%", sum(r["win_rate"] for r in strategy_results) / len(strategy_results) * 100)
            log.info("  Средний Net PnL: %.2f", sum(r["net_pnl"] for r in strategy_results) / len(strategy_results))
            log.info("  Средний Recovery Factor: %.4f", sum(r["recovery_factor"] for r in strategy_results) / len(strategy_results))
            log.info("  Средний Profit Factor: %.4f", sum(r["profit_factor"] for r in strategy_results) / len(strategy_results))

        # Лучшие результаты
        log.info("\nЛучшие результаты:")
        best_recovery = max(completed, key=lambda r: r["recovery_factor"])
        log.info(
            "  Лучший Recovery Factor: %s %s %s (%.4f)",
            best_recovery["strategy"],
            best_recovery["instrument"],
            best_recovery["period"],
            best_recovery["recovery_factor"],
        )

        best_profit = max(completed, key=lambda r: r["profit_factor"])
        log.info(
            "  Лучший Profit Factor: %s %s %s (%.4f)",
            best_profit["strategy"],
            best_profit["instrument"],
            best_profit["period"],
            best_profit["profit_factor"],
        )

    log.info("\n" + "=" * 80)


if __name__ == "__main__":
    # Сначала тестируем обнаружение паттернов
    test_pattern_detection()

    # Затем тестируем стратегии
    test_strategies()

