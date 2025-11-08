# Исправление кодировки UTF-8 для Windows консоли

## Проблема

В Windows консоли русские буквы отображались как кракозябры (например, "����������" вместо "результаты").

## Решение

Создан модуль `src/utils/encoding.py` с функцией `setup_utf8_encoding()`, которая:
1. Настраивает UTF-8 кодировку для stdout и stderr через `reconfigure()`
2. Устанавливает переменную окружения `PYTHONIOENCODING=utf-8`
3. Пытается установить кодировку консоли через `chcp 65001` (если доступно)

## Правило разработки

**ВАЖНО**: Все скрипты, которые выводят русский текст, должны использовать `setup_utf8_encoding()` в начале файла.

### Порядок импортов

```python
from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

# Остальные импорты...
import json
from pathlib import Path
```

### Обновленные скрипты

Все скрипты в `scripts/` и `research/` обновлены для использования настройки кодировки:

**scripts/**
- ✅ `optimize_strategy.py`
- ✅ `walk_forward_validation.py`
- ✅ `run_full_backtests.py`
- ✅ `download_data.py`
- ✅ `analyze_all_gaps.py`
- ✅ `analyze_losing_trades.py`
- ✅ `convert_raw_to_parquet.py`
- ✅ `backfill_ctrader_history.py`
- ✅ `backfill_year_data.py`
- ✅ `fetch_ctrader_trendbars.py`
- ✅ `analyze_backtest_results.py`
- ✅ `analyze_and_backfill_gaps.py`
- ✅ `update_symbol_info.py`
- ✅ `update_economic_calendar.py`
- ✅ `run_ingest.py`
- ✅ `test_pairs_trading.py`
- ✅ `backfill_xauusd_missing.py`
- ✅ `paper_dry_run.py`
- ✅ `compare_winning_losing_trades.py`
- ✅ `quick_test_strategies.py`

**research/**
- ✅ `backtests/run_baseline.py`
- ✅ `flows/ctrader_daily.py`
- ✅ `flows/daily_backtests.py`
- ✅ `tools/cli.py`

## Использование

Все скрипты автоматически настраивают кодировку при запуске. Никаких дополнительных действий не требуется.

## Работа с файлами

При работе с текстовыми файлами всегда указывайте `encoding="utf-8"`:

```python
# Правильно
with path.open("r", encoding="utf-8") as fp:
    data = json.load(fp)

path.write_text(content, encoding="utf-8")

# Неправильно
with path.open("r") as fp:  # Может использовать системную кодировку
    data = json.load(fp)
```

## Тестирование

Проверено на Windows 10/11 с PowerShell. Русские буквы теперь отображаются корректно во всех скриптах:
- ✅ "Тестируем", "сделок", "Отчет сохранен"
- ✅ "Деградация Sharpe", "Деградация Recovery"
- ✅ "Приемлемая деградация"
- ✅ "строк", "дней", "подозрительных разрывов"

## Пример использования

```python
from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Теперь русские буквы будут отображаться корректно
log.info("Привет, мир!")
log.info("Тестирование завершено")

# При работе с файлами всегда указывайте encoding
with Path("data.json").open("r", encoding="utf-8") as fp:
    data = json.load(fp)
```

## Дополнительные рекомендации

1. **Всегда используйте `encoding="utf-8"`** при работе с файлами
2. **Добавляйте `setup_utf8_encoding()`** в начало всех скриптов, которые выводят русский текст
3. **Используйте `logging`** вместо `print` для информационных сообщений
4. **Проверяйте вывод** в Windows консоли после изменений в скриптах
