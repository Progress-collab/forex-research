# Forex Research Project

Инструменты данных и исследования алгоритмических форекс-стратегий.

## Описание проекта

Проект предназначен для разработки, тестирования и оптимизации алгоритмических торговых стратегий на форекс-рынке. Включает в себя:

- **Конвейер данных**: Загрузка и подготовка исторических данных из cTrader API
- **Бэктестинг**: Полное тестирование стратегий на исторических данных
- **Оптимизация**: Поиск оптимальных параметров стратегий
- **Валидация**: Walk-forward валидация для проверки стабильности стратегий
- **Мониторинг**: Отслеживание производительности стратегий

## Структура проекта

```
forex-research/
├── src/                    # Исходный код проекта
│   ├── backtesting/        # Модули бэктестинга
│   ├── data_pipeline/      # Конвейер данных
│   ├── execution/          # Исполнение стратегий
│   ├── risk/               # Управление рисками
│   ├── signals/            # Генерация сигналов и индикаторы
│   ├── strategies/         # Реализации стратегий
│   └── utils/              # Утилиты (включая настройку кодировки)
├── scripts/                # Исполняемые скрипты
├── research/               # Исследовательская среда
│   ├── configs/           # Конфигурации экспериментов
│   ├── flows/             # Prefect flows
│   ├── templates/         # Шаблоны для экспериментов
│   └── tools/             # CLI инструменты
├── data/                   # Данные (raw, curated, reports)
├── docs/                   # Документация
├── config/                 # Конфигурации стратегий
└── monitoring/             # Конфигурации мониторинга
```

## Быстрый старт

### Установка зависимостей

```bash
python -m venv .venv
source .venv/bin/activate  # На Windows: .venv\Scripts\activate
pip install -e ".[backtesting]"
```

### Настройка окружения

Создайте файл `.env` в корне проекта:

```env
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_ACCESS_TOKEN=your_access_token
CTRADER_REFRESH_TOKEN=your_refresh_token
```

### Загрузка данных

```bash
python scripts/download_data.py --symbols EURUSD GBPUSD USDJPY --periods m15 --years 1
```

### Запуск бэктеста

```bash
python scripts/run_full_backtests.py
```

## Правила разработки

### Кодировка UTF-8

**ВАЖНО**: Проект автоматически настраивает UTF-8 кодировку при импорте модулей из `src.utils`. Это обеспечивает корректное отображение русского текста в Windows консоли, включая однострочные команды типа `python -c "from src.utils import ..."`.

#### Автоматическая настройка

При импорте любого модуля из `src.utils` кодировка UTF-8 настраивается автоматически:

```python
from src.utils import ...  # Кодировка уже настроена!
```

#### Ручная настройка (для скриптов)

Для скриптов, которые не импортируют из `src.utils`, можно явно вызвать функцию:

```python
from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

# Остальные импорты...
```

#### Настройка PowerShell профиля (рекомендуется)

Для постоянной поддержки UTF-8 во всех сессиях PowerShell запустите один раз:

```powershell
.\scripts\setup_powershell_encoding.ps1
```

Это добавит в ваш PowerShell профиль автоматическую настройку UTF-8 при каждом запуске терминала.

#### Что делает настройка

Функция `setup_utf8_encoding()` использует несколько методов для максимальной совместимости:
1. `reconfigure()` для Python 3.7+ (stdout, stderr, stdin)
2. `io.TextIOWrapper` как fallback для старых версий Python
3. Установка переменной окружения `PYTHONIOENCODING=utf-8`
4. Установка кодировки консоли через `chcp 65001`

Это правило применяется ко всем скриптам в `scripts/` и `research/`, которые могут выводить русский текст.

### Работа с файлами

Всегда указывайте `encoding="utf-8"` при открытии текстовых файлов:

```python
# Правильно
with path.open("r", encoding="utf-8") as fp:
    data = json.load(fp)

# Правильно
path.write_text(content, encoding="utf-8")

# Неправильно
with path.open("r") as fp:  # Может использовать системную кодировку
    data = json.load(fp)
```

### Импорты

Порядок импортов:
1. Стандартная библиотека Python
2. Сторонние библиотеки
3. Локальные модули проекта

После импортов стандартной библиотеки и перед сторонними библиотеками добавляйте настройку кодировки (если скрипт выводит русский текст).

### Стиль кода

- Используйте type hints для всех функций
- Добавляйте docstrings для публичных функций и классов
- Используйте `Path` из `pathlib` вместо строковых путей
- Используйте `logging` вместо `print` для информационных сообщений

### Обработка ошибок

Всегда используйте try-except блоки с логированием:

```python
import logging

log = logging.getLogger(__name__)

try:
    # Код, который может вызвать ошибку
    result = risky_operation()
except Exception as e:
    log.error("Ошибка при выполнении операции: %s", e, exc_info=True)
    raise
```

### Логирование

Используйте модуль `logging` вместо `print`:

```python
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

log.info("Начало обработки данных")
log.error("Ошибка: %s", error_message)
```

## Основные компоненты

### Стратегии

Стратегии находятся в `src/strategies/`:
- `momentum_breakout.py` - Momentum Breakout стратегия
- `carry_momentum.py` - Carry Momentum стратегия
- `mean_reversion.py` - Mean Reversion стратегия
- И другие...

### Бэктестинг

Модули бэктестинга в `src/backtesting/`:
- `full_backtest.py` - Полный бэктест с учетом комиссий и свопов
- `optimization.py` - Оптимизация параметров стратегий
- `walk_forward.py` - Walk-forward валидация

### Конвейер данных

Модули конвейера данных в `src/data_pipeline/`:
- `ctrader_client.py` - Клиент для работы с cTrader API
- `curation.py` - Подготовка и валидация данных
- `storage.py` - Хранение данных

## Документация

Подробная документация находится в директории `docs/`:
- `data_pipeline_overview.md` - Обзор конвейера данных
- `strategy_development_process.md` - Процесс разработки стратегий
- `ENCODING_FIX.md` - Исправление кодировки UTF-8
- И другие документы...

## Лицензия

Проект разработан для внутреннего использования.

