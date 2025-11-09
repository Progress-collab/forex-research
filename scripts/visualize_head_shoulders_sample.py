"""
Скрипт для визуализации паттернов Head & Shoulders на небольшом участке данных.
Позволяет визуально оценить качество распознавания перед обработкой всего датасета.
"""
from __future__ import annotations

import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import List, Tuple

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.patterns.chart import detect_all_head_shoulders_top, detect_all_head_shoulders_bottom


def filter_best_patterns(hst_patterns: List, hsb_patterns: List, sample_df: pd.DataFrame, 
                         max_patterns: int = 20) -> Tuple[List, List]:
    """
    Фильтрует и оставляет только лучшие паттерны по качеству.
    
    Критерии качества:
    - Высота головы относительно плеч (больше = лучше)
    - Расстояние между плечами (оптимальное 50-150 баров)
    - Четкость neckline
    
    Args:
        hst_patterns: Список HST паттернов
        hsb_patterns: Список HSB паттернов
        sample_df: DataFrame с данными
        max_patterns: Максимальное количество паттернов каждого типа для визуализации
    
    Returns:
        Tuple[List[HST], List[HSB]] - отфильтрованные списки
    """
    def calculate_quality_score(pattern, is_top: bool, df: pd.DataFrame) -> float:
        """Вычисляет оценку качества паттерна (0-100)."""
        left_idx, head_idx, right_idx, neckline = pattern
        
        if is_top:
            left_price = df.loc[left_idx, 'high']
            head_price = df.loc[head_idx, 'high']
            right_price = df.loc[right_idx, 'high']
        else:
            left_price = df.loc[left_idx, 'low']
            head_price = df.loc[head_idx, 'low']
            right_price = df.loc[right_idx, 'low']
        
        avg_shoulder = (left_price + right_price) / 2
        
        # Расстояние между плечами в барах
        left_pos = df.index.get_loc(left_idx)
        right_pos = df.index.get_loc(right_idx)
        distance = right_pos - left_pos
        
        # Высота головы
        if is_top:
            head_advantage = (head_price - avg_shoulder) / avg_shoulder
        else:
            head_advantage = (avg_shoulder - head_price) / avg_shoulder
        
        # Оценка качества (0-100)
        score = 0.0
        
        # 1. Высота головы (макс 50 баллов)
        score += min(head_advantage * 5000, 50)  # 1% = 50 баллов
        
        # 2. Расстояние между плечами (макс 30 баллов)
        # Оптимальное расстояние: 60-120 баров
        if 60 <= distance <= 120:
            score += 30
        elif 50 <= distance < 60 or 120 < distance <= 150:
            score += 20
        elif 40 <= distance < 50 or 150 < distance <= 200:
            score += 10
        
        # 3. Четкость neckline (макс 20 баллов)
        if is_top:
            neckline_clearance = (head_price - neckline) / head_price
        else:
            neckline_clearance = (neckline - head_price) / head_price
        
        score += min(neckline_clearance * 2000, 20)  # 1% = 20 баллов
        
        return score
    
    # Вычисляем оценки для всех паттернов
    hst_scored = []
    for pattern in hst_patterns:
        score = calculate_quality_score(pattern, True, sample_df)
        hst_scored.append((score, pattern))
    
    hsb_scored = []
    for pattern in hsb_patterns:
        score = calculate_quality_score(pattern, False, sample_df)
        hsb_scored.append((score, pattern))
    
    # Сортируем по убыванию оценки и берем лучшие
    hst_scored.sort(reverse=True, key=lambda x: x[0])
    hsb_scored.sort(reverse=True, key=lambda x: x[0])
    
    # Фильтруем дубликаты по времени и цене (если паттерны слишком близко, берем только лучший)
    def filter_by_time_and_price(scored_patterns, min_distance_bars=100, is_top: bool = True):
        filtered = []
        for score, pattern in scored_patterns:
            left_idx, head_idx, right_idx, neckline = pattern
            is_too_close = False
            
            # Получаем позиции и цены текущего паттерна
            left_pos = sample_df.index.get_loc(left_idx)
            head_pos = sample_df.index.get_loc(head_idx)
            right_pos = sample_df.index.get_loc(right_idx)
            
            if is_top:
                head_price = sample_df.loc[head_idx, 'high']
            else:
                head_price = sample_df.loc[head_idx, 'low']
            
            for _, existing_pattern in filtered:
                existing_left, existing_head, existing_right, _ = existing_pattern
                existing_head_pos = sample_df.index.get_loc(existing_head)
                
                if is_top:
                    existing_head_price = sample_df.loc[existing_head, 'high']
                else:
                    existing_head_price = sample_df.loc[existing_head, 'low']
                
                # Проверяем близость головы по времени (минимум 100-150 баров)
                time_diff = abs(head_pos - existing_head_pos)
                
                # Проверяем близость по цене (в пределах 0.2%)
                price_diff = abs(head_price - existing_head_price) / head_price
                
                # Если паттерны слишком близки по времени И по цене, считаем дубликатом
                if time_diff < min_distance_bars and price_diff < 0.002:
                    is_too_close = True
                    break
            
            if not is_too_close:
                filtered.append((score, pattern))
        
        return filtered
    
    hst_filtered = filter_by_time_and_price(hst_scored[:max_patterns * 3], min_distance_bars=100, is_top=True)[:max_patterns]
    hsb_filtered = filter_by_time_and_price(hsb_scored[:max_patterns * 3], min_distance_bars=100, is_top=False)[:max_patterns]
    
    return [p for _, p in hst_filtered], [p for _, p in hsb_filtered]


