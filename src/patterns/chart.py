"""
Распознавание графических паттернов.
Реализация по оригинальной логике Patternz.
"""
from __future__ import annotations

from typing import Optional, Tuple, List

import pandas as pd
import numpy as np

try:
    from scipy.signal import find_peaks
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# Глобальные переменные для состояния алгоритма (как в оригинале Patternz)
_armpit: Optional[float] = None
_head_index: Optional[int] = None
_strict_patterns: bool = False  # Режим строгих паттернов


def _get_price_scale(price1: float, price2: float) -> float:
    """
    Вычисляет масштаб цены для нормализации.
    Аналог GetPriceScale из оригинального кода (строка 10300).
    """
    if price1 + price2 != 0:
        return (price1 + price2) / 2.0 / 40.0
    if price1 > 0:
        return price1 / 40.0
    return price2 / 40.0


def _get_percent(percent: float, strict_patterns: bool = False) -> float:
    """
    Корректирует процент в зависимости от режима.
    Аналог GetPercent из оригинального кода (строка 10282).
    """
    if not strict_patterns:
        if 0 <= percent <= 1:
            return percent * 2.0
        else:
            return percent * 1.5
    return percent


def check_nearness(
    point1: float,
    point2: float,
    percent: float = -1.0,
    price_vary: float = -1.0,
    strict_patterns: bool = False,
) -> bool:
    """
    Проверяет близость двух цен с учетом процента или абсолютного отклонения.
    Аналог CheckNearness из оригинального кода (строка 1120).
    
    Логика:
    - Если percent=-1 и price_vary положительный: проверяет что цены НЕ близки (разница >= price_vary)
    - Если percent задан и price_vary=-1: проверяет что цены близки (разница <= percent)
    - Если оба заданы: проверяет что цены близки по любому критерию
    
    Args:
        point1: Первая цена
        point2: Вторая цена
        percent: Процент отклонения (-1 если не используется)
        price_vary: Абсолютное отклонение (-1 если не используется, положительное = проверка что НЕ близки)
        strict_patterns: Режим строгих паттернов
    
    Returns:
        True если условие выполнено, False иначе
    """
    if percent == -1.0 and price_vary == -1.0:
        return False
    
    if point1 == 0 or point2 == 0:
        return False
    
    price_scale = _get_price_scale(point1, point2)
    if price_scale == 0:
        return False
    
    # Случай 1: percent=-1, price_vary положительный - проверяем что цены НЕ близки
    # (голова должна быть достаточно далеко от плеч)
    if percent == -1.0 and price_vary != -1.0 and price_vary > 0:
        # Корректировка для высоких цен
        adjusted_price_vary = price_vary
        if point1 > 2500 or point2 > 2500:
            adjusted_price_vary /= 2.0
        if point1 > 5000 or point2 > 5000:
            adjusted_price_vary /= 2.0
        if point1 > 10000 or point2 > 10000:
            adjusted_price_vary /= 2.0
        if point1 > 50000 or point2 > 50000:
            adjusted_price_vary /= 2.0
        
        diff_scaled = abs(point1 / price_scale - point2 / price_scale)
        # Возвращаем True если цены БЛИЗКИ (разница <= price_vary) - это плохо для Head & Shoulders
        # Т.е. голова слишком близка к плечу
        return diff_scaled <= adjusted_price_vary
    
    # Корректировка price_vary для высоких цен (только если используется)
    adjusted_price_vary = price_vary
    if price_vary != -1.0 and price_vary > 0:
        if point1 > 2500 or point2 > 2500:
            adjusted_price_vary /= 2.0
        if point1 > 5000 or point2 > 5000:
            adjusted_price_vary /= 2.0
        if point1 > 10000 or point2 > 10000:
            adjusted_price_vary /= 2.0
        if point1 > 50000 or point2 > 50000:
            adjusted_price_vary /= 2.0
    
    # Корректировка процента
    adjusted_percent = percent
    if percent != -1.0:
        adjusted_percent = _get_percent(percent, strict_patterns)
    
    # Проверка по абсолютному отклонению (price_vary) - цены близки
    if percent == -1.0:
        diff_scaled = abs(point1 / price_scale - point2 / price_scale)
        return diff_scaled <= adjusted_price_vary
    
    # Проверка по проценту (percent) - цены близки
    if price_vary == -1.0:
        if strict_patterns:
            diff_pct = abs(point1 - point2) / max(point1, point2) * 100.0
            return diff_pct <= adjusted_percent
        else:
            diff_pct1 = abs(point1 - point2) / point1 * 100.0
            diff_pct2 = abs(point1 - point2) / point2 * 100.0
            return diff_pct1 <= adjusted_percent or diff_pct2 <= adjusted_percent
    
    # Оба параметра заданы - проверяем по любому из них (цены близки)
    diff_scaled = abs(point1 / price_scale - point2 / price_scale)
    diff_pct1 = abs(point1 - point2) / point1 * 100.0
    diff_pct2 = abs(point1 - point2) / point2 * 100.0
    
    return (
        diff_scaled <= adjusted_price_vary
        or diff_pct1 <= adjusted_percent
        or diff_pct2 <= adjusted_percent
    )


