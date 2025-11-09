"""Тестовый скрипт для отладки алгоритма Head & Shoulders"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import pandas as pd
from src.patterns.chart import (
    find_all_tops, find_all_bottoms, 
    find_hst, find_top_armpit,
    detect_all_head_shoulders_top
)

# Загружаем данные
df = pd.read_parquet('data/v1/curated/ctrader/EURUSD_m15.parquet')
df['utc_time'] = pd.to_datetime(df['utc_time'])
df = df.set_index('utc_time').sort_index()
sample = df.tail(500).reset_index(drop=True)

print(f"Размер выборки: {len(sample)}")
print(f"Диапазон цен: High={sample['high'].max():.5f}, Low={sample['low'].min():.5f}")
print(f"Разброс цен: {(sample['high'].max() - sample['low'].min()) / sample['low'].min() * 100:.2f}%")

# Находим пики и впадины
tops = find_all_tops(sample, trade_days=3)
bottoms = find_all_bottoms(sample, trade_days=2)

print(f"\nНайдено пиков: {len(tops)}")
print(f"Найдено впадин: {len(bottoms)}")

if len(tops) >= 3:
    print("\nПроверяем первые несколько пиков:")
    for i, top_idx in enumerate(tops[:10]):
        print(f"  Пик {i}: индекс={top_idx}, цена={sample.iloc[top_idx]['high']:.5f}")
    
    # Проверяем паттерн с головой на позиции 1
    i = 1
    head_idx = tops[i]
    head_price = sample.iloc[head_idx]['high']
    print(f"\nГолова: индекс={head_idx}, цена={head_price:.5f}")
    
    # Ищем левое плечо
    for j in range(i-1, max(-1, i-5), -1):
        ls_idx = tops[j]
        ls_price = sample.iloc[ls_idx]['high']
        print(f"\n  Левое плечо {j}: idx={ls_idx}, price={ls_price:.5f}")
        
        if ls_price > head_price:
            print(f"    Пропускаем - выше головы")
            break
        
        # Ищем правое плечо
        for k in range(i+1, min(i+5, len(tops))):
            rs_idx = tops[k]
            rs_price = sample.iloc[rs_idx]['high']
            print(f"    Правое плечо {k}: idx={rs_idx}, price={rs_price:.5f}")
            
            if rs_price > head_price:
                print(f"      Пропускаем - выше головы")
                break
            
            # Проверяем FindHST
            hst_result = find_hst(sample, ls_idx, rs_idx, head_idx, 0.15, False)
            print(f"      FindHST (15%): {hst_result} (True=невалиден, False=валиден)")
            
            # Проверяем с меньшим процентом
            hst_result_05 = find_hst(sample, ls_idx, rs_idx, head_idx, 0.05, False)
            print(f"      FindHST (5%): {hst_result_05}")
            
            # Проверяем neckline
            error_left, neckline_left = find_top_armpit(sample, ls_idx, head_idx, bottoms)
            error_right, neckline_right = find_top_armpit(sample, head_idx, rs_idx, bottoms)
            print(f"      Neckline left: error={error_left}, neckline={neckline_left}")
            print(f"      Neckline right: error={error_right}, neckline={neckline_right}")
            
            if not hst_result_05 and not error_left and not error_right:
                print(f"      ✓ ПАТТЕРН НАЙДЕН!")
                break

# Пробуем с меньшим процентом
print("\n" + "="*60)
print("Тест с head_shoulder_pct=0.05 (5%):")
patterns_05 = detect_all_head_shoulders_top(sample, lookback=500, strict_patterns=False, head_shoulder_pct=0.05)
print(f"Найдено паттернов: {len(patterns_05)}")

print("\nТест с head_shoulder_pct=0.01 (1%):")
patterns_01 = detect_all_head_shoulders_top(sample, lookback=500, strict_patterns=False, head_shoulder_pct=0.01)
print(f"Найдено паттернов: {len(patterns_01)}")