def visualize_sample_patterns(df: pd.DataFrame, sample_size: int = 1500, 
                              start_offset: int = 0,
                              instrument: str = "EURUSD", period: str = "m15"):
    """
    Визуализирует паттерны Head & Shoulders на небольшом участке данных.
    
    Args:
        df: Полный DataFrame с данными
        sample_size: Размер выборки в барах (по умолчанию 1500 = ~1 неделя на m15)
        start_offset: Смещение от начала данных (0 = с начала)
        instrument: Название инструмента
        period: Таймфрейм
    """
    # Берем выборку
    end_idx = min(start_offset + sample_size, len(df))
    sample_df = df.iloc[start_offset:end_idx].copy()
    
    print(f"Визуализация участка данных:")
    print(f"  Размер выборки: {len(sample_df)} баров")
    print(f"  Период: {sample_df.index[0]} - {sample_df.index[-1]}")
    sys.stdout.flush()
    
    # Ищем паттерны
    print(f"\nПоиск паттернов...")
    sys.stdout.flush()
    
    hst_patterns = detect_all_head_shoulders_top(
        sample_df,
        lookback=len(sample_df),
        shoulder_tolerance=0.02,
        max_peaks=25,
        min_distance_between_shoulders=20
    )
    
    hsb_patterns = detect_all_head_shoulders_bottom(
        sample_df,
        lookback=len(sample_df),
        shoulder_tolerance=0.02,
        max_troughs=25,
        min_distance_between_shoulders=20
    )
    
    print(f"Найдено паттернов:")
    print(f"  Head & Shoulders Top (HST): {len(hst_patterns)}")
    print(f"  Head & Shoulders Bottom (HSB): {len(hsb_patterns)}")
    print(f"  Всего: {len(hst_patterns) + len(hsb_patterns)}")
    sys.stdout.flush()
    
    # Фильтруем и оставляем только лучшие паттерны для визуализации
    # Уменьшаем количество для лучшей читаемости
    max_show = 5  # Показываем только 5 лучших паттернов каждого типа
    if len(hst_patterns) > max_show or len(hsb_patterns) > max_show:
        print(f"\nФильтрация паттернов по качеству (оставляем до {max_show} лучших каждого типа)...")
        sys.stdout.flush()
        hst_patterns, hsb_patterns = filter_best_patterns(hst_patterns, hsb_patterns, sample_df, max_patterns=max_show)
        print(f"После фильтрации:")
        print(f"  HST: {len(hst_patterns)} паттернов")
        print(f"  HSB: {len(hsb_patterns)} паттернов")
        sys.stdout.flush()
    
    # Выводим статистику по паттернам
    if hst_patterns:
        print(f"\nСтатистика HST паттернов:")
        distances = []
        head_advantages = []
        for left_idx, head_idx, right_idx, neckline in hst_patterns:
            left_price = sample_df.loc[left_idx, 'high']
            head_price = sample_df.loc[head_idx, 'high']
            right_price = sample_df.loc[right_idx, 'high']
            avg_shoulder = (left_price + right_price) / 2
            head_adv = (head_price - avg_shoulder) / avg_shoulder * 100
            
            # Расстояние между плечами в барах
            left_pos = sample_df.index.get_loc(left_idx)
            right_pos = sample_df.index.get_loc(right_idx)
            distance = right_pos - left_pos
            
            distances.append(distance)
            head_advantages.append(head_adv)
        
        print(f"  Среднее расстояние между плечами: {sum(distances)/len(distances):.1f} баров")
        print(f"  Мин/Макс расстояние: {min(distances)} / {max(distances)} баров")
        print(f"  Средняя высота головы: {sum(head_advantages)/len(head_advantages):.2f}%")
        print(f"  Мин/Макс высота головы: {min(head_advantages):.2f}% / {max(head_advantages):.2f}%")
        sys.stdout.flush()
    
    if hsb_patterns:
        print(f"\nСтатистика HSB паттернов:")
        distances = []
        head_advantages = []
        for left_idx, head_idx, right_idx, neckline in hsb_patterns:
            left_price = sample_df.loc[left_idx, 'low']
            head_price = sample_df.loc[head_idx, 'low']
            right_price = sample_df.loc[right_idx, 'low']
            avg_shoulder = (left_price + right_price) / 2
            head_adv = (avg_shoulder - head_price) / avg_shoulder * 100
            
            # Расстояние между плечами в барах
            left_pos = sample_df.index.get_loc(left_idx)
            right_pos = sample_df.index.get_loc(right_idx)
            distance = right_pos - left_pos
            
            distances.append(distance)
            head_advantages.append(head_adv)
        
        print(f"  Среднее расстояние между плечами: {sum(distances)/len(distances):.1f} баров")
        print(f"  Мин/Макс расстояние: {min(distances)} / {max(distances)} баров")
        print(f"  Средняя глубина головы: {sum(head_advantages)/len(head_advantages):.2f}%")
        print(f"  Мин/Макс глубина головы: {min(head_advantages):.2f}% / {max(head_advantages):.2f}%")
        sys.stdout.flush()
    
    # Создаем график
    fig, ax = plt.subplots(figsize=(20, 10))
    
    # Рисуем свечи (упрощенно - только high/low/close)
    # Используем более тонкие линии для свечей, чтобы паттерны были видны
    for i, (idx, row) in enumerate(sample_df.iterrows()):
        color = 'lightgreen' if row['close'] >= row['open'] else 'lightcoral'
        ax.plot([idx, idx], [row['low'], row['high']], color='gray', linewidth=0.3, alpha=0.2)
        ax.plot([idx, idx], [row['open'], row['close']], color=color, linewidth=1, alpha=0.4)
    
    # Рисуем паттерны HST с улучшенной визуализацией
    colors_hst = ['#0066FF', '#0033CC', '#0000FF', '#3300FF', '#6600FF']  # Разные оттенки синего
    for i, (left_idx, head_idx, right_idx, neckline) in enumerate(hst_patterns):
        left_price = sample_df.loc[left_idx, 'high']
        head_price = sample_df.loc[head_idx, 'high']
        right_price = sample_df.loc[right_idx, 'high']
        
        color = colors_hst[i % len(colors_hst)]
        
        # Полупрозрачная область паттерна
        from matplotlib.patches import Polygon
        pattern_area = Polygon(
            [(left_idx, neckline), (left_idx, left_price), 
             (head_idx, head_price), (right_idx, right_price), 
             (right_idx, neckline)],
            closed=True, facecolor=color, alpha=0.15, edgecolor='none'
        )
        ax.add_patch(pattern_area)
        
        # Структура паттерна - более толстая линия
        ax.plot([left_idx, head_idx, right_idx], 
               [left_price, head_price, right_price], 
               color=color, linewidth=3.5, alpha=0.95, 
               marker='o', markersize=10, markeredgecolor='white', markeredgewidth=2,
               label=f'HST {i+1}' if i < 3 else '')
        
        # Neckline - только в пределах паттерна (не за его границы)
        ax.plot([left_idx, right_idx], [neckline, neckline], 
               color='red', linestyle='--', linewidth=2.5, alpha=0.9,
               label=f'Neckline HST {i+1}' if i < 3 else '')
        
        # Подписи для всех паттернов
        ax.annotate(f'L{i+1}', xy=(left_idx, left_price), xytext=(8, 8), 
                   textcoords='offset points', fontsize=10, fontweight='bold', 
                   color=color, bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9, edgecolor=color, linewidth=2))
        ax.annotate(f'H{i+1}', xy=(head_idx, head_price), xytext=(8, 8), 
                   textcoords='offset points', fontsize=11, fontweight='bold', 
                   color=color, bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.9, edgecolor=color, linewidth=2))
        ax.annotate(f'R{i+1}', xy=(right_idx, right_price), xytext=(8, 8), 
                   textcoords='offset points', fontsize=10, fontweight='bold', 
                   color=color, bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9, edgecolor=color, linewidth=2))
    
    # Рисуем паттерны HSB с улучшенной визуализацией
    colors_hsb = ['#00AA00', '#008800', '#00CC00', '#00FF00', '#66FF66']  # Разные оттенки зеленого
    for i, (left_idx, head_idx, right_idx, neckline) in enumerate(hsb_patterns):
        left_price = sample_df.loc[left_idx, 'low']
        head_price = sample_df.loc[head_idx, 'low']
        right_price = sample_df.loc[right_idx, 'low']
        
        color = colors_hsb[i % len(colors_hsb)]
        
        # Полупрозрачная область паттерна
        from matplotlib.patches import Polygon
        pattern_area = Polygon(
            [(left_idx, neckline), (left_idx, left_price), 
             (head_idx, head_price), (right_idx, right_price), 
             (right_idx, neckline)],
            closed=True, facecolor=color, alpha=0.15, edgecolor='none'
        )
        ax.add_patch(pattern_area)
        
        # Структура паттерна - более толстая линия
        ax.plot([left_idx, head_idx, right_idx], 
               [left_price, head_price, right_price], 
               color=color, linewidth=3.5, alpha=0.95, 
               marker='o', markersize=10, markeredgecolor='white', markeredgewidth=2,
               label=f'HSB {i+1}' if i < 3 else '')
        
        # Neckline - только в пределах паттерна, разные оттенки для различимости
        neckline_color = ['#FF6600', '#FF8800', '#FFAA00', '#FFCC00', '#FFEE00'][i % 5]
        ax.plot([left_idx, right_idx], [neckline, neckline], 
               color=neckline_color, linestyle='--', linewidth=2.5, alpha=0.9,
               label=f'Neckline HSB {i+1}' if i < 3 else '')
        
        # Подписи для всех паттернов
        ax.annotate(f'L{i+1}', xy=(left_idx, left_price), xytext=(8, -8), 
                   textcoords='offset points', fontsize=10, fontweight='bold', 
                   color=color, bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9, edgecolor=color, linewidth=2))
        ax.annotate(f'H{i+1}', xy=(head_idx, head_price), xytext=(8, -8), 
                   textcoords='offset points', fontsize=11, fontweight='bold', 
                   color=color, bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.9, edgecolor=color, linewidth=2))
        ax.annotate(f'R{i+1}', xy=(right_idx, right_price), xytext=(8, -8), 
                   textcoords='offset points', fontsize=10, fontweight='bold', 
                   color=color, bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9, edgecolor=color, linewidth=2))
    
    # Настройка графика
    ax.set_title(f'{instrument} {period} - Head & Shoulders Patterns (Sample)\n'
                f'Найдено: {len(hst_patterns)} HST (Top) и {len(hsb_patterns)} HSB (Bottom) | '
                f'Период: {sample_df.index[0].strftime("%Y-%m-%d")} - {sample_df.index[-1].strftime("%Y-%m-%d")}', 
                fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Price', fontsize=12)
    ax.grid(True, alpha=0.3, linestyle=':')
    
    # Форматирование дат
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    plt.xticks(rotation=45, ha='right')
    
    # Легенда
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()
    
    # Сохраняем график
    output_dir = Path("docs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"head_shoulders_sample_{instrument}_{period}_{start_offset}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ График сохранен: {output_path}")
    sys.stdout.flush()
    
    plt.show()


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Визуализация паттернов Head & Shoulders на небольшом участке данных')
    parser.add_argument('--instrument', type=str, default='EURUSD', help='Инструмент (по умолчанию: EURUSD)')
    parser.add_argument('--period', type=str, default='m15', help='Таймфрейм (по умолчанию: m15)')
    parser.add_argument('--size', type=int, default=1500, help='Размер выборки в барах (по умолчанию: 1500)')
    parser.add_argument('--offset', type=int, default=0, help='Смещение от начала данных (по умолчанию: 0)')
    
    args = parser.parse_args()
    
    # Загружаем данные
    curated_dir = Path("data/v1/curated/ctrader")
    data_path = curated_dir / f"{args.instrument}_{args.period}.parquet"
    
    if not data_path.exists():
        print(f"Ошибка: Данные не найдены: {data_path}")
        sys.stdout.flush()
        return
    
    df = pd.read_parquet(data_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.set_index("utc_time").sort_index()
    
    print(f"Загружено {len(df)} баров для {args.instrument} {args.period}")
    print(f"Полный период: {df.index[0]} - {df.index[-1]}")
    sys.stdout.flush()
    
    # Визуализируем выборку
    visualize_sample_patterns(df, sample_size=args.size, start_offset=args.offset,
                              instrument=args.instrument, period=args.period)


if __name__ == "__main__":
    main()