def find_all_tops(df: pd.DataFrame, trade_days: int = 3, start_idx: int = 0, end_idx: Optional[int] = None) -> List[int]:
    """
    Находит все пики используя алгоритм скользящего окна.
    Аналог FindAllTops из оригинального кода (строка 2398).
    
    Args:
        df: DataFrame с данными
        trade_days: Количество баров, в течение которых пик должен оставаться пиком
        start_idx: Начальный индекс для поиска
        end_idx: Конечный индекс для поиска (None = до конца)
    
    Returns:
        Список индексов пиков
    """
    if end_idx is None:
        end_idx = len(df)
    
    if end_idx - start_idx < trade_days:
        return []
    
    highs = df["high"].values
    array_tops: List[int] = []
    
    # Инициализация: первый пик - начальный индекс
    array_tops.append(start_idx)
    num = trade_days
    
    for i in range(start_idx + 1, end_idx):
        # Если текущая цена выше или равна текущему пику, обновляем пик
        if highs[i] >= highs[array_tops[-1]]:
            array_tops[-1] = i
            num = trade_days - 1
            continue
        
        num -= 1
        
        # Когда счетчик становится отрицательным, проверяем валидность пика
        while num < 0:
            num = trade_days
            peak_idx = array_tops[-1]
            
            # Проверяем, что пик оставался пиком в течение trade_days баров
            if peak_idx - trade_days >= start_idx:
                # Проверяем все бары перед пиком
                valid = True
                for j in range(peak_idx - trade_days, peak_idx):
                    if highs[j] > highs[peak_idx]:
                        valid = False
                        break
                
                if valid:
                    # Проверяем, есть ли место для следующего пика
                    if end_idx - i > trade_days:
                        array_tops.append(i)
                        break
                    else:
                        return array_tops
                else:
                    # Удаляем невалидный пик и пробуем снова
                    if len(array_tops) > 1:
                        array_tops.pop()
                        continue
                    else:
                        array_tops[-1] = i
                        break
            else:
                # Недостаточно баров для проверки, просто обновляем пик
                array_tops[-1] = i
                break
    
    return array_tops


def find_all_bottoms(df: pd.DataFrame, trade_days: int = 3, start_idx: int = 0, end_idx: Optional[int] = None) -> List[int]:
    """
    Находит все впадины используя алгоритм скользящего окна.
    Аналог FindAllBottoms из оригинального кода (строка 1894).
    
    Args:
        df: DataFrame с данными
        trade_days: Количество баров, в течение которых впадина должна оставаться впадиной
        start_idx: Начальный индекс для поиска
        end_idx: Конечный индекс для поиска (None = до конца)
    
    Returns:
        Список индексов впадин
    """
    if end_idx is None:
        end_idx = len(df)
    
    if end_idx - start_idx < trade_days:
        return []
    
    lows = df["low"].values
    array_bottoms: List[int] = []
    
    # Инициализация: первая впадина - начальный индекс
    array_bottoms.append(start_idx)
    num = trade_days
    
    for i in range(start_idx + 1, end_idx):
        # Если текущая цена ниже или равна текущей впадине, обновляем впадину
        if lows[i] <= lows[array_bottoms[-1]]:
            array_bottoms[-1] = i
            num = trade_days - 1
            continue
        
        num -= 1
        
        # Когда счетчик становится отрицательным, проверяем валидность впадины
        while num < 0:
            num = trade_days
            bottom_idx = array_bottoms[-1]
            
            # Проверяем, что впадина оставалась впадиной в течение trade_days баров
            if bottom_idx - trade_days >= start_idx:
                # Проверяем все бары перед впадиной
                valid = True
                for j in range(bottom_idx - trade_days, bottom_idx):
                    if lows[j] < lows[bottom_idx]:
                        valid = False
                        break
                
                if valid:
                    # Проверяем, есть ли место для следующей впадины
                    if end_idx - i > trade_days:
                        array_bottoms.append(i)
                        break
                    else:
                        return array_bottoms
                else:
                    # Удаляем невалидную впадину и пробуем снова
                    if len(array_bottoms) > 1:
                        array_bottoms.pop()
                        continue
                    else:
                        array_bottoms[-1] = i
                        break
            else:
                # Недостаточно баров для проверки, просто обновляем впадину
                array_bottoms[-1] = i
                break
    
    return array_bottoms


