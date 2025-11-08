# Инструкция: Копирование данных из локальной папки

## Вариант 1: Через терминал (рекомендуется)

Выполните в терминале на вашем Mac:

```bash
# Перейти в директорию проекта
cd /workspace

# Скопировать данные
cp -r "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data"/* data/

# Или если нужно скопировать только curated данные:
mkdir -p data/v1/curated/ctrader
cp "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"/*.parquet data/v1/curated/ctrader/
```

## Вариант 2: Через Cursor (если есть доступ к файловой системе)

1. Откройте файловый менеджер в Cursor
2. Найдите папку `/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data`
3. Скопируйте содержимое в `/workspace/data`

## Вариант 3: Проверка структуры данных

Сначала проверьте структуру ваших данных:

```bash
ls -la "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data"
ls -la "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"
```

Должны быть файлы типа:
- `EURUSD_m15.parquet`
- `GBPUSD_m15.parquet`
- `XAUUSD_m15.parquet`
- и т.д.

## После копирования

Проверьте что данные скопированы:

```bash
python3 scripts/check_and_test_momentum.py
```

Этот скрипт проверит наличие данных и запустит тест Momentum Breakout стратегии.
