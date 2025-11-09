"""Скрипт для проверки, действительно ли оптимизация работает или зависла."""
import sys
import time
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

def check_if_optimization_is_running():
    """Проверяет, работает ли оптимизация или зависла."""
    import psutil
    
    print("=" * 80)
    sys.stdout.flush()
    print("ПРОВЕРКА СТАТУСА ОПТИМИЗАЦИИ")
    sys.stdout.flush()
    print("=" * 80)
    sys.stdout.flush()
    
    python_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'create_time']):
        try:
            if 'python' in proc.info['name'].lower():
                python_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not python_processes:
        print("Процессы Python не найдены.")
        sys.stdout.flush()
        return
    
    print(f"\nНайдено процессов Python: {len(python_processes)}")
    sys.stdout.flush()
    print("-" * 80)
    sys.stdout.flush()
    
    active_count = 0
    for proc in python_processes:
        try:
            cpu_percent = proc.cpu_percent(interval=1)
            memory_mb = proc.memory_info().rss / 1024 / 1024
            runtime = time.time() - proc.create_time()
            
            status = "РАБОТАЕТ" if cpu_percent > 1.0 else "ВОЗМОЖНО ЗАВИС"
            
            print(f"PID {proc.pid}: CPU={cpu_percent:.1f}%, RAM={memory_mb:.1f}MB, Runtime={runtime/60:.1f}мин - {status}")
            sys.stdout.flush()
            
            if cpu_percent > 1.0:
                active_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    print("-" * 80)
    sys.stdout.flush()
    print(f"Активных процессов: {active_count} из {len(python_processes)}")
    sys.stdout.flush()
    
    # Проверяем файлы результатов
    config_dir = Path("research/configs/optimized")
    files = list(config_dir.glob("carry_momentum_*_all_results.json"))
    
    if files:
        print("\nФайлы результатов:")
        sys.stdout.flush()
        for f in files:
            mtime = f.stat().st_mtime
            age_minutes = (time.time() - mtime) / 60
            print(f"  {f.name}: обновлен {age_minutes:.1f} минут назад")
            sys.stdout.flush()
    
    print("\n" + "=" * 80)
    sys.stdout.flush()
    print("ВЫВОД:")
    sys.stdout.flush()
    if active_count > 0:
        print("✓ Оптимизация РАБОТАЕТ (процессы потребляют CPU)")
        sys.stdout.flush()
        print("  Результаты сохраняются только после завершения каждого этапа.")
        sys.stdout.flush()
        print("  Это нормально - подождите завершения.")
        sys.stdout.flush()
    else:
        print("⚠ Процессы НЕ потребляют CPU - возможно зависли")
        sys.stdout.flush()
        print("  Рекомендуется остановить и перезапустить оптимизацию.")
        sys.stdout.flush()

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("Установите psutil: pip install psutil")
        sys.stdout.flush()
        sys.exit(1)
    
    check_if_optimization_is_running()