def find_top_armpit(
    df: pd.DataFrame,
    index1: int,
    index2: int,
    bottom_indices: List[int],
) -> Tuple[bool, Optional[float]]:
    """
    Находит минимальную впадину (neckline) между двумя пиками.
    Аналог FindTopArmpit из оригинального кода (строка 8295).
    
    Args:
        df: DataFrame с данными
        index1: Индекс первого пика
        index2: Индекс второго пика
        bottom_indices: Список индексов впадин
    
    Returns:
        Tuple (найдено ли, цена neckline или None)
    """
    global _armpit
    
    _armpit = None
    lows = df["low"].values
    
    # Ищем максимальную впадину между index1 и index2
    for bottom_idx in bottom_indices:
        if index1 <= bottom_idx <= index2:
            if _armpit is None:
                _armpit = float(lows[bottom_idx])
            else:
                _armpit = min(_armpit, float(lows[bottom_idx]))
    
    if _armpit is None:
        return True, None  # Не найдено - возвращаем True (ошибка)
    
    return False, _armpit  # Найдено


def find_bottom_armpit(
    df: pd.DataFrame,
    index1: int,
    index2: int,
    top_indices: List[int],
) -> Tuple[bool, Optional[float]]:
    """
    Находит максимальный пик (neckline) между двумя впадинами.
    Аналог FindBottomArmpit из оригинального кода (строка 3182).
    
    Args:
        df: DataFrame с данными
        index1: Индекс первой впадины
        index2: Индекс второй впадины
        top_indices: Список индексов пиков
    
    Returns:
        Tuple (найдено ли, цена neckline или None)
    """
    global _armpit
    
    _armpit = None
    highs = df["high"].values
    
    # Ищем минимальный пик между index1 и index2
    for top_idx in top_indices:
        if index1 <= top_idx <= index2:
            if _armpit is None:
                _armpit = float(highs[top_idx])
            else:
                _armpit = max(_armpit, float(highs[top_idx]))
    
    if _armpit is None:
        return True, None  # Не найдено - возвращаем True (ошибка)
    
    return False, _armpit  # Найдено


def find_hst(
    df: pd.DataFrame,
    ls_index: int,
    rs_index: int,
    head_index: int,
    head_shoulder: float,
    strict_patterns: bool = False,
) -> bool:
    """
    Проверяет симметрию плеч и преимущество головы для HST.
    Аналог FindHST из оригинального кода (строка 6127).
    
    Args:
        df: DataFrame с данными
        ls_index: Индекс левого плеча
        rs_index: Индекс правого плеча
        head_index: Индекс головы
        head_shoulder: Процент преимущества головы (0.15 или 0.25)
        strict_patterns: Режим строгих паттернов
    
    Returns:
        True если паттерн невалиден, False если валиден
    """
    highs = df["high"].values
    ls_price = float(highs[ls_index])
    rs_price = float(highs[rs_index])
    head_price = float(highs[head_index])
    
    if strict_patterns:
        # Строгий режим: плечи должны быть очень близки (40%)
        if not check_nearness(ls_price, rs_price, percent=1.0, price_vary=0.4, strict_patterns=True):
            return True
        
        # Голова должна быть достаточно далеко от плеч (head_shoulder)
        # CheckNearness с percent=-1 и price_vary=head_shoulder проверяет что цены НЕ близки
        if check_nearness(head_price, rs_price, percent=-1.0, price_vary=head_shoulder, strict_patterns=True):
            return True  # Голова слишком близка к правому плечу
        if check_nearness(head_price, ls_price, percent=-1.0, price_vary=head_shoulder, strict_patterns=True):
            return True  # Голова слишком близка к левому плечу
    else:
        # Обычный режим: плечи должны быть близки (40-60% в зависимости от расстояния)
        shoulder_distance = rs_index - ls_index
        shoulder_tolerance = 0.6 if shoulder_distance >= 42 else 0.4
        
        if not check_nearness(ls_price, rs_price, percent=0.5, price_vary=shoulder_tolerance, strict_patterns=False):
            return True
        
        # Голова должна быть достаточно далеко от плеч (head_shoulder)
        # CheckNearness с percent=0.5 и price_vary=head_shoulder проверяет что цены НЕ близки
        if check_nearness(head_price, rs_price, percent=0.5, price_vary=head_shoulder, strict_patterns=False):
            return True  # Голова слишком близка к правому плечу
        if check_nearness(head_price, ls_price, percent=0.5, price_vary=head_shoulder, strict_patterns=False):
            return True  # Голова слишком близка к левому плечу
    
    return False  # Паттерн валиден


