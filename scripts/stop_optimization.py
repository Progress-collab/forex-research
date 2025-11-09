"""Скрипт для остановки всех процессов оптимизации Python."""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import subprocess

def stop_optimization_processes():
    """Останавливает все процессы Python, связанные с оптимизацией."""
    try:
        # В Windows используем taskkill
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq *optimize*"],
            capture_output=True,
            text=True
        )
        print("Попытка остановить процессы оптимизации...")
        sys.stdout.flush()
        print(result.stdout)
        sys.stdout.flush()
        if result.stderr:
            print("Ошибки:", result.stderr)
            sys.stdout.flush()
    except Exception as e:
        print(f"Ошибка при остановке процессов: {e}")
        sys.stdout.flush()
        print("\nАльтернативный способ:")
        sys.stdout.flush()
        print("Откройте PowerShell и выполните:")
        sys.stdout.flush()
        print("Get-Process python* | Stop-Process -Force")
        sys.stdout.flush()

if __name__ == "__main__":
    stop_optimization_processes()

