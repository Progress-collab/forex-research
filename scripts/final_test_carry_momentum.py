"""Скрипт для финального тестирования Carry Momentum с оптимизированными параметрами."""
from __future__ import annotations

import json
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
from src.strategies import CarryMomentumStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load_optimized_params(instrument: str, period: str, config_dir: Path = Path("research/configs/optimized")) -> dict | None:
    """Загружает оптимизированные параметры для инструмента и таймфрейма."""
    params_path = config_dir / f"carry_momentum_{instrument}_{period}.json"
    if not params_path.exists():
        return None
    
    with params_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
        return data.get("best_params")


def run_final_tests(config_dir: Path = Path("research/configs/optimized")) -> None:
    """Запускает финальные бэктесты с оптимизированными параметрами."""
    
    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    periods = ["m15", "h1", "h4"]
    
    runner = FullBacktestRunner()
    
    results_summary = []
    
    log.info("=" * 80)
    log.info("ФИНАЛЬНОЕ ТЕСТИРОВАНИЕ CARRY MOMENTUM С ОПТИМИЗИРОВАННЫМИ ПАРАМЕТРАМИ")
    log.info("=" * 80)
    
    for instrument in instruments:
        for period in periods:
            log.info("\n" + "-" * 80)
            log.info("Тестирование: %s %s", instrument, period)
            log.info("-" * 80)
            
            # Загружаем оптимизированные параметры
            params = load_optimized_params(instrument, period, config_dir)
            if not params:
                log.warning("Оптимизированные параметры не найдены для %s %s, пропускаем", instrument, period)
                results_summary.append({
                    "instrument": instrument,
                    "period": period,
                    "status": "skipped",
                    "reason": "no_params"
                })
                continue
            
            # Создаем стратегию с оптимизированными параметрами
            strategy = CarryMomentumStrategy(
                atr_multiplier=params.get("atr_multiplier", 2.0),
                min_adx=params.get("min_adx", 20.0),
                risk_reward_ratio=params.get("risk_reward_ratio", 2.0),
                min_pos_di_advantage=params.get("min_pos_di_advantage", 2.0),
                trend_confirmation_bars=params.get("trend_confirmation_bars", 3),
                max_volatility_pct=params.get("max_volatility_pct", 0.15),
                min_volatility_pct=params.get("min_volatility_pct", 0.08),
                avoid_hours=params.get("avoid_hours", [8, 9, 16, 17, 21, 22, 23, 0, 1, 2, 3, 4, 5]),
                min_rsi_long=params.get("min_rsi_long", 50.0),
                max_rsi_short=params.get("max_rsi_short", 50.0),
                enable_short_trades=params.get("enable_short_trades", False),
            )
            
            try:
                # Запускаем бэктест
                result = runner.run(strategy, instrument, period)
                
                # Проверяем целевые метрики
                recovery_factor_ok = result.recovery_factor >= 1.5
                profit_factor_ok = result.profit_factor > 1.0
                
                log.info("Результаты:")
                log.info("  Всего сделок: %s", result.total_trades)
                log.info("  Прибыльных: %s (%.1f%%)", result.winning_trades, result.win_rate * 100)
                log.info("  Убыточных: %s", result.losing_trades)
                log.info("  Net PnL: %.2f", result.net_pnl)
                log.info("  Recovery Factor: %.4f %s", result.recovery_factor, "✓" if recovery_factor_ok else "✗")
                log.info("  Profit Factor: %.4f %s", result.profit_factor, "✓" if profit_factor_ok else "✗")
                log.info("  Sharpe Ratio: %.4f", result.sharpe_ratio)
                log.info("  Max Drawdown: %.2f%%", result.max_drawdown * 100)
                
                results_summary.append({
                    "instrument": instrument,
                    "period": period,
                    "status": "completed",
                    "total_trades": result.total_trades,
                    "win_rate": result.win_rate,
                    "net_pnl": result.net_pnl,
                    "recovery_factor": result.recovery_factor,
                    "profit_factor": result.profit_factor,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "recovery_factor_ok": recovery_factor_ok,
                    "profit_factor_ok": profit_factor_ok,
                })
                
            except Exception as e:
                log.error("Ошибка при тестировании %s %s: %s", instrument, period, e, exc_info=True)
                results_summary.append({
                    "instrument": instrument,
                    "period": period,
                    "status": "error",
                    "error": str(e)
                })
    
    # Выводим сводку
    log.info("\n" + "=" * 80)
    log.info("СВОДКА ФИНАЛЬНОГО ТЕСТИРОВАНИЯ")
    log.info("=" * 80)
    
    completed = [r for r in results_summary if r["status"] == "completed"]
    if completed:
        log.info("\nУспешно протестировано: %s из %s комбинаций", len(completed), len(results_summary))
        
        # Подсчитываем достижение целевых метрик
        recovery_ok_count = sum(1 for r in completed if r.get("recovery_factor_ok", False))
        profit_ok_count = sum(1 for r in completed if r.get("profit_factor_ok", False))
        both_ok_count = sum(1 for r in completed if r.get("recovery_factor_ok", False) and r.get("profit_factor_ok", False))
        
        log.info("\nДостижение целевых метрик:")
        log.info("  Recovery Factor ≥ 1.5: %s из %s (%.1f%%)", recovery_ok_count, len(completed), 
                recovery_ok_count / len(completed) * 100 if completed else 0)
        log.info("  Profit Factor > 1.0: %s из %s (%.1f%%)", profit_ok_count, len(completed),
                profit_ok_count / len(completed) * 100 if completed else 0)
        log.info("  Обе метрики: %s из %s (%.1f%%)", both_ok_count, len(completed),
                both_ok_count / len(completed) * 100 if completed else 0)
        
        # Средние значения метрик
        avg_recovery = sum(r["recovery_factor"] for r in completed) / len(completed)
        avg_profit = sum(r["profit_factor"] for r in completed) / len(completed)
        avg_sharpe = sum(r["sharpe_ratio"] for r in completed) / len(completed)
        
        log.info("\nСредние значения метрик:")
        log.info("  Средний Recovery Factor: %.4f", avg_recovery)
        log.info("  Средний Profit Factor: %.4f", avg_profit)
        log.info("  Средний Sharpe Ratio: %.4f", avg_sharpe)
        
        # Лучшие результаты
        log.info("\nЛучшие результаты:")
        best_recovery = max(completed, key=lambda r: r["recovery_factor"])
        log.info("  Лучший Recovery Factor: %s %s (%.4f)", 
                best_recovery["instrument"], best_recovery["period"], best_recovery["recovery_factor"])
        
        best_profit = max(completed, key=lambda r: r["profit_factor"])
        log.info("  Лучший Profit Factor: %s %s (%.4f)", 
                best_profit["instrument"], best_profit["period"], best_profit["profit_factor"])
    
    log.info("\n" + "=" * 80)


if __name__ == "__main__":
    run_final_tests()