def find_hsb(
    df: pd.DataFrame,
    ls_index: int,
    rs_index: int,
    head_index: int,
    head_shoulder: float,
    strict_patterns: bool = False,
) -> bool:
    """
    Проверяет симметрию плеч и преимущество головы для HSB.
    Аналог FindHSB из оригинального кода (строка 6092).
    
    Args:
        df: DataFrame с данными
        ls_index: Индекс левого плеча
        rs_index: Индекс правого плеча
        head_index: Индекс головы
        head_shoulder: Процент преимущества головы (0.15 или 0.25)
        strict_patterns: Режим строгих паттернов
    
    Returns:
        True если паттерн невалиден, False если валиден
    """
    lows = df["low"].values
    ls_price = float(lows[ls_index])
    rs_price = float(lows[rs_index])
    head_price = float(lows[head_index])
    
    if strict_patterns:
        # Строгий режим: плечи должны быть очень близки (40%)
        if not check_nearness(ls_price, rs_price, percent=1.0, price_vary=0.4, strict_patterns=True):
            return True
        
        # Голова должна быть достаточно далеко от плеч (head_shoulder)
        if check_nearness(rs_price, head_price, percent=-1.0, price_vary=head_shoulder, strict_patterns=True):
            return True  # Голова слишком близка к правому плечу
        if check_nearness(ls_price, head_price, percent=-1.0, price_vary=head_shoulder, strict_patterns=True):
            return True  # Голова слишком близка к левому плечу
    else:
        # Обычный режим: плечи должны быть близки (40-60% в зависимости от расстояния)
        shoulder_distance = rs_index - ls_index
        shoulder_tolerance = 0.6 if shoulder_distance >= 42 else 0.4
        
        if not check_nearness(ls_price, rs_price, percent=0.5, price_vary=shoulder_tolerance, strict_patterns=False):
            return True
        
        # Голова должна быть достаточно далеко от плеч (head_shoulder)
        if check_nearness(rs_price, head_price, percent=0.5, price_vary=head_shoulder, strict_patterns=False):
            return True  # Голова слишком близка к правому плечу
        if check_nearness(ls_price, head_price, percent=0.5, price_vary=head_shoulder, strict_patterns=False):
            return True  # Голова слишком близка к левому плечу
    
    return False  # Паттерн валиден


