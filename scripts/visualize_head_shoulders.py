"""
Визуализация паттерна Head & Shoulders на графике EURUSD m15.
"""
from __future__ import annotations

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
from matplotlib.patches import Rectangle

from src.patterns.chart import detect_head_shoulders_top, detect_head_shoulders_bottom


def visualize_head_shoulders(instrument: str = "EURUSD", period: str = "m15", 
                             window_size: int = 400):
    """
    Визуализирует паттерны Head & Shoulders на графике.
    
    Args:
        instrument: Инструмент (EURUSD, GBPUSD, etc.)
        period: Таймфрейм (m15, h1, etc.)
        window_size: Размер окна для поиска паттернов
    """
    # Загружаем данные
    curated_dir = Path("data/v1/curated/ctrader")
    data_path = curated_dir / f"{instrument}_{period}.parquet"
    
    if not data_path.exists():
        print(f"Данные не найдены: {data_path}")
        sys.stdout.flush()
        return
    
    df = pd.read_parquet(data_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.set_index("utc_time").sort_index()
    
    print(f"Всего баров в данных: {len(df)}")
    sys.stdout.flush()
    
    # Ищем паттерны на разных участках данных
    hst = None
    hsb = None
    found_window = None
    
    # Пробуем разные участки данных
    for start_idx in range(0, len(df) - window_size, window_size // 2):
        window_df = df.iloc[start_idx:start_idx + window_size]
        
        # Пробуем разные параметры
        for lookback in [150, 200]:
            for tolerance in [0.02, 0.03, 0.05]:
                hst_test = detect_head_shoulders_top(window_df, lookback=lookback, shoulder_tolerance=tolerance)
                hsb_test = detect_head_shoulders_bottom(window_df, lookback=lookback, shoulder_tolerance=tolerance)
                
                if hst_test or hsb_test:
                    hst = hst_test
                    hsb = hsb_test
                    found_window = window_df
                    print(f"\n✓ Паттерны найдены на участке: {window_df.index[0]} - {window_df.index[-1]}")
                    sys.stdout.flush()
                    print(f"  Параметры: lookback={lookback}, tolerance={tolerance}")
                    sys.stdout.flush()
                    break
            
            if hst or hsb:
                break
        
        if hst or hsb:
            break
    
    if not hst and not hsb:
        print("\n⚠ Паттерны не найдены. Показываю последние данные...")
        sys.stdout.flush()
        found_window = df.tail(window_size)
        hst = detect_head_shoulders_top(found_window, lookback=150, shoulder_tolerance=0.05)
        hsb = detect_head_shoulders_bottom(found_window, lookback=150, shoulder_tolerance=0.05)
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(18, 10))
    
    # Рисуем свечи более качественно
    for idx, row in found_window.iterrows():
        color = 'green' if row['close'] >= row['open'] else 'red'
        # Тени
        ax.plot([idx, idx], [row['low'], row['high']], color='black', linewidth=0.5, alpha=0.3)
        # Тело свечи
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['open'], row['close'])
        rect = Rectangle((mdates.date2num(idx) - 0.0002, body_bottom), 
                        0.0004, body_height, 
                        facecolor=color, edgecolor='black', linewidth=0.5, alpha=0.8)
        ax.add_patch(rect)
    
    has_pattern = False
    
    # Рисуем Head & Shoulders Top
    if hst:
        left_idx, head_idx, right_idx = hst
        
        # Получаем цены
        left_price = found_window.loc[left_idx, 'high']
        head_price = found_window.loc[head_idx, 'high']
        right_price = found_window.loc[right_idx, 'high']
        
        # Вычисляем neckline
        between_left_head = found_window.loc[min(left_idx, head_idx):max(left_idx, head_idx)]
        between_head_right = found_window.loc[min(head_idx, right_idx):max(head_idx, right_idx)]
        neckline_left = between_left_head["low"].min()
        neckline_right = between_head_right["low"].min()
        neckline = max(neckline_left, neckline_right)
        
        # Рисуем структуру паттерна
        # Линия между плечами и головой
        ax.plot([left_idx, head_idx], [left_price, head_price], 
               'b-', linewidth=3, alpha=0.8, label='HST Structure')
        ax.plot([head_idx, right_idx], [head_price, right_price], 
               'b-', linewidth=3, alpha=0.8)
        
        # Neckline
        ax.plot([left_idx, right_idx], [neckline, neckline], 
               'r--', linewidth=3, alpha=0.9, label='Neckline (HST)')
        
        # Отмечаем точки
        ax.plot(left_idx, left_price, 'bo', markersize=12, label='Left Shoulder', zorder=5)
        ax.plot(head_idx, head_price, 'ro', markersize=15, label='Head', zorder=5)
        ax.plot(right_idx, right_price, 'bo', markersize=12, label='Right Shoulder', zorder=5)
        
        # Подписи
        ax.annotate('Left Shoulder', xy=(left_idx, left_price), 
                   xytext=(15, 15), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8, edgecolor='blue', linewidth=2),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=2),
                   fontsize=11, fontweight='bold')
        
        ax.annotate('HEAD', xy=(head_idx, head_price), 
                   xytext=(15, 15), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='red', alpha=0.8, edgecolor='darkred', linewidth=2),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=2),
                   fontsize=12, fontweight='bold')
        
        ax.annotate('Right Shoulder', xy=(right_idx, right_price), 
                   xytext=(15, 15), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.8, edgecolor='blue', linewidth=2),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=2),
                   fontsize=11, fontweight='bold')
        
        print(f"\nHead & Shoulders Top найден:")
        sys.stdout.flush()
        print(f"  Left Shoulder: {left_idx} - {left_price:.5f}")
        sys.stdout.flush()
        print(f"  Head: {head_idx} - {head_price:.5f}")
        sys.stdout.flush()
        print(f"  Right Shoulder: {right_idx} - {right_price:.5f}")
        sys.stdout.flush()
        print(f"  Neckline: {neckline:.5f}")
        sys.stdout.flush()
        has_pattern = True
    
    # Рисуем Head & Shoulders Bottom
    if hsb:
        left_idx, head_idx, right_idx = hsb
        
        # Получаем цены
        left_price = found_window.loc[left_idx, 'low']
        head_price = found_window.loc[head_idx, 'low']
        right_price = found_window.loc[right_idx, 'low']
        
        # Вычисляем neckline
        between_left_head = found_window.loc[min(left_idx, head_idx):max(left_idx, head_idx)]
        between_head_right = found_window.loc[min(head_idx, right_idx):max(head_idx, right_idx)]
        neckline_left = between_left_head["high"].max()
        neckline_right = between_head_right["high"].max()
        neckline = min(neckline_left, neckline_right)
        
        # Рисуем структуру паттерна
        # Линия между плечами и головой
        ax.plot([left_idx, head_idx], [left_price, head_price], 
               'g-', linewidth=3, alpha=0.8, label='HSB Structure')
        ax.plot([head_idx, right_idx], [head_price, right_price], 
               'g-', linewidth=3, alpha=0.8)
        
        # Neckline
        ax.plot([left_idx, right_idx], [neckline, neckline], 
               'orange', linestyle='--', linewidth=3, alpha=0.9, label='Neckline (HSB)')
        
        # Отмечаем точки
        ax.plot(left_idx, left_price, 'go', markersize=12, label='Left Shoulder (HSB)', zorder=5)
        ax.plot(head_idx, head_price, 'mo', markersize=15, label='Head (HSB)', zorder=5)
        ax.plot(right_idx, right_price, 'go', markersize=12, label='Right Shoulder (HSB)', zorder=5)
        
        # Подписи
        ax.annotate('Left Shoulder', xy=(left_idx, left_price), 
                   xytext=(15, -25), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8, edgecolor='green', linewidth=2),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=2),
                   fontsize=11, fontweight='bold')
        
        ax.annotate('HEAD', xy=(head_idx, head_price), 
                   xytext=(15, -25), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='magenta', alpha=0.8, edgecolor='darkmagenta', linewidth=2),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=2),
                   fontsize=12, fontweight='bold')
        
        ax.annotate('Right Shoulder', xy=(right_idx, right_price), 
                   xytext=(15, -25), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8, edgecolor='green', linewidth=2),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', lw=2),
                   fontsize=11, fontweight='bold')
        
        print(f"\nHead & Shoulders Bottom найден:")
        sys.stdout.flush()
        print(f"  Left Shoulder: {left_idx} - {left_price:.5f}")
        sys.stdout.flush()
        print(f"  Head: {head_idx} - {head_price:.5f}")
        sys.stdout.flush()
        print(f"  Right Shoulder: {right_idx} - {right_price:.5f}")
        sys.stdout.flush()
        print(f"  Neckline: {neckline:.5f}")
        sys.stdout.flush()
        has_pattern = True
    
    # Настройка графика
    title = f'{instrument} {period} - Head & Shoulders Patterns'
    if not has_pattern:
        title += ' (Patterns not found - showing recent data)'
    ax.set_title(title, fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Time', fontsize=14)
    ax.set_ylabel('Price', fontsize=14)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Легенда только если есть паттерны
    if has_pattern:
        ax.legend(loc='best', fontsize=11, framealpha=0.9)
    
    # Форматирование дат
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # Сохраняем график
    output_dir = Path("docs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"head_shoulders_{instrument}_{period}.png"
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    print(f"\n✓ График сохранен: {output_path}")
    sys.stdout.flush()
    
    plt.show()


if __name__ == "__main__":
    visualize_head_shoulders(instrument="EURUSD", period="m15", window_size=400)
