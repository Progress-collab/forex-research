"""Скрипт для мониторинга оптимизации в реальном времени."""
import json
import sys
import time
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

def monitor_optimization(interval: int = 5):
    """Мониторит прогресс оптимизации в реальном времени."""
    config_dir = Path("research/configs/optimized")
    instruments = ["EURUSD", "GBPUSD", "USDJPY"]
    periods = ["m15", "h1", "h4"]
    
    print("=" * 80)
    print("МОНИТОРИНГ ОПТИМИЗАЦИИ CARRY MOMENTUM")
    print("Нажмите Ctrl+C для остановки")
    print("=" * 80)
    print()
    
    previous_counts = {}
    
    try:
        while True:
            total_tested = 0
            current_time = time.strftime("%H:%M:%S")
            
            print(f"\n[{current_time}] Проверка прогресса...")
            print("-" * 80)
            
            for instrument in instruments:
                for period in periods:
                    all_results_path = config_dir / f"carry_momentum_{instrument}_{period}_all_results.json"
                    
                    if all_results_path.exists():
                        try:
                            # Проверяем время изменения файла
                            mtime = all_results_path.stat().st_mtime
                            file_time = time.strftime("%H:%M:%S", time.localtime(mtime))
                            
                            with all_results_path.open("r", encoding="utf-8") as fp:
                                data = json.load(fp)
                            
                            count = len(data.get("all_results", []))
                            total_tested += count
                            
                            # Проверяем изменение
                            key = f"{instrument}_{period}"
                            prev_count = previous_counts.get(key, 0)
                            change = count - prev_count
                            previous_counts[key] = count
                            
                            status = ""
                            if change > 0:
                                status = f" (+{change} новых)"
                            
                            best_score = data.get("best_score", 0.0)
                            print(f"  {instrument} {period}: {count} комбинаций, лучший RF = {best_score:.4f}, обновлено: {file_time}{status}")
                            
                        except Exception as e:
                            print(f"  {instrument} {period}: ошибка чтения - {e}")
                    else:
                        # Проверяем есть ли частичные результаты (best_params без all_results)
                        best_params_path = config_dir / f"carry_momentum_{instrument}_{period}.json"
                        if best_params_path.exists():
                            mtime = best_params_path.stat().st_mtime
                            file_time = time.strftime("%H:%M:%S", time.localtime(mtime))
                            print(f"  {instrument} {period}: оптимизация начата, обновлено: {file_time}")
                        else:
                            print(f"  {instrument} {period}: не начато")
            
            print("-" * 80)
            print(f"ВСЕГО ПРОТЕСТИРОВАНО: {total_tested} комбинаций")
            print(f"Следующая проверка через {interval} секунд...")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\nМониторинг остановлен.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Мониторинг оптимизации в реальном времени")
    parser.add_argument("--interval", type=int, default=5, help="Интервал проверки в секундах (по умолчанию 5)")
    args = parser.parse_args()
    
    monitor_optimization(interval=args.interval)