def detect_head_shoulders_top(df: pd.DataFrame, lookback: int = 100, shoulder_tolerance: float = 0.02) -> Optional[Tuple[int, int, int]]:
    """
    Обнаруживает паттерн Head & Shoulders Top (Голова и Плечи - вершина).
    
    Условия:
    - Три вершины: левое плечо, голова (выше), правое плечо
    - Плечи примерно на одном уровне (в пределах shoulder_tolerance)
    - Голова заметно выше плеч (минимум на 0.3% для коротких таймфреймов)
    - Между плечами есть впадина (neckline)
    
    Args:
        df: DataFrame с колонками open, high, low, close
        lookback: Количество последних свечей для анализа
        shoulder_tolerance: Допустимое отклонение цен плеч (0.02 = 2%)
    
    Returns:
        Tuple (индекс левого плеча, индекс головы, индекс правого плеча) или None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    highs = recent["high"]
    
    # Находим локальные максимумы
    peaks = []
    window = 3
    
    for i in range(window, len(highs) - window):
        is_peak = True
        for j in range(i - window, i + window + 1):
            if j != i and highs.iloc[j] >= highs.iloc[i]:
                is_peak = False
                break
        if is_peak:
            peaks.append((i, highs.iloc[i]))
    
    if len(peaks) < 3:
        return None
    
    # Ищем три вершины: левое плечо, голова, правое плечо
    for i in range(len(peaks) - 2):
        left_shoulder_idx, left_shoulder_price = peaks[i]
        
        for j in range(i + 1, len(peaks) - 1):
            head_idx, head_price = peaks[j]
            
            # Голова должна быть выше левого плеча
            if head_price <= left_shoulder_price:
                continue
            
            for k in range(j + 1, len(peaks)):
                right_shoulder_idx, right_shoulder_price = peaks[k]
                
                # Голова должна быть выше правого плеча
                if head_price <= right_shoulder_price:
                    continue
                
                # Плечи должны быть примерно на одном уровне
                shoulder_diff = abs(left_shoulder_price - right_shoulder_price) / max(left_shoulder_price, right_shoulder_price)
                if shoulder_diff > shoulder_tolerance:
                    continue
                
                # Голова должна быть заметно выше плеч (ослаблено до 0.3% для коротких таймфреймов)
                avg_shoulder_price = (left_shoulder_price + right_shoulder_price) / 2
                head_advantage = (head_price - avg_shoulder_price) / avg_shoulder_price
                if head_advantage < 0.003:  # 0.3% вместо 2%
                    continue
                
                # Проверяем наличие впадины между плечами (neckline)
                between_left_head = recent.iloc[left_shoulder_idx:head_idx]
                between_head_right = recent.iloc[head_idx:right_shoulder_idx]
                neckline_left = between_left_head["low"].min()
                neckline_right = between_head_right["low"].min()
                neckline = max(neckline_left, neckline_right)
                
                # Neckline должна быть ниже головы (ослаблено условие)
                # Проверяем, что есть четкая впадина между плечами
                if neckline >= head_price * 0.999:  # Neckline не должна быть слишком близко к голове
                    continue
                
                # Проверяем, что между плечами есть впадина (neckline ниже среднего плеча или близко к нему)
                # Ослабляем условие - neckline может быть немного выше плеч, но должна быть четко ниже головы
                neckline_to_shoulder = (neckline - avg_shoulder_price) / avg_shoulder_price
                if neckline_to_shoulder > 0.01:  # Neckline не должна быть более чем на 1% выше плеч
                    continue
                
                return (recent.index[left_shoulder_idx], recent.index[head_idx], recent.index[right_shoulder_idx])
    
    return None


def detect_head_shoulders_bottom(df: pd.DataFrame, lookback: int = 100, shoulder_tolerance: float = 0.02) -> Optional[Tuple[int, int, int]]:
    """
    Обнаруживает паттерн Head & Shoulders Bottom (Голова и Плечи - дно).
    
    Условия:
    - Три дна: левое плечо, голова (ниже), правое плечо
    - Плечи примерно на одном уровне (в пределах shoulder_tolerance)
    - Голова заметно ниже плеч (минимум на 0.3% для коротких таймфреймов)
    - Между плечами есть пик (neckline)
    
    Args:
        df: DataFrame с колонками open, high, low, close
        lookback: Количество последних свечей для анализа
        shoulder_tolerance: Допустимое отклонение цен плеч (0.02 = 2%)
    
    Returns:
        Tuple (индекс левого плеча, индекс головы, индекс правого плеча) или None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    lows = recent["low"]
    
    # Находим локальные минимумы
    troughs = []
    window = 3
    
    for i in range(window, len(lows) - window):
        is_trough = True
        for j in range(i - window, i + window + 1):
            if j != i and lows.iloc[j] <= lows.iloc[i]:
                is_trough = False
                break
        if is_trough:
            troughs.append((i, lows.iloc[i]))
    
    if len(troughs) < 3:
        return None
    
    # Ищем три дна: левое плечо, голова, правое плечо
    for i in range(len(troughs) - 2):
        left_shoulder_idx, left_shoulder_price = troughs[i]
        
        for j in range(i + 1, len(troughs) - 1):
            head_idx, head_price = troughs[j]
            
            # Голова должна быть ниже левого плеча
            if head_price >= left_shoulder_price:
                continue
            
            for k in range(j + 1, len(troughs)):
                right_shoulder_idx, right_shoulder_price = troughs[k]
                
                # Голова должна быть ниже правого плеча
                if head_price >= right_shoulder_price:
                    continue
                
                # Плечи должны быть примерно на одном уровне
                shoulder_diff = abs(left_shoulder_price - right_shoulder_price) / max(left_shoulder_price, right_shoulder_price)
                if shoulder_diff > shoulder_tolerance:
                    continue
                
                # Голова должна быть заметно ниже плеч (ослаблено до 0.3% для коротких таймфреймов)
                avg_shoulder_price = (left_shoulder_price + right_shoulder_price) / 2
                head_advantage = (avg_shoulder_price - head_price) / avg_shoulder_price
                if head_advantage < 0.003:  # 0.3% вместо 2%
                    continue
                
                # Проверяем наличие пика между плечами (neckline)
                between_left_head = recent.iloc[left_shoulder_idx:head_idx]
                between_head_right = recent.iloc[head_idx:right_shoulder_idx]
                neckline_left = between_left_head["high"].max()
                neckline_right = between_head_right["high"].max()
                neckline = min(neckline_left, neckline_right)
                
                # Neckline должна быть выше головы (ослаблено условие)
                # Проверяем, что есть четкий пик между плечами
                if neckline <= head_price * 1.001:  # Neckline не должна быть слишком близко к голове
                    continue
                
                # Проверяем, что между плечами есть пик (neckline выше среднего плеча или близко к нему)
                # Ослабляем условие - neckline может быть немного ниже плеч, но должна быть четко выше головы
                neckline_to_shoulder = (neckline - avg_shoulder_price) / avg_shoulder_price
                if neckline_to_shoulder < -0.01:  # Neckline не должна быть более чем на 1% ниже плеч
                    continue
                
                return (recent.index[left_shoulder_idx], recent.index[head_idx], recent.index[right_shoulder_idx])
    
    return None


