"""Быстрая проверка текущего прогресса оптимизации."""
import json
from pathlib import Path

config_dir = Path("research/configs/optimized")
files = list(config_dir.glob("carry_momentum_*_all_results.json"))

total = 0
print(f"Найдено файлов результатов: {len(files)}\n")

for f in files:
    try:
        with f.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        count = len(data.get("all_results", []))
        total += count
        print(f"{f.name}:")
        print(f"  Комбинаций: {count}")
        print(f"  Обновлено: {data.get('optimized_at', 'N/A')}")
        print(f"  Лучший результат: {data.get('best_score', 'N/A')}")
        print()
    except Exception as e:
        print(f"Ошибка при чтении {f.name}: {e}")

print(f"=" * 50)
print(f"ВСЕГО ПРОТЕСТИРОВАНО: {total} комбинаций")
print(f"=" * 50)

