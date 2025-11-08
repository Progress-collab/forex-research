"""Расширенный анализ результатов оптимизации с детальной статистикой."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

# Добавляем корень проекта в sys.path для импорта модулей
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner
from src.strategies import CarryMomentumStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def load_best_result(file_path: Path) -> Dict:
    """Загружает лучший результат из файла."""
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_detailed_backtest(params: Dict, instrument: str, period: str) -> Dict:
    """Запускает детальный бэктест и возвращает полную статистику."""
    runner = FullBacktestRunner()
    
    # Создаем стратегию с лучшими параметрами
    strategy = CarryMomentumStrategy(**params)
    
    # Запускаем бэктест
    result = runner.run(strategy, instrument, period)
    
    # Формируем детальную статистику
    stats = {
        "strategy_id": result.strategy_id,
        "instrument": result.instrument,
        "period": result.period,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate": result.win_rate,
        "total_pnl": result.total_pnl,
        "total_commission": result.total_commission,
        "total_swap": result.total_swap,
        "net_pnl": result.net_pnl,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown": result.max_drawdown,
        "recovery_factor": result.recovery_factor,
        "profit_factor": result.profit_factor,
        "average_win": result.average_win,
        "average_loss": result.average_loss,
        "average_win_loss_ratio": abs(result.average_win / result.average_loss) if result.average_loss != 0 else float("inf"),
    }
    
    return stats


def print_detailed_analysis(stats: Dict, params: Dict) -> None:
    """Выводит детальный анализ результатов."""
    log.info("=" * 80)
    log.info("ДЕТАЛЬНЫЙ АНАЛИЗ ЛУЧШЕГО РЕЗУЛЬТАТА")
    log.info("=" * 80)
    
    log.info("\n📊 ОСНОВНЫЕ ПАРАМЕТРЫ:")
    log.info("  Инструмент: %s", stats["instrument"])
    log.info("  Таймфрейм: %s", stats["period"])
    log.info("  Период тестирования: %s - %s", stats["start_date"][:10], stats["end_date"][:10])
    
    log.info("\n⚙️ ПАРАМЕТРЫ СТРАТЕГИИ:")
    for key, value in params.items():
        log.info("  %s: %s", key, value)
    
    log.info("\n📈 СТАТИСТИКА СДЕЛОК:")
    log.info("  Всего сделок: %s", stats["total_trades"])
    log.info("  Прибыльных: %s (%.1f%%)", stats["winning_trades"], stats["win_rate"] * 100)
    log.info("  Убыточных: %s (%.1f%%)", stats["losing_trades"], (1 - stats["win_rate"]) * 100)
    log.info("  Win Rate: %.2f%%", stats["win_rate"] * 100)
    
    log.info("\n💰 ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
    log.info("  Общий PnL: %.2f", stats["total_pnl"])
    log.info("  Комиссии: %.2f", stats["total_commission"])
    log.info("  Свопы: %.2f", stats["total_swap"])
    log.info("  Чистый PnL: %.2f", stats["net_pnl"])
    log.info("  Средний выигрыш: %.2f", stats["average_win"])
    log.info("  Средний проигрыш: %.2f", stats["average_loss"])
    log.info("  Соотношение Win/Loss: %.2f", stats["average_win_loss_ratio"])
    
    log.info("\n📊 МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ:")
    log.info("  Recovery Factor: %.4f", stats["recovery_factor"])
    log.info("  Profit Factor: %.4f", stats["profit_factor"])
    log.info("  Sharpe Ratio: %.4f", stats["sharpe_ratio"])
    log.info("  Max Drawdown: %.2f%%", stats["max_drawdown"] * 100)
    
    log.info("\n✅ ОЦЕНКА РЕЗУЛЬТАТА:")
    
    # Критерии оценки
    recovery_ok = stats["recovery_factor"] >= 1.5
    profit_factor_ok = stats["profit_factor"] > 1.0
    win_rate_ok = stats["win_rate"] >= 0.4  # Минимум 40% выигрышей
    sharpe_ok = stats["sharpe_ratio"] > 1.0
    trades_ok = stats["total_trades"] >= 30  # Минимум 30 сделок для статистической значимости
    
    log.info("  Recovery Factor >= 1.5: %s (%.4f)", "✓" if recovery_ok else "✗", stats["recovery_factor"])
    log.info("  Profit Factor > 1.0: %s (%.4f)", "✓" if profit_factor_ok else "✗", stats["profit_factor"])
    log.info("  Win Rate >= 40%%: %s (%.2f%%)", "✓" if win_rate_ok else "✗", stats["win_rate"] * 100)
    log.info("  Sharpe Ratio > 1.0: %s (%.4f)", "✓" if sharpe_ok else "✗", stats["sharpe_ratio"])
    log.info("  Достаточно сделок (>=30): %s (%s)", "✓" if trades_ok else "✗", stats["total_trades"])
    
    all_ok = recovery_ok and profit_factor_ok and win_rate_ok and sharpe_ok and trades_ok
    log.info("\n  ОБЩАЯ ОЦЕНКА: %s", "✓ ПРИЕМЛЕМО ДЛЯ ПАПЕР-ТРЕЙДИНГА" if all_ok else "⚠ ТРЕБУЕТСЯ ДОРАБОТКА")
    
    log.info("\n" + "=" * 80)


def main() -> None:
    """Запускает расширенный анализ результатов оптимизации."""
    
    best_result_file = Path("research/configs/optimized/best_result.json")
    
    if not best_result_file.exists():
        log.error("Файл с лучшим результатом не найден: %s", best_result_file)
        log.info("Сначала запустите: python scripts/extract_and_analyze_results.py")
        return
    
    # Загружаем лучший результат
    best_data = load_best_result(best_result_file)
    params = best_data["best_params"]
    instrument_period = best_data["instrument"]
    
    # Парсим инструмент и таймфрейм
    if "_" in instrument_period:
        parts = instrument_period.split("_")
        instrument = parts[0]
        period = "_".join(parts[1:])
    else:
        instrument = instrument_period
        period = "m15"
    
    log.info("Запускаем детальный бэктест с лучшими параметрами...")
    log.info("Инструмент: %s, Таймфрейм: %s", instrument, period)
    
    # Запускаем детальный бэктест
    try:
        stats = run_detailed_backtest(params, instrument, period)
        
        # Выводим детальный анализ
        print_detailed_analysis(stats, params)
        
        # Сохраняем детальную статистику
        stats_file = Path("research/configs/optimized/best_result_detailed_stats.json")
        with stats_file.open("w", encoding="utf-8") as f:
            json.dump({
                "params": params,
                "stats": stats,
            }, f, ensure_ascii=False, indent=2)
        
        log.info("Детальная статистика сохранена в: %s", stats_file)
        
    except Exception as e:
        log.error("Ошибка при запуске детального бэктеста: %s", e, exc_info=True)


if __name__ == "__main__":
    main()

