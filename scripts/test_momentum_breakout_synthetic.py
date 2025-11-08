#!/usr/bin/env python3
"""
Тест исправленной стратегии Momentum Breakout на синтетических данных
Проверяет что стратегия генерирует сигналы при пробитиях
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.momentum_breakout import MomentumBreakoutStrategy

def create_test_data_with_breakout():
    """Создает тестовые данные с пробитием максимума"""
    # Создаем базовую цену
    dates = pd.date_range('2024-01-01 00:00:00', periods=200, freq='15min')
    base_price = 1.1000
    
    # Первые 150 баров - консолидация (цена в диапазоне)
    consolidation_high = base_price + 0.0010
    consolidation_low = base_price - 0.0010
    
    prices = []
    for i in range(150):
        # Случайные колебания в диапазоне
        close = base_price + np.random.uniform(-0.0005, 0.0005)
        high = close + np.random.uniform(0, 0.0003)
        low = close - np.random.uniform(0, 0.0003)
        prices.append({
            'timestamp': dates[i],
            'open': close,
            'high': min(high, consolidation_high),
            'low': max(low, consolidation_low),
            'close': close,
            'instrument': 'EURUSD',
            'volume': 1000
        })
    
    # Последние 50 баров - пробитие вверх
    breakout_level = consolidation_high
    for i in range(150, 200):
        # Цена пробивает максимум
        close = breakout_level + 0.0005 + (i - 150) * 0.0001
        high = close + np.random.uniform(0, 0.0002)
        low = close - np.random.uniform(0, 0.0002)
        prices.append({
            'timestamp': dates[i],
            'open': close - 0.0001,
            'high': high,  # Пробивает уровень!
            'low': low,
            'close': close,
            'instrument': 'EURUSD',
            'volume': 1500
        })
    
    df = pd.DataFrame(prices)
    return df

def main():
    print("="*60)
    print("🧪 Тест исправленной Momentum Breakout стратегии")
    print("="*60)
    
    # Создаем стратегию
    strategy = MomentumBreakoutStrategy()
    print(f"\n📊 Параметры стратегии:")
    print(f"   - Lookback hours: {strategy.lookback_hours}")
    print(f"   - ADX threshold: {strategy.adx_threshold}")
    print(f"   - Min ATR: {strategy.min_atr}")
    print(f"   - Check window: 5 баров")
    
    # Создаем тестовые данные с пробитием
    print(f"\n📈 Создание тестовых данных с пробитием...")
    test_df = create_test_data_with_breakout()
    
    # Показываем статистику данных
    prev_period = test_df.iloc[-70:-5]
    current_period = test_df.iloc[-5:]
    high_break = prev_period["high"].max()
    low_break = prev_period["low"].min()
    
    print(f"   - Всего баров: {len(test_df)}")
    print(f"   - Предыдущий период: {len(prev_period)} баров")
    print(f"   - Текущий период: {len(current_period)} баров")
    print(f"   - Уровень пробития вверх: {high_break:.5f}")
    print(f"   - Уровень пробития вниз: {low_break:.5f}")
    print(f"   - Максимум текущего периода: {current_period['high'].max():.5f}")
    print(f"   - Минимум текущего периода: {current_period['low'].min():.5f}")
    
    # Генерируем сигналы
    print(f"\n🔍 Генерация сигналов...")
    signals = strategy.generate_signals(test_df)
    
    print(f"\n✅ Результаты:")
    print(f"   - Сгенерировано сигналов: {len(signals)}")
    
    if signals:
        print(f"\n   📋 Детали сигналов:")
        for i, sig in enumerate(signals, 1):
            print(f"   {i}. {sig.direction} @ {sig.entry_price:.5f}")
            print(f"      Stop Loss: {sig.stop_loss:.5f}")
            print(f"      Take Profit: {sig.take_profit:.5f}")
            print(f"      Notional: {sig.notional:.2f}")
            print(f"      Confidence: {sig.confidence:.2f}")
        
        print(f"\n🎉 УСПЕХ! Стратегия работает и генерирует сигналы!")
        return 0
    else:
        print(f"\n⚠️  Стратегия не сгенерировала сигналы")
        print(f"   Возможные причины:")
        print(f"   - Фильтры слишком строгие (ADX, ATR)")
        print(f"   - Нужно больше данных для расчета индикаторов")
        return 1

if __name__ == "__main__":
    sys.exit(main())
