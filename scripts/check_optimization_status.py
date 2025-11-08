"""Скрипт для проверки статуса оптимизации Carry Momentum."""
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def check_optimization_status() -> None:
    """Проверяет статус оптимизации."""
    
    config_dir = Path("research/configs/optimized")
    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    periods = ["m15", "h1", "h4"]
    
    # Для двухэтапной оптимизации: 432 (этап 1) + ~125 (этап 2) = ~557 комбинаций
    # Для полной оптимизации: 21,504 комбинаций
    # Определяем тип оптимизации по количеству результатов
    total_combinations_fast = 432  # Быстрая оптимизация (этап 1)
    total_combinations_full = 21_504  # Полная оптимизация
    
    log.info("=" * 80)
    log.info("СТАТУС ОПТИМИЗАЦИИ CARRY MOMENTUM")
    log.info("=" * 80)
    
    completed = []
    in_progress = []
    not_started = []
    total_tested = 0
    
    for instrument in instruments:
        for period in periods:
            best_params_path = config_dir / f"carry_momentum_{instrument}_{period}.json"
            all_results_path = config_dir / f"carry_momentum_{instrument}_{period}_all_results.json"
            
            # Проверяем время последнего изменения файлов
            best_params_time = best_params_path.stat().st_mtime if best_params_path.exists() else 0
            all_results_time = all_results_path.stat().st_mtime if all_results_path.exists() else 0
            last_update = max(best_params_time, all_results_time)
            
            if best_params_path.exists() and all_results_path.exists():
                # Завершено
                try:
                    with all_results_path.open("r", encoding="utf-8") as fp:
                        all_data = json.load(fp)
                    tested_count = len(all_data.get("all_results", []))
                    total_combinations_in_file = all_data.get("total_combinations", tested_count)
                    total_tested += tested_count
                    
                    # Определяем тип оптимизации по количеству комбинаций
                    if total_combinations_in_file <= 600:
                        opt_type = "быстрая (двухэтапная)"
                        expected_total = total_combinations_fast
                    else:
                        opt_type = "полная"
                        expected_total = total_combinations_full
                    
                    with best_params_path.open("r", encoding="utf-8") as fp:
                        best_data = json.load(fp)
                    
                    from datetime import datetime
                    update_time = datetime.fromtimestamp(last_update).strftime("%Y-%m-%d %H:%M:%S")
                    
                    completed.append({
                        "instrument": instrument,
                        "period": period,
                        "tested": tested_count,
                        "expected_total": expected_total,
                        "best_score": best_data.get("best_score", 0.0),
                        "progress_pct": (tested_count / expected_total * 100) if tested_count < expected_total else 100.0,
                        "opt_type": opt_type,
                        "last_update": update_time,
                    })
                except Exception as e:
                    log.warning("Ошибка при чтении результатов для %s %s: %s", instrument, period, e)
                    in_progress.append({"instrument": instrument, "period": period})
            elif best_params_path.exists() or all_results_path.exists():
                # В процессе (есть частичные результаты)
                try:
                    if all_results_path.exists():
                        with all_results_path.open("r", encoding="utf-8") as fp:
                            all_data = json.load(fp)
                        tested_count = len(all_data.get("all_results", []))
                        total_tested += tested_count
                        from datetime import datetime
                        update_time = datetime.fromtimestamp(all_results_time).strftime("%Y-%m-%d %H:%M:%S")
                        in_progress.append({
                            "instrument": instrument,
                            "period": period,
                            "tested": tested_count,
                            "last_update": update_time,
                        })
                    else:
                        in_progress.append({"instrument": instrument, "period": period})
                except Exception:
                    in_progress.append({"instrument": instrument, "period": period})
            else:
                # Не начато
                not_started.append({"instrument": instrument, "period": period})
    
    # Выводим статус
    log.info("\nЗавершено: %s из %s комбинаций инструмент/таймфрейм", len(completed), len(instruments) * len(periods))
    if completed:
        log.info("\nЗавершенные оптимизации:")
        for item in completed:
            log.info("  %s %s (%s): протестировано %s комбинаций (%.1f%%), лучший Recovery Factor = %.4f, обновлено: %s",
                    item["instrument"], item["period"], item["opt_type"], item["tested"], 
                    item["progress_pct"], item["best_score"], item["last_update"])
    
    if in_progress:
        log.info("\nВ процессе: %s", len(in_progress))
        for item in in_progress:
            if "tested" in item:
                log.info("  %s %s: протестировано %s комбинаций, обновлено: %s", 
                        item["instrument"], item["period"], item["tested"], item.get("last_update", "N/A"))
            else:
                log.info("  %s %s", item["instrument"], item["period"])
    
    if not_started:
        log.info("\nНе начато: %s", len(not_started))
        for item in not_started:
            log.info("  %s %s", item["instrument"], item["period"])
    
    # Общий прогресс (приблизительный, так как может быть смешанный тип оптимизации)
    log.info("\n" + "=" * 80)
    log.info("ОБЩИЙ ПРОГРЕСС")
    log.info("=" * 80)
    log.info("Протестировано комбинаций: %s", total_tested)
    log.info("\nПримечание: Количество комбинаций зависит от типа оптимизации:")
    log.info("  - Быстрая (двухэтапная): ~432 комбинаций на пару")
    log.info("  - Полная: 21,504 комбинаций на пару")
    
    log.info("=" * 80)


if __name__ == "__main__":
    check_optimization_status()

