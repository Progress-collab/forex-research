# Стратегии на основе паттернов Patternz

## Обзор

Интеграция распознавания паттернов из Patternz (Thomas Bulkowski) в систему торговых стратегий.

## Структура модуля

### `src/patterns/`

Модуль распознавания паттернов:

- **`candlestick.py`** - Свечные паттерны:
  - `detect_hammer()` - Молот (разворот внизу тренда)
  - `detect_engulfing()` - Поглощение (бычье/медвежье)
  - `detect_doji()` - Доджи (неопределенность/разворот)

- **`chart.py`** - Графические паттерны:
  - `detect_double_top()` - Двойная вершина
  - `detect_double_bottom()` - Двойное дно

## Стратегии

### PatternReversalStrategy

Стратегия на основе свечных паттернов разворота:

- **Hammer** → сигнал на покупку (LONG)
- **Bullish Engulfing** → сигнал на покупку (LONG)
- **Bearish Engulfing** → сигнал на продажу (SHORT)

**Параметры:**
- `atr_multiplier`: 2.0 (множитель для стоп-лосса)
- `min_adx`: 15.0 (минимальная сила тренда для фильтрации)
- `risk_reward_ratio`: 2.0 (соотношение риск/прибыль)

### PatternBreakoutStrategy

Стратегия на основе графических паттернов:

- **Double Bottom** → пробой вверх (LONG)
- **Double Top** → пробой вниз (SHORT)

**Параметры:**
- `atr_multiplier`: 1.5
- `breakout_confirmation_bars`: 2 (количество баров для подтверждения пробоя)
- `risk_reward_ratio`: 2.5

## Использование

### Тестирование обнаружения паттернов

```python
from src.patterns import detect_hammer, detect_engulfing
from src.signals.data_access import CandleLoader
from src.data_pipeline.config import DataPipelineConfig

config = DataPipelineConfig()
loader = CandleLoader(config)
df = loader.load_recent("EURUSD", limit=500)
df = df.set_index("end")

# Обнаруживаем паттерны
hammer_idx = detect_hammer(df)
bullish_engulfing = detect_engulfing(df, bullish=True)
```

### Запуск стратегий

```python
from src.strategies import PatternReversalStrategy, PatternBreakoutStrategy
from src.backtesting.full_backtest import FullBacktestRunner

strategy = PatternReversalStrategy()
runner = FullBacktestRunner()
result = runner.run(strategy, "EURUSD", "m15")
```

### Полное тестирование

```bash
python scripts/test_pattern_strategies.py
```

## Логика обнаружения паттернов

### Hammer (Молот)

Условия из Patternz:
- Нисходящий тренд (цена ниже предыдущей)
- Верхняя тень <= 5% от высоты свечи
- Нижняя тень >= 2x высоты тела И <= 3x высоты тела
- Маленькое тело (меньше средней высоты тела за период)

### Engulfing (Поглощение)

**Bullish Engulfing:**
- Вчера: черная свеча (close < open)
- Сегодня: белая свеча (close > open)
- Сегодняшний open <= вчерашний close
- Сегодняшний close >= вчерашний open
- Хотя бы одно неравенство строгое

**Bearish Engulfing:**
- Вчера: белая свеча (close > open)
- Сегодня: черная свеча (close < open)
- Сегодняшний open >= вчерашний close
- Сегодняшний close <= вчерашний open
- Хотя бы одно неравенство строгое

### Double Top/Bottom

**Double Top:**
- Две вершины примерно на одном уровне (в пределах 1%)
- Между ними есть впадина минимум на 2% ниже вершин

**Double Bottom:**
- Два дна примерно на одном уровне (в пределах 1%)
- Между ними есть пик минимум на 2% выше дна

## Следующие шаги

1. ✅ Реализованы базовые свечные паттерны (Hammer, Engulfing, Doji)
2. ✅ Реализованы графические паттерны (Double Top/Bottom)
3. ✅ Созданы две стратегии на основе паттернов
4. ⏳ Тестирование на исторических данных
5. ⏳ Оптимизация параметров
6. ⏳ Добавление дополнительных паттернов:
   - Head & Shoulders
   - Гармонические паттерны (ABCD, Bat, Butterfly, Crab)
   - Дополнительные свечные паттерны (Morning Star, Evening Star, и т.д.)

## Источники

- Patternz Software: https://thepatternsite.com/PatternzNew.html
- Thomas Bulkowski's Encyclopedia of Chart Patterns

