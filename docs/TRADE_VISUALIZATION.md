# Визуализация сделок

Скрипт `scripts/visualize_trades.py` позволяет визуализировать сделки на ценовом графике, включая точки входа/выхода, линии между ними, стоп-лоссы и тейк-профиты.

## Возможности

- ✅ Отображение точек входа и выхода сделок
- ✅ Линии между входом и выходом (толщина зависит от прибыли)
- ✅ Горизонтальные линии стоп-лоссов и тейк-профитов
- ✅ **Динамические стоп-лоссы (trailing stop)** - отображение изменения стоп-лосса во времени
- ✅ Цветовая индикация прибыльных (зеленый) и убыточных (красный) сделок
- ✅ Фильтрация сделок (только прибыльные или только убыточные)
- ✅ Поддержка всех стратегий проекта

## Использование

### Базовое использование

```bash
python scripts/visualize_trades.py --strategy momentum_breakout --instrument EURUSD --period m15
```

### Сохранение графика без показа

```bash
python scripts/visualize_trades.py --strategy momentum_breakout --instrument EURUSD --period m15 --no-show --output reports/trades.png
```

### Фильтрация сделок

```bash
# Только прибыльные сделки
python scripts/visualize_trades.py --strategy momentum_breakout --instrument EURUSD --period m15 --filter winning

# Только убыточные сделки
python scripts/visualize_trades.py --strategy momentum_breakout --instrument EURUSD --period m15 --filter losing
```

### Загрузка из файла результатов

Если у вас есть сохраненные результаты бэктеста в JSON формате:

```bash
python scripts/visualize_trades.py --trades-file results.json --instrument EURUSD --period m15
```

## Параметры

- `--strategy` - Название стратегии (обязательно, если не используется --trades-file)
  - Доступные: `momentum_breakout`, `carry_momentum`, `mean_reversion`, `combined_momentum`, `macd_trend`, `bollinger_reversion`
- `--instrument` - Инструмент (например, EURUSD)
- `--period` - Период данных (по умолчанию m15)
- `--output` - Путь для сохранения графика (PNG)
- `--filter` - Фильтр сделок: `winning` (только прибыльные) или `losing` (только убыточные)
- `--no-show` - Не показывать график, только сохранить
- `--trades-file` - Путь к JSON файлу с результатами бэктеста (альтернатива запуску бэктеста)

## Визуализация

### Элементы графика

1. **Ценовая линия** - черная линия, показывает движение цены
2. **Точка входа** - треугольник ▲ (LONG) или ▼ (SHORT)
3. **Точка выхода** - круг ● (прибыль) или × (убыток)
4. **Линия между входом и выходом** - соединяет точки входа и выхода, толщина зависит от размера прибыли/убытка
5. **Стоп-лосс** - красная пунктирная линия, может быть динамической (trailing stop)
6. **Тейк-профит** - зеленая пунктирная линия

### Динамические стоп-лоссы

Если в сделке использовался trailing stop, график показывает ступенчатую линию стоп-лосса, которая изменяется во времени. Каждое изменение стоп-лосса отображается как новая точка на линии.

## Примеры

### Визуализация всех сделок Momentum Breakout

```bash
python scripts/visualize_trades.py --strategy momentum_breakout --instrument EURUSD --period m15
```

### Визуализация только прибыльных сделок Carry Momentum

```bash
python scripts/visualize_trades.py --strategy carry_momentum --instrument GBPUSD --period h1 --filter winning --output reports/carry_winning.png --no-show
```

### Анализ убыточных сделок

```bash
python scripts/visualize_trades.py --strategy momentum_breakout --instrument EURUSD --period m15 --filter losing --output reports/losing_trades.png
```

## Технические детали

### Структура данных

Скрипт использует структуру `Trade` из `src.backtesting.full_backtest`, которая включает:
- Базовую информацию о сделке (вход, выход, цена, направление)
- Историю изменений стоп-лоссов и тейк-профитов (`stop_take_history`)
- Причину выхода (`exit_reason`)

### История стоп-лоссов

Каждая запись в `stop_take_history` содержит:
- `timestamp` - время изменения
- `stop_loss` - значение стоп-лосса
- `take_profit` - значение тейк-профита
- `notional` - размер позиции на этот момент
- `reason` - причина изменения (entry, trailing_stop, partial_close, exit)

## Требования

- `matplotlib` - для построения графиков
- `pandas` - для работы с данными
- Данные должны быть загружены в `data/v1/curated/ctrader/`

## Примечания

- График автоматически определяет диапазон времени на основе сделок
- Если сделок много, график может быть перегружен - используйте фильтры
- Для лучшей визуализации рекомендуется использовать период не более нескольких дней сделок

