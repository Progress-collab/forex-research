# Исправление кодировки UTF-8 для Windows консоли

## Проблема

В Windows консоли русские буквы отображались как кракозябры (например, "����������" вместо "результаты"). Особенно это проявлялось в однострочных командах типа `python -c "..."`.

## Решение

Создан модуль `src/utils/encoding.py` с функцией `setup_utf8_encoding()`, которая использует несколько методов для максимальной совместимости:

1. **`reconfigure()` для Python 3.7+** - настраивает UTF-8 для stdout, stderr и stdin
2. **`io.TextIOWrapper` как fallback** - для старых версий Python или когда `reconfigure()` недоступен
3. **Установка переменной окружения** - `PYTHONIOENCODING=utf-8` для всех процессов Python
4. **Установка кодировки консоли** - через `chcp 65001` с проверкой результата

### Автоматическая настройка

Кодировка автоматически настраивается при импорте модулей из `src.utils`:

```python
from src.utils import ...  # Кодировка уже настроена автоматически!
```

Это работает даже в однострочных командах:
```bash
python -c "from src.utils import ...; print('Привет, мир!')"
```

### Настройка PowerShell профиля

Для постоянной поддержки UTF-8 во всех сессиях PowerShell рекомендуется запустить скрипт настройки:

```powershell
.\scripts\setup_powershell_encoding.ps1
```

Скрипт добавит в ваш PowerShell профиль:
- `chcp 65001` - установка UTF-8 кодировки консоли
- `$env:PYTHONIOENCODING = "utf-8"` - переменная окружения для Python

После этого UTF-8 будет автоматически настроен при каждом запуске PowerShell.

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

### Автоматическая настройка (рекомендуется)

При импорте модулей из `src.utils` кодировка настраивается автоматически:

```python
from src.utils import ...  # Кодировка уже настроена!
```

### Ручная настройка

Для скриптов, которые не импортируют из `src.utils`, можно явно вызвать функцию:

```python
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()
```

### Настройка терминала (опционально, но рекомендуется)

Запустите скрипт настройки PowerShell профиля один раз:

```powershell
.\scripts\setup_powershell_encoding.ps1
```

Это обеспечит постоянную поддержку UTF-8 во всех сессиях PowerShell.

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
