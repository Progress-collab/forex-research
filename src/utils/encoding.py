"""Утилита для настройки кодировки UTF-8 в Windows консоли."""
from __future__ import annotations

import sys
import os


def setup_utf8_encoding() -> None:
    """Настраивает UTF-8 кодировку для Windows консоли."""
    if sys.platform == "win32":
        # Устанавливаем UTF-8 для stdout и stderr
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        
        # Устанавливаем переменную окружения для Python
        os.environ["PYTHONIOENCODING"] = "utf-8"
        
        # Пытаемся установить кодировку консоли через chcp (если доступно)
        try:
            import subprocess
            subprocess.run(["chcp", "65001"], shell=True, capture_output=True, check=False)
        except Exception:
            pass  # Игнорируем ошибки, если chcp недоступен

