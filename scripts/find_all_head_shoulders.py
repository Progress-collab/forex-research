"""
Скрипт для поиска и визуализации всех паттернов Head & Shoulders по всему датасету EURUSD m15.
"""
from __future__ import annotations

import sys
import time
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

from src.patterns.chart import detect_all_head_shoulders_top, detect_all_head_shoulders_bottom


def find_all_patterns_in_dataset(df: pd.DataFrame, window_size: int = 500, 
                                 step: int = 400):
    """
    Находит все паттерны Head & Shoulders в датасете, используя скользящее окно.
    
    Args:
        df: DataFrame с данными
        window_size: Размер окна для поиска паттернов
        step: Шаг для скользящего окна (увеличен для уменьшения перекрытий)
        shoulder_tolerance: Допустимое отклонение цен плеч
    
    Returns:
        Tuple[List[HST], List[HSB]] - списки всех найденных паттернов
    """
    all_hst = []
    all_hsb = []
    # Улучшенная фильтрация дубликатов: проверяем по индексам и ценам
    seen_hst = {}  # {(left_idx, head_idx, right_idx): (left_price, head_price, right_price)}
    seen_hsb = {}
    
    print(f"Поиск паттернов в датасете из {len(df)} баров...")
    sys.stdout.flush()
    print(f"Параметры: window_size={window_size}, step={step}")
    sys.stdout.flush()
    
    total_windows = (len(df) - window_size) // step + 1
    print(f"Всего окон для обработки: {total_windows}")
    sys.stdout.flush()
    
    start_time = time.time()
    window_times = []
    
    # Используем скользящее окно
    try:
        for window_num, start_idx in enumerate(range(0, len(df) - window_size, step)):
            window_start_time = time.time()
            window_df = df.iloc[start_idx:start_idx + window_size]
            
            # Ищем паттерны используя новый алгоритм Patternz
            hst_patterns = detect_all_head_shoulders_top(
                window_df, 
                lookback=window_size,
                strict_patterns=False,  # Обычный режим (TradeDays=3)
                head_shoulder_pct=0.15  # 15% преимущество головы
            )
            hsb_patterns = detect_all_head_shoulders_bottom(
                window_df, 
                lookback=window_size,
                strict_patterns=False,  # Обычный режим (TradeDays=3)
                head_shoulder_pct=0.15  # 15% преимущество головы
            )
            
            # Добавляем паттерны с улучшенной фильтрацией дубликатов
            for pattern in hst_patterns:
                left_idx, head_idx, right_idx, neckline = pattern
                pattern_key = (left_idx, head_idx, right_idx)
                
                # Получаем цены для проверки
                left_price = window_df.loc[left_idx, 'high']
                head_price = window_df.loc[head_idx, 'high']
                right_price = window_df.loc[right_idx, 'high']
                
                # Проверяем, не является ли это дубликатом
                # Дубликат = паттерн очень близкий по времени (минимум 100-150 баров между головами) и ценам
                is_duplicate = False
                for existing_key, (existing_left, existing_head, existing_right) in seen_hst.items():
                    # Проверяем временную близость головы (минимум 100 баров)
                    time_diff_head = abs((head_idx - existing_key[1]).total_seconds() / 900)  # секунды в барах m15
                    
                    if time_diff_head < 100:
                        # Проверяем ценовую близость головы (в пределах 0.2%)
                        price_diff_head = abs(head_price - existing_head) / head_price
                        
                        if price_diff_head < 0.002:
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    seen_hst[pattern_key] = (left_price, head_price, right_price)
                    all_hst.append(pattern)
            
            for pattern in hsb_patterns:
                left_idx, head_idx, right_idx, neckline = pattern
                pattern_key = (left_idx, head_idx, right_idx)
                
                # Получаем цены для проверки
                left_price = window_df.loc[left_idx, 'low']
                head_price = window_df.loc[head_idx, 'low']
                right_price = window_df.loc[right_idx, 'low']
                
                # Проверяем, не является ли это дубликатом
                # Дубликат = паттерн очень близкий по времени (минимум 100-150 баров между головами) и ценам
                is_duplicate = False
                for existing_key, (existing_left, existing_head, existing_right) in seen_hsb.items():
                    # Проверяем временную близость головы (минимум 100 баров)
                    time_diff_head = abs((head_idx - existing_key[1]).total_seconds() / 900)
                    
                    if time_diff_head < 100:
                        # Проверяем ценовую близость головы (в пределах 0.2%)
                        price_diff_head = abs(head_price - existing_head) / head_price
                        
                        if price_diff_head < 0.002:
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    seen_hsb[pattern_key] = (left_price, head_price, right_price)
                    all_hsb.append(pattern)
            
            # Отслеживаем время обработки окна
            window_time = time.time() - window_start_time
            window_times.append(window_time)
            
            # Показываем прогресс после каждого окна
            progress = (window_num + 1) / total_windows * 100
            elapsed_time = time.time() - start_time
            avg_window_time = sum(window_times) / len(window_times)
            remaining_windows = total_windows - (window_num + 1)
            eta_seconds = avg_window_time * remaining_windows
            
            print(f"  Прогресс: {window_num + 1}/{total_windows} окон ({progress:.1f}%) | "
                  f"Найдено: HST={len(all_hst)}, HSB={len(all_hsb)} | "
                  f"Время: {elapsed_time:.1f}с | Осталось: {eta_seconds:.1f}с")
            sys.stdout.flush()
    
    except KeyboardInterrupt:
        print("\n\nПрерывание пользователем. Сохраняем найденные паттерны...")
        sys.stdout.flush()
    
    total_time = time.time() - start_time
    print(f"\nОбработка завершена за {total_time:.1f} секунд")
    sys.stdout.flush()
    
    return all_hst, all_hsb


