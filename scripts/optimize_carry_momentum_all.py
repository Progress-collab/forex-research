"""Скрипт для массовой оптимизации Carry Momentum на всех комбинациях инструментов и таймфреймов."""
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
from scripts.optimize_strategy import optimize_carry_momentum_two_stage, optimize_carry_momentum_fast, optimize_carry_momentum_genetic

# Создаем директорию для логов перед настройкой логирования
log_dir = Path("research/logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "optimization.log", encoding="utf-8"),
        logging.StreamHandler(),  # Также выводим в консоль
    ]
)
log = logging.getLogger(__name__)


def main() -> None:
    """Запускает оптимизацию Carry Momentum для всех комбинаций инструментов и таймфреймов."""
    
    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    periods = ["m15", "h1", "h4"]
    n_jobs = 12  # Параллелизация (12 ядер для ускорения)
    use_genetic = False  # Использовать генетический алгоритм (быстрее для больших пространств параметров)
    use_two_stage = True  # Использовать двухэтапную оптимизацию (быстрее и эффективнее, только если use_genetic=False)
    
    runner = FullBacktestRunner()
    output_dir = Path("research/configs/optimized")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем директорию для логов
    log_dir = Path("research/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    total_combinations = len(instruments) * len(periods)
    current = 0
    
    log.info("Начинаем массовую оптимизацию Carry Momentum")
    log.info("Инструменты: %s", ", ".join(instruments))
    log.info("Таймфреймы: %s", ", ".join(periods))
    log.info("Всего комбинаций: %s", total_combinations)
    log.info("Параллелизация: %s процессов", n_jobs)
    log.info("Режим оптимизации: %s", "Генетический алгоритм" if use_genetic else ("Двухэтапная (быстрая)" if use_two_stage else "Полная"))
    
    results_summary = []
    
    for instrument in instruments:
        for period in periods:
            current += 1
            log.info("=" * 80)
            log.info("[%s/%s] Оптимизация Carry Momentum: %s %s", current, total_combinations, instrument, period)
            log.info("=" * 80)
            
            try:
                # Проверяем наличие данных
                data_path = runner.curated_dir / f"{instrument}_{period}.parquet"
                if not data_path.exists():
                    log.warning("Данные не найдены: %s, пропускаем", data_path)
                    results_summary.append({
                        "instrument": instrument,
                        "period": period,
                        "status": "skipped",
                        "reason": "no_data"
                    })
                    continue
                
                # Проверяем что файл не пустой
                import pandas as pd
                try:
                    test_df = pd.read_parquet(data_path)
                    if test_df.empty:
                        log.warning("Файл данных пуст: %s, пропускаем", data_path)
                        results_summary.append({
                            "instrument": instrument,
                            "period": period,
                            "status": "skipped",
                            "reason": "empty_data"
                        })
                        continue
                except Exception as e:
                    log.warning("Ошибка при чтении данных %s: %s, пропускаем", data_path, e)
                    results_summary.append({
                        "instrument": instrument,
                        "period": period,
                        "status": "skipped",
                        "reason": f"read_error: {e}"
                    })
                    continue
                
                # Запускаем оптимизацию
                if use_genetic:
                    result = optimize_carry_momentum_genetic(
                        runner=runner,
                        instrument=instrument,
                        period=period,
                        n_jobs=n_jobs,
                    )
                elif use_two_stage:
                    result = optimize_carry_momentum_two_stage(
                        runner=runner,
                        instrument=instrument,
                        period=period,
                        n_jobs=n_jobs,
                    )
                else:
                    result = optimize_carry_momentum_fast(
                        runner=runner,
                        instrument=instrument,
                        period=period,
                        n_jobs=n_jobs,
                        early_stopping_threshold=0.1,  # Агрессивный early stopping
                    )
                
                # Сохраняем результаты
                from src.backtesting.optimization import HyperparameterOptimizer
                optimizer = HyperparameterOptimizer(runner)
                
                # Сохраняем лучшие параметры
                best_params_path = output_dir / f"carry_momentum_{instrument}_{period}.json"
                optimizer.save_best_params(result, best_params_path)
                
                # Сохраняем все результаты
                all_results_path = output_dir / f"carry_momentum_{instrument}_{period}_all_results.json"
                optimizer.save_all_results(result, all_results_path)
                
                log.info("Результаты сохранены:")
                log.info("  Лучшие параметры: %s", best_params_path)
                log.info("  Все результаты: %s", all_results_path)
                log.info("  Лучший Recovery Factor: %.4f", result.best_score)
                log.info("  Всего протестировано комбинаций: %s", len(result.all_results))
                
                results_summary.append({
                    "instrument": instrument,
                    "period": period,
                    "status": "completed",
                    "best_recovery_factor": result.best_score,
                    "best_params": result.best_params,
                    "total_combinations_tested": len(result.all_results),
                })
                
            except Exception as e:
                log.error("Ошибка при оптимизации %s %s: %s", instrument, period, e, exc_info=True)
                results_summary.append({
                    "instrument": instrument,
                    "period": period,
                    "status": "error",
                    "error": str(e)
                })
    
    # Выводим сводку результатов
    log.info("=" * 80)
    log.info("СВОДКА РЕЗУЛЬТАТОВ ОПТИМИЗАЦИИ")
    log.info("=" * 80)
    
    for summary in results_summary:
        if summary["status"] == "completed":
            log.info("%s %s: Recovery Factor = %.4f, Параметры: %s",
                    summary["instrument"], summary["period"],
                    summary["best_recovery_factor"],
                    summary["best_params"])
        elif summary["status"] == "skipped":
            log.info("%s %s: Пропущено (%s)", summary["instrument"], summary["period"], summary.get("reason", "unknown"))
        else:
            log.info("%s %s: Ошибка - %s", summary["instrument"], summary["period"], summary.get("error", "unknown"))
    
    log.info("=" * 80)
    log.info("Оптимизация завершена!")


if __name__ == "__main__":
    main()

