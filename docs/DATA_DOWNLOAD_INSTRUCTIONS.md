# Инструкция по загрузке данных

## Вариант 1: Загрузка через cTrader API

1. Создайте файл `.env` в корне проекта (скопируйте `.env.example`)
2. Заполните учетные данные cTrader:
   - `CTRADER_CLIENT_ID` - ID клиента из cTrader Open API
   - `CTRADER_CLIENT_SECRET` - Секретный ключ
   - `CTRADER_ACCESS_TOKEN` - Токен доступа
   - `CTRADER_REFRESH_TOKEN` - Токен обновления (опционально)

3. Запустите загрузку данных:
```bash
python scripts/download_data.py --symbols EURUSD USDJPY GBPUSD --periods m15 --years 1
```

## Вариант 2: Копирование данных с MacBook

Если данные уже загружены на MacBook:

1. Скопируйте папку `data/v1/curated/ctrader/` с MacBook на Windows
2. Разместите файлы в `forex-research/data/v1/curated/ctrader/`
3. Ожидаемые файлы:
   - `EURUSD_m15.parquet`
   - `USDJPY_m15.parquet`
   - `GBPUSD_m15.parquet`

4. Проверьте данные:
```bash
python scripts/analyze_all_gaps.py --symbols EURUSD USDJPY GBPUSD --periods m15
```

## Требования к данным

- Минимум 12 месяцев истории для полноценного тестирования
- Период m15 (15-минутные свечи) - основной для стратегий
- Отсутствие критических разрывов (>72 часа, кроме выходных)

