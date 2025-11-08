# Forex Research Project

Инструменты данных и исследования алгоритмических форекс-стратегий.

## Быстрый старт (локально)

### Вариант 1: Автоматическая настройка
```bash
./scripts/setup_local.sh
```

### Вариант 2: Ручная настройка
```bash
# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows

# Установить зависимости
pip install --upgrade pip
pip install -e ".[backtesting]"
```

## Структура проекта

- `src/` - основной код проекта
  - `data_pipeline/` - сбор и обработка данных
  - `strategies/` - алгоритмические стратегии
  - `backtesting/` - бэктестинг
  - `execution/` - исполнение сделок
  - `risk/` - управление рисками
- `scripts/` - утилиты и скрипты
- `research/` - исследовательская среда
- `config/` - конфигурационные файлы
- `docs/` - документация

## Основные команды

### Сбор данных
```bash
python scripts/run_ingest.py
```

### Бэктестинг
```bash
python scripts/run_full_backtests.py
```

### Оптимизация стратегий
```bash
python scripts/optimize_strategy.py
```

### Анализ результатов
```bash
python scripts/analyze_backtest_results.py
```

## Документация

- [План итераций](docs/forex_system/iteration_plan.md)
- [Чек-лист запуска](docs/forex_system/launch_checklist.md)
- [План paper trading](docs/forex_system/paper_trading_plan.md)
- [Процесс разработки стратегий](docs/strategy_development_process.md)

## Требования

- Python >= 3.10
- pip

## Cloud Build

Проект настроен для автоматической сборки через GitHub Actions. 
Workflow запускается при push в main/master/develop ветки.

Для локального запуска используйте `./scripts/setup_local.sh`