def visualize_all_patterns(df: pd.DataFrame, all_hst: list, all_hsb: list, 
                          instrument: str = "EURUSD", period: str = "m15"):
    """
    Визуализирует все найденные паттерны на графике с простой и читаемой визуализацией.
    """
    fig, ax = plt.subplots(figsize=(24, 12))
    
    # Рисуем ценовую линию для контекста
    # Используем каждую N-ю свечу для производительности
    sample_rate = max(1, len(df) // 5000)  # Максимум 5000 точек
    sampled_df = df.iloc[::sample_rate]
    
    ax.plot(sampled_df.index, sampled_df['close'], 
           color='lightgray', linewidth=0.5, alpha=0.6, label='Close Price')
    
    # Рисуем паттерны HST - простой стиль, один цвет для всех
    hst_count = 0
    for left_idx, head_idx, right_idx, neckline in all_hst:
        if left_idx not in df.index or head_idx not in df.index or right_idx not in df.index:
            continue
        
        # Структура паттерна - синий цвет для всех HST
        left_price = df.loc[left_idx, 'high']
        head_price = df.loc[head_idx, 'high']
        right_price = df.loc[right_idx, 'high']
        
        ax.plot([left_idx, head_idx, right_idx], 
               [left_price, head_price, right_price], 
               color='blue', linewidth=2, alpha=0.8, 
               marker='o', markersize=6,
               label='HST Structure' if hst_count == 0 else '')
        
        # Neckline - красный пунктир для всех HST
        ax.plot([left_idx, right_idx], [neckline, neckline], 
               color='red', linestyle='--', linewidth=1.5, alpha=0.7,
               label='Neckline (HST)' if hst_count == 0 else '')
        
        hst_count += 1
    
    # Рисуем паттерны HSB - простой стиль, один цвет для всех
    hsb_count = 0
    for left_idx, head_idx, right_idx, neckline in all_hsb:
        if left_idx not in df.index or head_idx not in df.index or right_idx not in df.index:
            continue
        
        # Структура паттерна - зеленый цвет для всех HSB
        left_price = df.loc[left_idx, 'low']
        head_price = df.loc[head_idx, 'low']
        right_price = df.loc[right_idx, 'low']
        
        ax.plot([left_idx, head_idx, right_idx], 
               [left_price, head_price, right_price], 
               color='green', linewidth=2, alpha=0.8, 
               marker='o', markersize=6,
               label='HSB Structure' if hsb_count == 0 else '')
        
        # Neckline - оранжевый пунктир для всех HSB
        ax.plot([left_idx, right_idx], [neckline, neckline], 
               color='orange', linestyle='--', linewidth=1.5, alpha=0.7,
               label='Neckline (HSB)' if hsb_count == 0 else '')
        
        hsb_count += 1
    
    # Настройка графика
    ax.set_title(f'{instrument} {period} - Все паттерны Head & Shoulders\n'
                f'Найдено: {len(all_hst)} HST (Top) и {len(all_hsb)} HSB (Bottom)', 
                fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Time', fontsize=14)
    ax.set_ylabel('Price', fontsize=14)
    ax.grid(True, alpha=0.3, linestyle=':')
    
    # Форматирование дат
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.xticks(rotation=45, ha='right')
    
    # Легенда
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()
    
    # Сохраняем график
    output_dir = Path("docs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"head_shoulders_all_{instrument}_{period}.png"
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    print(f"\n✓ График сохранен: {output_path}")
    sys.stdout.flush()
    
    plt.show()


def main():
    """Основная функция."""
    instrument = "EURUSD"
    period = "m15"
    
    # Загружаем данные
    curated_dir = Path("data/v1/curated/ctrader")
    data_path = curated_dir / f"{instrument}_{period}.parquet"
    
    if not data_path.exists():
        print(f"Ошибка: Данные не найдены: {data_path}")
        sys.stdout.flush()
        return
    
    df = pd.read_parquet(data_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.set_index("utc_time").sort_index()
    
    print(f"Загружено {len(df)} баров для {instrument} {period}")
    sys.stdout.flush()
    print(f"Период: {df.index[0]} - {df.index[-1]}")
    sys.stdout.flush()
    
    # Находим все паттерны используя новый алгоритм Patternz
    all_hst, all_hsb = find_all_patterns_in_dataset(df, window_size=500, step=400)
    
    print(f"\n{'='*60}")
    sys.stdout.flush()
    print(f"ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    sys.stdout.flush()
    print(f"{'='*60}")
    sys.stdout.flush()
    print(f"Head & Shoulders Top (HST): {len(all_hst)} паттернов")
    sys.stdout.flush()
    print(f"Head & Shoulders Bottom (HSB): {len(all_hsb)} паттернов")
    sys.stdout.flush()
    print(f"Всего найдено: {len(all_hst) + len(all_hsb)} паттернов")
    sys.stdout.flush()
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    # Визуализируем
    if all_hst or all_hsb:
        visualize_all_patterns(df, all_hst, all_hsb, instrument, period)
    else:
        print("Паттерны не найдены.")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

