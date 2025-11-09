"""Визуализация Head & Shoulders паттернов на D1 данных с четкой маркировкой"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

from src.patterns.chart import detect_all_head_shoulders_top, detect_all_head_shoulders_bottom

# Загружаем D1 данные
df = pd.read_parquet('data/v1/curated/ctrader/EURUSD_d1.parquet')
df['utc_time'] = pd.to_datetime(df['utc_time'])
df = df.set_index('utc_time').sort_index()

print(f"Загружено D1 баров: {len(df)}")
print(f"Период: {df.index[0]} - {df.index[-1]}")

sample = df.reset_index(drop=True)
original_index = df.index

# Находим паттерны
patterns_hst = detect_all_head_shoulders_top(sample, lookback=len(sample), strict_patterns=False, head_shoulder_pct=0.15)
patterns_hsb = detect_all_head_shoulders_bottom(sample, lookback=len(sample), strict_patterns=False, head_shoulder_pct=0.15)

print(f"\nНайдено HST: {len(patterns_hst)}")
print(f"Найдено HSB: {len(patterns_hsb)}")

# Визуализируем
fig, ax = plt.subplots(figsize=(24, 12))

# Рисуем свечи (упрощенная версия для читаемости) - используем даты вместо индексов
for i in range(0, len(sample), max(1, len(sample) // 500)):  # Показываем каждую N-ю свечу
    row = sample.iloc[i]
    date = original_index[i]
    color = 'green' if row['close'] >= row['open'] else 'red'
    ax.plot([date, date], [row['low'], row['high']], color='gray', linewidth=0.3, alpha=0.5)
    body_height = abs(row['close'] - row['open'])
    if body_height > 0:
        ax.plot([date, date], [row['open'], row['close']], color=color, linewidth=1.5, alpha=0.6)

# Рисуем паттерны HST (Head & Shoulders Top - медвежий, вход SHORT)
hst_drawn = 0
for left_idx, head_idx, right_idx, neckline in patterns_hst:
    left_date = original_index[left_idx]
    head_date = original_index[head_idx]
    right_date = original_index[right_idx]
    left_price = sample.iloc[left_idx]['high']
    head_price = sample.iloc[head_idx]['high']
    right_price = sample.iloc[right_idx]['high']
    
    # Структура паттерна - синяя линия
    ax.plot([left_date, head_date, right_date], 
           [left_price, head_price, right_price], 
           color='blue', linewidth=3, marker='o', markersize=10, 
           label='HST (SHORT)' if hst_drawn == 0 else '', zorder=5)
    
    # Подписи: левое плечо, голова, правое плечо
    ax.annotate('Левое\nплечо', xy=(left_date, left_price), xytext=(left_date, left_price + 0.01),
               arrowprops=dict(arrowstyle='->', color='blue', lw=1.5),
               fontsize=9, color='blue', weight='bold', ha='center')
    ax.annotate('ГОЛОВА', xy=(head_date, head_price), xytext=(head_date, head_price + 0.015),
               arrowprops=dict(arrowstyle='->', color='blue', lw=2),
               fontsize=11, color='blue', weight='bold', ha='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    ax.annotate('Правое\nплечо', xy=(right_date, right_price), xytext=(right_date, right_price + 0.01),
               arrowprops=dict(arrowstyle='->', color='blue', lw=1.5),
               fontsize=9, color='blue', weight='bold', ha='center')
    
    # Neckline - красная пунктирная линия (уровень для входа SHORT)
    ax.plot([left_date, right_date], [neckline, neckline], 
           color='red', linestyle='--', linewidth=2.5, alpha=0.9,
           label='Neckline (SHORT)' if hst_drawn == 0 else '', zorder=4)
    
    # Стрелка направления входа (SHORT - вниз)
    entry_bar_idx = right_idx + 5  # Вход через несколько баров после правого плеча
    if entry_bar_idx < len(sample):
        entry_date = original_index[entry_bar_idx]
        entry_price = neckline - 0.005  # Немного ниже neckline
        ax.annotate('', xy=(entry_date, entry_price), xytext=(right_date, neckline),
                   arrowprops=dict(arrowstyle='->', color='red', lw=3, mutation_scale=20))
        # Используем timedelta для позиционирования текста
        from datetime import timedelta
        ax.text(entry_date + timedelta(days=2), entry_price - 0.005, 'ВХОД\nSHORT', 
               fontsize=10, color='red', weight='bold',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='red', alpha=0.3))
    
    hst_drawn += 1
    if hst_drawn >= 3:  # Показываем только первые 3 для читаемости
        break

# Рисуем паттерны HSB (Head & Shoulders Bottom - бычий, вход LONG)
hsb_drawn = 0
for left_idx, head_idx, right_idx, neckline in patterns_hsb:
    left_date = original_index[left_idx]
    head_date = original_index[head_idx]
    right_date = original_index[right_idx]
    left_price = sample.iloc[left_idx]['low']
    head_price = sample.iloc[head_idx]['low']
    right_price = sample.iloc[right_idx]['low']
    
    # Структура паттерна - зеленая линия
    ax.plot([left_date, head_date, right_date], 
           [left_price, head_price, right_price], 
           color='green', linewidth=3, marker='o', markersize=10,
           label='HSB (LONG)' if hsb_drawn == 0 else '', zorder=5)
    
    # Подписи: левое плечо, голова, правое плечо
    ax.annotate('Левое\nплечо', xy=(left_date, left_price), xytext=(left_date, left_price - 0.01),
               arrowprops=dict(arrowstyle='->', color='green', lw=1.5),
               fontsize=9, color='green', weight='bold', ha='center')
    ax.annotate('ГОЛОВА', xy=(head_date, head_price), xytext=(head_date, head_price - 0.015),
               arrowprops=dict(arrowstyle='->', color='green', lw=2),
               fontsize=11, color='green', weight='bold', ha='center',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    ax.annotate('Правое\nплечо', xy=(right_date, right_price), xytext=(right_date, right_price - 0.01),
               arrowprops=dict(arrowstyle='->', color='green', lw=1.5),
               fontsize=9, color='green', weight='bold', ha='center')
    
    # Neckline - оранжевая пунктирная линия (уровень для входа LONG)
    ax.plot([left_date, right_date], [neckline, neckline], 
           color='orange', linestyle='--', linewidth=2.5, alpha=0.9,
           label='Neckline (LONG)' if hsb_drawn == 0 else '', zorder=4)
    
    # Стрелка направления входа (LONG - вверх)
    entry_bar_idx = right_idx + 5  # Вход через несколько баров после правого плеча
    if entry_bar_idx < len(sample):
        entry_date = original_index[entry_bar_idx]
        entry_price = neckline + 0.005  # Немного выше neckline
        ax.annotate('', xy=(entry_date, entry_price), xytext=(right_date, neckline),
                   arrowprops=dict(arrowstyle='->', color='orange', lw=3, mutation_scale=20))
        # Используем timedelta для позиционирования текста
        from datetime import timedelta
        ax.text(entry_date + timedelta(days=2), entry_price + 0.005, 'ВХОД\nLONG', 
               fontsize=10, color='orange', weight='bold',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='orange', alpha=0.3))
    
    hsb_drawn += 1
    if hsb_drawn >= 3:  # Показываем только первые 3 для читаемости
        break

ax.set_title(f'EURUSD D1 - Head & Shoulders Patterns (Patternz Algorithm)\n'
            f'Найдено: {len(patterns_hst)} HST (SHORT), {len(patterns_hsb)} HSB (LONG)\n'
            f'Синие линии = HST (медвежий, вход SHORT при пробое neckline вниз)\n'
            f'Зеленые линии = HSB (бычий, вход LONG при пробое neckline вверх)', 
            fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel('Даты', fontsize=12)
ax.set_ylabel('Price (EURUSD)', fontsize=12)
ax.grid(True, alpha=0.3, linestyle=':')
ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

# Форматирование оси X для отображения дат
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
ax.xaxis.set_major_locator(mdates.AutoDateLocator())
plt.xticks(rotation=45, ha='right')

plt.tight_layout()
output_path = Path("docs") / "head_shoulders_EURUSD_d1_patternz.png"
output_path.parent.mkdir(exist_ok=True)
plt.savefig(output_path, dpi=200, bbox_inches='tight')
print(f"\n✓ График сохранен: {output_path}")
plt.show()

