"""Скрипт для анализа результатов массовой оптимизации Carry Momentum."""
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

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def analyze_optimization_results(output_dir: Path = Path("research/configs/optimized")) -> None:
    """Анализирует результаты оптимизации и создает сводную таблицу."""
    
    if not output_dir.exists():
        log.error("Директория с результатами не найдена: %s", output_dir)
        return
    
    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    periods = ["m15", "h1", "h4"]
    
    results = []
    
    for instrument in instruments:
        for period in periods:
            best_params_path = output_dir / f"carry_momentum_{instrument}_{period}.json"
            all_results_path = output_dir / f"carry_momentum_{instrument}_{period}_all_results.json"
            
            if not best_params_path.exists():
                log.warning("Файл не найден: %s", best_params_path)
                continue
            
            try:
                # Загружаем лучшие параметры
                with best_params_path.open("r", encoding="utf-8") as fp:
                    best_data = json.load(fp)
                
                # Загружаем все результаты для анализа распределения
                all_results_data = None
                if all_results_path.exists():
                    with all_results_path.open("r", encoding="utf-8") as fp:
                        all_results_data = json.load(fp)
                
                best_score = best_data.get("best_score", 0.0)
                best_params = best_data.get("best_params", {})
                
                # Анализируем распределение результатов
                top_10_scores = []
                if all_results_data:
                    all_scores = [r[1] for r in all_results_data.get("all_results", [])]
                    all_scores.sort(reverse=True)
                    top_10_scores = all_scores[:10] if len(all_scores) >= 10 else all_scores
                
                results.append({
                    "instrument": instrument,
                    "period": period,
                    "best_recovery_factor": best_score,
                    "atr_multiplier": best_params.get("atr_multiplier"),
                    "min_adx": best_params.get("min_adx"),
                    "min_pos_di_advantage": best_params.get("min_pos_di_advantage"),
                    "trend_confirmation_bars": best_params.get("trend_confirmation_bars"),
                    "risk_reward_ratio": best_params.get("risk_reward_ratio"),
                    "top_10_avg": sum(top_10_scores) / len(top_10_scores) if top_10_scores else 0.0,
                    "total_combinations_tested": len(all_results_data.get("all_results", [])) if all_results_data else 0,
                })
                
                log.info("%s %s: Recovery Factor = %.4f", instrument, period, best_score)
                
            except Exception as e:
                log.error("Ошибка при анализе %s %s: %s", instrument, period, e, exc_info=True)
    
    if not results:
        log.warning("Не найдено результатов для анализа")
        return
    
    # Создаем DataFrame для удобного анализа
    df = pd.DataFrame(results)
    
    # Выводим сводную таблицу
    log.info("=" * 80)
    log.info("СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ ОПТИМИЗАЦИИ")
    log.info("=" * 80)
    print("\n" + df.to_string(index=False))
    
    # Сохраняем в CSV
    csv_path = output_dir / "optimization_summary.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    log.info("\nСводная таблица сохранена: %s", csv_path)
    
    # Анализ паттернов
    log.info("\n" + "=" * 80)
    log.info("АНАЛИЗ ПАТТЕРНОВ")
    log.info("=" * 80)
    
    # Средние значения параметров для лучших результатов
    log.info("\nСредние значения параметров для лучших результатов:")
    log.info("  atr_multiplier: %.2f", df["atr_multiplier"].mean())
    log.info("  min_adx: %.2f", df["min_adx"].mean())
    log.info("  min_pos_di_advantage: %.2f", df["min_pos_di_advantage"].mean())
    log.info("  trend_confirmation_bars: %.2f", df["trend_confirmation_bars"].mean())
    log.info("  risk_reward_ratio: %.2f", df["risk_reward_ratio"].mean())
    
    # Лучшие комбинации инструмент/таймфрейм
    log.info("\nЛучшие комбинации инструмент/таймфрейм:")
    top_3 = df.nlargest(3, "best_recovery_factor")
    for _, row in top_3.iterrows():
        log.info("  %s %s: Recovery Factor = %.4f", row["instrument"], row["period"], row["best_recovery_factor"])
    
    # Анализ по инструментам
    log.info("\nСредний Recovery Factor по инструментам:")
    instrument_avg = df.groupby("instrument")["best_recovery_factor"].mean()
    for instrument, avg_rf in instrument_avg.items():
        log.info("  %s: %.4f", instrument, avg_rf)
    
    # Анализ по таймфреймам
    log.info("\nСредний Recovery Factor по таймфреймам:")
    period_avg = df.groupby("period")["best_recovery_factor"].mean()
    for period, avg_rf in period_avg.items():
        log.info("  %s: %.4f", period, avg_rf)
    
    # Универсальные параметры (если есть)
    log.info("\n" + "=" * 80)
    log.info("РЕКОМЕНДАЦИИ")
    log.info("=" * 80)
    
    # Проверяем стабильность параметров
    atr_std = df["atr_multiplier"].std()
    adx_std = df["min_adx"].std()
    rrr_std = df["risk_reward_ratio"].std()
    
    if atr_std < 0.5:
        log.info("✓ atr_multiplier стабилен (std=%.2f), можно использовать универсальное значение: %.2f", 
                atr_std, df["atr_multiplier"].mean())
    else:
        log.info("⚠ atr_multiplier варьируется (std=%.2f), требуется оптимизация для каждого инструмента/таймфрейма", atr_std)
    
    if adx_std < 3.0:
        log.info("✓ min_adx стабилен (std=%.2f), можно использовать универсальное значение: %.2f", 
                adx_std, df["min_adx"].mean())
    else:
        log.info("⚠ min_adx варьируется (std=%.2f), требуется оптимизация для каждого инструмента/таймфрейма", adx_std)
    
    if rrr_std < 0.5:
        log.info("✓ risk_reward_ratio стабилен (std=%.2f), можно использовать универсальное значение: %.2f", 
                rrr_std, df["risk_reward_ratio"].mean())
    else:
        log.info("⚠ risk_reward_ratio варьируется (std=%.2f), требуется оптимизация для каждого инструмента/таймфрейма", rrr_std)
    
    # Проверяем достижение целевых метрик
    log.info("\nДостижение целевых метрик:")
    above_threshold = df[df["best_recovery_factor"] >= 1.5]
    log.info("  Recovery Factor ≥ 1.5: %s из %s комбинаций (%.1f%%)", 
            len(above_threshold), len(df), len(above_threshold) / len(df) * 100 if len(df) > 0 else 0)
    
    log.info("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_optimization_results()

