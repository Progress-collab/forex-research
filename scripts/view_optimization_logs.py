"""Скрипт для просмотра логов оптимизации."""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

def tail_log(log_file: Path = Path("research/logs/optimization.log"), lines: int = 50):
    """Показывает последние строки лог-файла."""
    if not log_file.exists():
        print(f"Лог-файл не найден: {log_file}")
        print("Запустите оптимизацию, чтобы создать лог-файл.")
        return
    
    try:
        with log_file.open("r", encoding="utf-8") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            print("".join(last_lines))
    except Exception as e:
        print(f"Ошибка при чтении лог-файла: {e}")

def watch_log(log_file: Path = Path("research/logs/optimization.log")):
    """Следит за лог-файлом в реальном времени (tail -f)."""
    import time
    
    if not log_file.exists():
        print(f"Лог-файл не найден: {log_file}")
        print("Ожидание создания лог-файла...")
        while not log_file.exists():
            time.sleep(1)
    
    print(f"Мониторинг лог-файла: {log_file}")
    print("Нажмите Ctrl+C для остановки")
    print("=" * 80)
    
    try:
        with log_file.open("r", encoding="utf-8") as f:
            # Переходим в конец файла
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\nМониторинг остановлен.")
    except Exception as e:
        print(f"\nОшибка: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Просмотр логов оптимизации")
    parser.add_argument("--watch", "-w", action="store_true", help="Следить за логом в реальном времени (tail -f)")
    parser.add_argument("--lines", "-n", type=int, default=50, help="Количество последних строк для показа (по умолчанию 50)")
    parser.add_argument("--file", "-f", type=str, help="Путь к лог-файлу (по умолчанию research/logs/optimization.log)")
    args = parser.parse_args()
    
    log_file = Path(args.file) if args.file else Path("research/logs/optimization.log")
    
    if args.watch:
        watch_log(log_file)
    else:
        tail_log(log_file, args.lines)

