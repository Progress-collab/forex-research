# Инструкция: Работа с данными для бэктестинга

## Текущая ситуация

Данные должны находиться в `data/v1/curated/ctrader/` в формате parquet файлов:
- `EURUSD_m15.parquet`
- `GBPUSD_m15.parquet`
- `XAUUSD_m15.parquet`
- и т.д.

## Варианты получения данных

### Вариант 1: Если данные есть локально

Если у вас есть данные локально, скопируйте их:

```bash
# Создать структуру папок (уже создана)
mkdir -p data/v1/curated/ctrader

# Скопировать данные из локальной папки
# Например, если данные в ~/forex-data/:
cp ~/forex-data/*.parquet data/v1/curated/ctrader/
```

### Вариант 2: Собрать данные через cTrader API

Требуется настроить переменные окружения в `.env`:
```
CTRADER_CLIENT_ID=...
CTRADER_CLIENT_SECRET=...
CTRADER_ACCESS_TOKEN=...
CTRADER_REFRESH_TOKEN=...
```

Затем собрать данные:
```bash
# Получить данные для EURUSD m15
python3 scripts/fetch_ctrader_trendbars.py --symbol EURUSD --period m15 --bars 10000

# Обработать и сохранить в curated формат
python3 scripts/backfill_ctrader_history.py --symbol EURUSD --period m15
```

### Вариант 3: Использовать данные MOEX

```bash
# Посмотреть доступные инструменты
python3 scripts/run_ingest.py --list

# Собрать данные
python3 scripts/run_ingest.py --secid USD000UTSTOM
```

## Проверка данных

После того как данные будут на месте, проверьте:

```bash
python3 scripts/check_and_test_momentum.py
```

Этот скрипт:
1. Проверит наличие данных
2. Запустит бэктест Momentum Breakout
3. Покажет результаты

## Запуск бэктеста

Когда данные будут готовы:

```bash
# Тест только Momentum Breakout
python3 scripts/run_full_backtests.py --strategies momentum_breakout

# Или все стратегии
python3 scripts/run_full_backtests.py
```
