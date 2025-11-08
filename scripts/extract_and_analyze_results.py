"""Скрипт для извлечения промежуточных результатов из логов и анализа лучших результатов."""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Добавляем корень проекта в sys.path для импорта модулей
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def extract_results_from_logs(log_path: Path) -> List[Tuple[str, float]]:
    """Извлекает результаты из логов оптимизации."""
    results = []
    
    if not log_path.exists():
        log.warning("Файл логов не найден: %s", log_path)
        return results
    
    # Паттерн для поиска лучших результатов
    pattern = re.compile(r'recovery_factor = ([\d.]+)')
    
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                score = float(match.group(1))
                results.append((line.strip(), score))
    
    return results


def load_all_results(file_path: Path) -> Dict:
    """Загружает все результаты из JSON файла."""
    if not file_path.exists():
        return {}
    
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_best_result(all_results_files: List[Path], log_path: Path) -> Tuple[Dict, float, str]:
    """Находит лучший результат из всех доступных источников."""
    best_score = float("-inf")
    best_params = {}
    best_source = ""
    
    # Проверяем файлы результатов - ищем лучший из всех результатов, а не только best_score
    for result_file in all_results_files:
        if result_file.exists():
            data = load_all_results(result_file)
            
            # Проверяем best_score
            file_best_score = data.get("best_score", float("-inf"))
            
            # Но также проверяем все результаты в all_results
            all_results_list = data.get("all_results", [])
            if all_results_list:
                # Фильтруем некорректные результаты (>= 100.0 означает inf)
                valid_results = [(r["params"], r["score"]) for r in all_results_list 
                                if isinstance(r.get("score"), (int, float)) and r.get("score", 0) < 100.0]
                
                if valid_results:
                    # Находим лучший из валидных результатов
                    best_from_all = max(valid_results, key=lambda x: x[1])
                    if best_from_all[1] > best_score:
                        best_score = best_from_all[1]
                        best_params = best_from_all[0]
                        best_source = f"Файл: {result_file.name} (из all_results)"
                elif file_best_score < 100.0 and file_best_score > best_score:
                    # Используем best_score если он валидный
                    best_score = file_best_score
                    best_params = data.get("best_params", {})
                    best_source = f"Файл: {result_file.name} (best_score)"
    
    # Проверяем логи
    log_results = extract_results_from_logs(log_path)
    if log_results:
        log_scores = [score for _, score in log_results if score < 100.0]  # Фильтруем некорректные
        if log_scores:
            max_log_score = max(log_scores)
            if max_log_score > best_score:
                best_score = max_log_score
                best_source = f"Логи: {log_path.name}"
                # Пытаемся найти параметры из последнего лучшего результата в логах
                # (это сложно, так как параметры не логируются, но можем использовать последний найденный)
    
    return best_params, best_score, best_source


def main() -> None:
    """Анализирует результаты оптимизации и находит лучший."""
    
    results_dir = Path("research/configs/optimized")
    log_path = Path("research/logs/optimization.log")
    
    # Находим все файлы результатов
    all_results_files = list(results_dir.glob("carry_momentum_*_all_results.json"))
    
    log.info("=" * 80)
    log.info("АНАЛИЗ РЕЗУЛЬТАТОВ ОПТИМИЗАЦИИ")
    log.info("=" * 80)
    
    if not all_results_files:
        log.warning("Файлы результатов не найдены в %s", results_dir)
    
    # Анализируем каждый файл
    all_best_results = []
    
    for result_file in all_results_files:
        data = load_all_results(result_file)
        if data:
            instrument = result_file.stem.replace("carry_momentum_", "").replace("_all_results", "")
            
            # Ищем лучший результат из всех результатов, а не только best_score
            all_results_list = data.get("all_results", [])
            best_score = data.get("best_score", 0.0)
            best_params = data.get("best_params", {})
            
            # Фильтруем некорректные результаты и находим реальный лучший
            if all_results_list:
                valid_results = [(r["params"], r["score"]) for r in all_results_list 
                                if isinstance(r.get("score"), (int, float)) and r.get("score", 0) < 100.0]
                if valid_results:
                    best_from_all = max(valid_results, key=lambda x: x[1])
                    if best_from_all[1] > best_score or best_score >= 100.0:
                        best_score = best_from_all[1]
                        best_params = best_from_all[0]
            
            total_combinations = data.get("total_combinations", len(all_results_list) if all_results_list else 0)
            
            log.info("\n%s:", instrument)
            log.info("  Лучший Recovery Factor: %.4f", best_score)
            log.info("  Лучшие параметры: %s", best_params)
            log.info("  Всего комбинаций: %s", total_combinations)
            
            all_best_results.append({
                "instrument": instrument,
                "score": best_score,
                "params": best_params,
                "file": result_file,
            })
    
    # Извлекаем результаты из логов
    log_results = extract_results_from_logs(log_path)
    if log_results:
        log.info("\nРезультаты из логов:")
        log_scores = [score for _, score in log_results]
        log.info("  Найдено результатов: %s", len(log_results))
        log.info("  Лучший Recovery Factor: %.4f", max(log_scores) if log_scores else 0.0)
        log.info("  Последние 5 результатов: %s", log_scores[-5:] if len(log_scores) >= 5 else log_scores)
    
    # Находим абсолютно лучший результат
    if all_best_results:
        best_overall = max(all_best_results, key=lambda x: x["score"])
        log.info("\n" + "=" * 80)
        log.info("ЛУЧШИЙ РЕЗУЛЬТАТ:")
        log.info("=" * 80)
        log.info("Инструмент/Таймфрейм: %s", best_overall["instrument"])
        log.info("Recovery Factor: %.4f", best_overall["score"])
        log.info("Параметры: %s", best_overall["params"])
        log.info("Файл: %s", best_overall["file"])
        
        # Сохраняем лучший результат в отдельный файл
        best_file = results_dir / "best_result.json"
        with best_file.open("w", encoding="utf-8") as f:
            json.dump({
                "instrument": best_overall["instrument"],
                "best_score": best_overall["score"],
                "best_params": best_overall["params"],
                "source_file": str(best_overall["file"]),
            }, f, ensure_ascii=False, indent=2)
        
        log.info("\nЛучший результат сохранен в: %s", best_file)
        log.info("\nДля визуализации сделок используйте:")
        log.info("  python scripts/visualize_trades.py --strategy carry_momentum --instrument %s --params-file %s",
                best_overall["instrument"].split("_")[0] if "_" in best_overall["instrument"] else "EURUSD",
                best_file)
    else:
        log.warning("Не найдено завершенных результатов оптимизации")


if __name__ == "__main__":
    main()