def detect_all_head_shoulders_top(
    df: pd.DataFrame,
    lookback: int = 100,
    strict_patterns: bool = False,
    head_shoulder_pct: float = 0.15,
) -> List[Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, float]]:
    """
    Обнаруживает ВСЕ паттерны Head & Shoulders Top в данных.
    Реализация по оригинальной логике Patternz (строка 5965).
    
    Args:
        df: DataFrame с данными
        lookback: Количество последних свечей для анализа
        strict_patterns: Режим строгих паттернов (использует TradeDays=5 вместо 3)
        head_shoulder_pct: Процент преимущества головы (0.15 для обычных, 0.25 для строгих)
    
    Returns:
        List[Tuple] - список всех найденных паттернов:
        (индекс левого плеча, индекс головы, индекс правого плеча, цена neckline)
    """
    global _head_index, _armpit
    
    patterns = []
    
    if len(df) < lookback:
        return patterns
    
    recent = df.tail(lookback).copy()
    original_index = recent.index.copy()
    recent = recent.reset_index(drop=True)
    
    # Находим пики и впадины используя оригинальный алгоритм
    trade_days = 5 if strict_patterns else 3
    top_indices = find_all_tops(recent, trade_days=trade_days)
    bottom_indices = find_all_bottoms(recent, trade_days=2)
    
    if len(top_indices) < 3 or len(bottom_indices) < 2:
        return patterns
    
    highs = recent["high"].values
    
    # Основной цикл поиска паттернов (как в оригинале, строка 5984)
    for i in range(1, len(top_indices)):
        _head_index = top_indices[i]
        head_price = float(highs[_head_index])
        
        # Ищем левое плечо (j идет назад от головы)
        for j in range(i - 1, -1, -1):
            ls_idx = top_indices[j]
            ls_price = float(highs[ls_idx])
            
            # Левое плечо должно быть ниже головы
            if ls_price > head_price:
                break
            
            # Ищем правое плечо (k идет вперед от головы)
            for k in range(i + 1, len(top_indices)):
                rs_idx = top_indices[k]
                rs_price = float(highs[rs_idx])
                
                # Правое плечо должно быть ниже головы
                if rs_price > head_price:
                    break
                
                # Проверяем, что между плечами нет пиков выше головы (строка 6008-6013)
                has_higher_peak = False
                for l in range(j + 1, k):
                    if l != i and highs[top_indices[l]] > head_price:
                        has_higher_peak = True
                        break
                
                if has_higher_peak:
                    continue
                
                # Проверяем FindHST (симметрия плеч и преимущество головы)
                if find_hst(recent, ls_idx, rs_idx, _head_index, head_shoulder_pct, strict_patterns):
                    continue
                
                # Максимальное расстояние между плечами: 126 баров
                if rs_idx - ls_idx > 126:
                    break
                
                # Находим neckline между левым плечом и головой
                error, arm_pit_left = find_top_armpit(recent, ls_idx, _head_index, bottom_indices)
                if error:
                    continue
                
                # Находим neckline между головой и правым плечом
                error, arm_pit_right = find_top_armpit(recent, _head_index, rs_idx, bottom_indices)
                if error:
                    continue
                
                # Берем минимальную впадину (neckline)
                neckline = min(arm_pit_left, arm_pit_right)
                
                # Добавляем паттерн с оригинальными индексами
                patterns.append((
                    original_index[ls_idx],
                    original_index[_head_index],
                    original_index[rs_idx],
                    neckline
                ))
    
    return patterns


