"""Утилита для настройки кодировки UTF-8 в Windows консоли."""
from __future__ import annotations

import sys
import os
import io


def setup_utf8_encoding() -> None:
    """
    Настраивает UTF-8 кодировку для Windows консоли.
    
    Использует несколько методов для максимальной совместимости:
    1. reconfigure() для Python 3.7+
    2. io.TextIOWrapper как fallback
    3. Установка переменной окружения PYTHONIOENCODING
    4. Установка кодировки консоли через chcp 65001
    """
    if sys.platform == "win32":
        # Метод 1: Используем reconfigure() если доступно (Python 3.7+)
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
        
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
        
        if hasattr(sys.stdin, "reconfigure"):
            try:
                sys.stdin.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
        
        # Метод 2: Fallback через io.TextIOWrapper если reconfigure не сработал
        if not hasattr(sys.stdout, "reconfigure") or sys.stdout.encoding != "utf-8":
            try:
                if hasattr(sys.stdout, "buffer"):
                    sys.stdout = io.TextIOWrapper(
                        sys.stdout.buffer,
                        encoding="utf-8",
                        errors="replace",
                        line_buffering=True
                    )
            except (AttributeError, ValueError):
                pass
        
        if not hasattr(sys.stderr, "reconfigure") or (hasattr(sys.stderr, "encoding") and sys.stderr.encoding != "utf-8"):
            try:
                if hasattr(sys.stderr, "buffer"):
                    sys.stderr = io.TextIOWrapper(
                        sys.stderr.buffer,
                        encoding="utf-8",
                        errors="replace",
                        line_buffering=True
                    )
            except (AttributeError, ValueError):
                pass
        
        # Метод 3: Устанавливаем переменную окружения для Python
        os.environ["PYTHONIOENCODING"] = "utf-8"
        
        # Метод 4: Устанавливаем кодировку консоли через chcp (если доступно)
        try:
            import subprocess
            # Запускаем chcp 65001 и проверяем результат
            result = subprocess.run(
                ["chcp", "65001"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=2,
                check=False
            )
            # Проверяем, что команда выполнилась успешно
            if result.returncode == 0:
                # Дополнительно устанавливаем через os.system для надежности
                try:
                    os.system("chcp 65001 >nul 2>&1")
                except Exception:
                    pass
        except Exception:
            pass  # Игнорируем ошибки, если chcp недоступен

