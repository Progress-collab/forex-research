# Расширение пайплайна данных: анализ разрывов, справочная информация, pairs trading

## Реализованные компоненты

### 1. Анализ разрывов данных (`src/data_pipeline/gap_analysis.py`)

Утилиты для анализа разрывов в исторических данных и их классификации:

- `analyze_gaps()` - находит разрывы в данных
- `classify_gaps()` - классифицирует разрывы (выходные, подозрительные)
- `generate_backfill_requests()` - генерирует запросы для дозагрузки пропущенных данных
- `is_forex_weekend()` - проверяет, попадает ли разрыв на выходные forex

**Использование:**
```python
from src.data_pipeline.gap_analysis import analyze_gaps, classify_gaps

gaps = analyze_gaps(df, period_minutes=15)
classification = classify_gaps(gaps, "EURUSD")
```

### 2. Справочная информация о символах (`src/data_pipeline/symbol_info.py`)

Модуль для работы со справочной информацией о символах (swaps, комиссии, спреды):

- `SymbolInfo` - dataclass с информацией о символе
- `SymbolInfoCache` - кэш с возможностью сохранения/загрузки из JSON
- `extract_symbol_info()` - извлекает информацию из ProtoOASymbol

**Использование:**
```python
from src.data_pipeline.symbol_info import SymbolInfoCache

cache = SymbolInfoCache()
cache.load()  # Загрузить из файла
info = cache.get("EURUSD")
print(f"Swap Long: {info.swap_long}, Swap Short: {info.swap_short}")
```

### 3. Утилиты для pairs trading (`src/data_pipeline/pairs_utils.py`)

Функции для синхронизации данных и анализа пар:

- `load_pair_data()` - загружает и синхронизирует данные двух символов
- `compute_spread()` - вычисляет спред между двумя символами
- `compute_zscore()` - вычисляет z-score для временного ряда
- `find_pairs_candidates()` - находит потенциальные пары на основе корреляции

**Использование:**
```python
from src.data_pipeline.pairs_utils import load_pair_data, compute_spread, compute_zscore

df_pair = load_pair_data("EURUSD", "GBPUSD", "m15")
spread = compute_spread(df_pair, "EURUSD", "GBPUSD", method="ratio")
zscore = compute_zscore(spread, window=100)
```

## Скрипты

### 1. Обновление справочной информации о символах

```bash
python scripts/update_symbol_info.py --output data/v1/ref/symbols_info.json --environment live
```

Обновляет информацию о символах (swaps, комиссии, спреды) из cTrader API и сохраняет в JSON.

### 2. Анализ разрывов и дозагрузка

```bash
# Только анализ (dry-run)
python scripts/analyze_and_backfill_gaps.py --symbol EURUSD --period m15 --dry-run

# Анализ и дозагрузка
python scripts/analyze_and_backfill_gaps.py --symbol EURUSD --period m15 --chunk-size 200
```

Анализирует разрывы в данных и автоматически дозагружает пропущенные данные.

### 3. Массовая загрузка данных за год

```bash
python scripts/backfill_year_data.py \
  --symbols EURUSD GBPUSD USDJPY XAUUSD \
  --periods m1 m5 m15 h1 \
  --years 1 \
  --chunk-size 200
```

Загружает исторические данные за указанный период по всем указанным символам и таймфреймам.

## Интеграция с существующим кодом

### CTraderTrendbarFetcher

Расширен для автоматического сохранения информации о символах:
- При получении списка символов информация автоматически сохраняется в `SymbolInfoCache`
- При закрытии соединения кэш автоматически сохраняется в файл

### Структура данных

Новые файлы:
- `data/v1/ref/symbols_info.json` - справочная информация о символах
- `data/v1/curated/ctrader/{SYMBOL}_{PERIOD}.parquet` - обновлённые curated данные

## Источники экономического календаря

Документация по источникам экономического календаря находится в `docs/data_sources/economic_calendar_sources.md`.

Рекомендации:
- **MVP**: TradingEconomics API (бесплатный тариф до 500 запросов/месяц)
- **Production**: Комбинированный подход (TradingEconomics + парсинг ForexFactory как резерв)

## Следующие шаги

1. Запустить загрузку данных за год:
   ```bash
   python scripts/backfill_year_data.py --years 1
   ```

2. Обновить справочную информацию:
   ```bash
   python scripts/update_symbol_info.py
   ```

3. Проанализировать разрывы и дозагрузить пропуски:
   ```bash
   python scripts/analyze_and_backfill_gaps.py --symbol EURUSD --period m15
   ```

4. Интегрировать источник экономического календаря (TradingEconomics API)

5. Протестировать pairs trading на синхронизированных данных

