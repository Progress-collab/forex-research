"""Скрипт для остановки всех процессов оптимизации Python."""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

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
        print(result.stdout)
        if result.stderr:
            print("Ошибки:", result.stderr)
    except Exception as e:
        print(f"Ошибка при остановке процессов: {e}")
        print("\nАльтернативный способ:")
        print("Откройте PowerShell и выполните:")
        print("Get-Process python* | Stop-Process -Force")

if __name__ == "__main__":
    stop_optimization_processes()

