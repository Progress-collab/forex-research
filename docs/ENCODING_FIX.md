# Исправление кодировки UTF-8 для Windows консоли

## Проблема
В Windows консоли русские буквы отображались как кракозябры (например, "����������" вместо "результаты").

## Решение
Создан модуль `src/utils/encoding.py` с функцией `setup_utf8_encoding()`, которая:
1. Настраивает UTF-8 кодировку для stdout и stderr через `reconfigure()`
2. Устанавливает переменную окружения `PYTHONIOENCODING=utf-8`
3. Пытается установить кодировку консоли через `chcp 65001` (если доступно)

## Обновленные скрипты
Все 18 скриптов в `scripts/` обновлены для использования настройки кодировки:

✅ `optimize_strategy.py`
✅ `walk_forward_validation.py`
✅ `run_full_backtests.py`
✅ `download_data.py`
✅ `analyze_all_gaps.py`
✅ `analyze_losing_trades.py`
✅ `convert_raw_to_parquet.py`
✅ `backfill_ctrader_history.py`
✅ `backfill_year_data.py`
✅ `fetch_ctrader_trendbars.py`
✅ `analyze_backtest_results.py`
✅ `analyze_and_backfill_gaps.py`
✅ `update_symbol_info.py`
✅ `update_economic_calendar.py`
✅ `run_ingest.py`
✅ `test_pairs_trading.py`
✅ `backfill_xauusd_missing.py`
✅ `paper_dry_run.py`

## Использование
Все скрипты автоматически настраивают кодировку при запуске. Никаких дополнительных действий не требуется.

## Тестирование
Проверено на Windows 10/11 с PowerShell. Русские буквы теперь отображаются корректно во всех скриптах:
- ✅ "Тестируем", "сделок", "Отчет сохранен"
- ✅ "Деградация Sharpe", "Деградация Recovery"
- ✅ "Приемлемая деградация"
- ✅ "строк", "дней", "подозрительных разрывов"

## Пример использования
```python
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

# Теперь русские буквы будут отображаться корректно
print("Привет, мир!")
logging.info("Тестирование завершено")
```