def detect_all_head_shoulders_bottom(
    df: pd.DataFrame,
    lookback: int = 100,
    strict_patterns: bool = False,
    head_shoulder_pct: float = 0.15,
) -> List[Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, float]]:
    """
    Обнаруживает ВСЕ паттерны Head & Shoulders Bottom в данных.
    Реализация по оригинальной логике Patternz (строка 5841).
    
    Args:
        df: DataFrame с данными
        lookback: Количество последних свечей для анализа
        strict_patterns: Режим строгих паттернов (использует TradeDays=5 вместо 3)
        head_shoulder_pct: Процент преимущества головы (0.15 для обычных, 0.25 для строгих)
    
    Returns:
        List[Tuple] - список всех найденных паттернов:
        (индекс левого плеча, индекс головы, индекс правого плеча, цена neckline)
    """
    global _head_index, _armpit
    
    patterns = []
    
    if len(df) < lookback:
        return patterns
    
    recent = df.tail(lookback).copy()
    original_index = recent.index.copy()
    recent = recent.reset_index(drop=True)
    
    # Находим впадины и пики используя оригинальный алгоритм
    trade_days = 5 if strict_patterns else 3
    bottom_indices = find_all_bottoms(recent, trade_days=trade_days)
    top_indices = find_all_tops(recent, trade_days=2)
    
    if len(bottom_indices) < 3 or len(top_indices) < 2:
        return patterns
    
    lows = recent["low"].values
    
    # Основной цикл поиска паттернов (как в оригинале, строка 5860)
    for i in range(1, len(bottom_indices)):
        _head_index = bottom_indices[i]
        head_price = float(lows[_head_index])
        
        # Ищем левое плечо (j идет назад от головы)
        for j in range(i - 1, -1, -1):
            ls_idx = bottom_indices[j]
            ls_price = float(lows[ls_idx])
            
            # Левое плечо должно быть выше головы
            if ls_price < head_price:
                break
            
            # Ищем правое плечо (k идет вперед от головы)
            for k in range(i + 1, len(bottom_indices)):
                rs_idx = bottom_indices[k]
                rs_price = float(lows[rs_idx])
                
                # Правое плечо должно быть выше головы
                if rs_price < head_price:
                    break
                
                # Проверяем, что между плечами нет впадин ниже головы
                has_lower_trough = False
                for l in range(j + 1, k):
                    if l != i and lows[bottom_indices[l]] < head_price:
                        has_lower_trough = True
                        break
                
                if has_lower_trough:
                    continue
                
                # Проверяем FindHSB (симметрия плеч и преимущество головы)
                if find_hsb(recent, ls_idx, rs_idx, _head_index, head_shoulder_pct, strict_patterns):
                    continue
                
                # Максимальное расстояние между плечами: 126 баров
                if rs_idx - ls_idx > 126:
                    break
                
                # Находим neckline между левым плечом и головой
                error, arm_pit_left = find_bottom_armpit(recent, ls_idx, _head_index, top_indices)
                if error:
                    continue
                
                # Находим neckline между головой и правым плечом
                error, arm_pit_right = find_bottom_armpit(recent, _head_index, rs_idx, top_indices)
                if error:
                    continue
                
                # Берем максимальный пик (neckline)
                neckline = max(arm_pit_left, arm_pit_right)
                
                # Добавляем паттерн с оригинальными индексами
                patterns.append((
                    original_index[ls_idx],
                    original_index[_head_index],
                    original_index[rs_idx],
                    neckline
                ))
    
    return patterns


