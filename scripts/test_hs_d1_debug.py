"""Детальный тест алгоритма Head & Shoulders на D1 данных"""
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

# Загружаем D1 данные
df = pd.read_parquet('data/v1/curated/ctrader/EURUSD_d1.parquet')
df['utc_time'] = pd.to_datetime(df['utc_time'])
df = df.set_index('utc_time').sort_index()

print(f"Загружено D1 баров: {len(df)}")
print(f"Период: {df.index[0]} - {df.index[-1]}")
print(f"Разброс цен: {(df['high'].max() - df['low'].min()) / df['low'].min() * 100:.2f}%")

# Используем весь датасет
sample = df.reset_index(drop=True)

# Находим пики и впадины
tops = find_all_tops(sample, trade_days=3)
bottoms = find_all_bottoms(sample, trade_days=2)

print(f"\nНайдено пиков: {len(tops)}")
print(f"Найдено впадин: {len(bottoms)}")

if len(tops) >= 3:
    print("\nПервые 10 пиков:")
    for i, top_idx in enumerate(tops[:10]):
        print(f"  {i}: idx={top_idx}, price={sample.iloc[top_idx]['high']:.5f}")
    
    print("\nПроверяем паттерны:")
    checked = 0
    found_patterns = []
    
    for i in range(1, min(len(tops), 20)):  # Проверяем первые 20 голов
        head_idx = tops[i]
        head_price = sample.iloc[head_idx]['high']
        
        for j in range(i-1, max(-1, i-10), -1):  # Ищем левое плечо
            ls_idx = tops[j]
            ls_price = sample.iloc[ls_idx]['high']
            
            if ls_price > head_price:
                break
            
            for k in range(i+1, min(i+10, len(tops))):  # Ищем правое плечо
                rs_idx = tops[k]
                rs_price = sample.iloc[rs_idx]['high']
                
                if rs_price > head_price:
                    break
                
                checked += 1
                if checked > 50:  # Ограничиваем количество проверок
                    break
                
                # Проверяем что между плечами нет пиков выше головы
                has_higher = False
                for l in range(j+1, k):
                    if l != i and sample.iloc[tops[l]]['high'] > head_price:
                        has_higher = True
                        break
                
                if has_higher:
                    continue
                
                # Проверяем FindHST с разными процентами
                for pct in [0.15, 0.10, 0.05, 0.02]:
                    hst_result = find_hst(sample, ls_idx, rs_idx, head_idx, pct, False)
                    if not hst_result:  # Паттерн валиден
                        # Проверяем neckline
                        error_left, neckline_left = find_top_armpit(sample, ls_idx, head_idx, bottoms)
                        error_right, neckline_right = find_top_armpit(sample, head_idx, rs_idx, bottoms)
                        
                        if not error_left and not error_right:
                            neckline = min(neckline_left, neckline_right)
                            head_advantage = (head_price - (ls_price + rs_price)/2) / ((ls_price + rs_price)/2)
                            print(f"\n✓ ПАТТЕРН НАЙДЕН!")
                            print(f"  Голова: idx={head_idx}, price={head_price:.5f}")
                            print(f"  Левое плечо: idx={ls_idx}, price={ls_price:.5f}")
                            print(f"  Правое плечо: idx={rs_idx}, price={rs_price:.5f}")
                            print(f"  Преимущество головы: {head_advantage*100:.2f}%")
                            print(f"  Процент для FindHST: {pct*100:.1f}%")
                            print(f"  Neckline: {neckline:.5f}")
                            found_patterns.append((head_idx, ls_idx, rs_idx, neckline))
                            break
                
                if checked > 50:
                    break
            if checked > 50:
                break
        if checked > 50:
            break
    
    print(f"\nВсего проверено комбинаций: {checked}")
    print(f"Найдено паттернов: {len(found_patterns)}")

# Тест через detect_all_head_shoulders_top
print("\n" + "="*60)
print("Тест через detect_all_head_shoulders_top:")
for pct in [0.15, 0.10, 0.05, 0.02]:
    patterns = detect_all_head_shoulders_top(sample, lookback=len(sample), strict_patterns=False, head_shoulder_pct=pct)
    print(f"  head_shoulder_pct={pct*100:.1f}%: найдено {len(patterns)} паттернов")

