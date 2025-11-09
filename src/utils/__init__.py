"""Утилиты для проекта forex-research."""

# Автоматически настраиваем UTF-8 кодировку при импорте модуля utils
# Это обеспечивает корректное отображение русского текста в Windows консоли
# даже при использовании однострочных команд типа python -c "from src.utils import ..."
from .encoding import setup_utf8_encoding

setup_utf8_encoding()