def detect_double_top(df: pd.DataFrame, lookback: int = 50, tolerance: float = 0.02) -> Optional[Tuple[int, int]]:
    """
    Обнаруживает паттерн Double Top (двойная вершина).
    
    Условия:
    - Две вершины примерно на одном уровне (в пределах tolerance)
    - Между ними есть впадина минимум на 2% ниже вершин
    
    Args:
        df: DataFrame с колонками open, high, low, close
        lookback: Количество последних свечей для анализа
        tolerance: Допустимое отклонение цен вершин (0.02 = 2%, увеличено для большей гибкости)
    
    Returns:
        Tuple (индекс первой вершины, индекс второй вершины) или None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    highs = recent["high"]
    
    # Находим локальные максимумы (более гибкий алгоритм)
    peaks = []
    window = 3  # Окно для поиска локальных максимумов
    
    for i in range(window, len(highs) - window):
        # Проверяем, что текущая точка выше соседних в окне
        is_peak = True
        for j in range(i - window, i + window + 1):
            if j != i and highs.iloc[j] >= highs.iloc[i]:
                is_peak = False
                break
        
        if is_peak:
            peaks.append((i, highs.iloc[i]))
    
    if len(peaks) < 2:
        return None
    
    # Ищем две вершины примерно на одном уровне
    for i in range(len(peaks) - 1):
        peak1_idx, peak1_price = peaks[i]
        for j in range(i + 1, len(peaks)):
            peak2_idx, peak2_price = peaks[j]
            
            # Проверяем, что цены близки (в пределах tolerance)
            price_diff = abs(peak1_price - peak2_price) / peak1_price
            if price_diff <= tolerance:
                # Проверяем, что между ними есть впадина
                between = recent.iloc[peak1_idx : peak2_idx + 1]
                min_between = between["low"].min()
                if min_between < peak1_price * 0.98:  # Впадина минимум на 2% ниже
                    # Возвращаем абсолютные индексы из оригинального DataFrame
                    return (recent.index[peak1_idx], recent.index[peak2_idx])
    
    return None


def detect_double_bottom(df: pd.DataFrame, lookback: int = 50, tolerance: float = 0.02) -> Optional[Tuple[int, int]]:
    """
    Обнаруживает паттерн Double Bottom (двойное дно).
    
    Условия:
    - Два дна примерно на одном уровне (в пределах tolerance)
    - Между ними есть пик минимум на 2% выше дна
    
    Args:
        df: DataFrame с колонками open, high, low, close
        lookback: Количество последних свечей для анализа
        tolerance: Допустимое отклонение цен дна (0.02 = 2%, увеличено для большей гибкости)
    
    Returns:
        Tuple (индекс первого дна, индекс второго дна) или None
    """
    if len(df) < lookback:
        return None
    
    recent = df.tail(lookback).copy()
    lows = recent["low"]
    
    # Находим локальные минимумы (более гибкий алгоритм)
    troughs = []
    window = 3  # Окно для поиска локальных минимумов
    
    for i in range(window, len(lows) - window):
        # Проверяем, что текущая точка ниже соседних в окне
        is_trough = True
        for j in range(i - window, i + window + 1):
            if j != i and lows.iloc[j] <= lows.iloc[i]:
                is_trough = False
                break
        
        if is_trough:
            troughs.append((i, lows.iloc[i]))
    
    if len(troughs) < 2:
        return None
    
    # Ищем два дна примерно на одном уровне
    for i in range(len(troughs) - 1):
        trough1_idx, trough1_price = troughs[i]
        for j in range(i + 1, len(troughs)):
            trough2_idx, trough2_price = troughs[j]
            
            price_diff = abs(trough1_price - trough2_price) / trough1_price
            if price_diff <= tolerance:
                # Проверяем, что между ними есть пик
                between = recent.iloc[trough1_idx : trough2_idx + 1]
                max_between = between["high"].max()
                if max_between > trough1_price * 1.02:  # Пик минимум на 2% выше
                    # Возвращаем абсолютные индексы из оригинального DataFrame
                    return (recent.index[trough1_idx], recent.index[trough2_idx])
    
    return None

