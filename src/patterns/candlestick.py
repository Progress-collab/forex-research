"""
Распознавание свечных паттернов на основе логики Patternz.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def detect_hammer(df: pd.DataFrame, lookback: int = 20) -> Optional[int]:
    """
    Обнаруживает паттерн Hammer (молот).
    
    Условия из Patternz:
    - Нисходящий тренд (цена ниже предыдущей)
    - Верхняя тень <= 5% от высоты свечи ИЛИ на вершине
    - Нижняя тень >= 2x высоты тела И <= 3x высоты тела
    - Маленькое тело (меньше средней высоты тела за период)
    
    Args:
        df: DataFrame с колонками open, high, low, close
        lookback: Количество последних свечей для анализа
    
    Returns:
        Индекс свечи с паттерном или None
    """
    if len(df) < 2:
        return None
    
    # Берем последние свечи
    recent = df.tail(lookback).copy()
    
    for i in range(1, len(recent)):
        idx = recent.index[i]
        prev_idx = recent.index[i - 1]
        
        # Текущая свеча
        open_price = recent.loc[idx, "open"]
        close_price = recent.loc[idx, "close"]
        high_price = recent.loc[idx, "high"]
        low_price = recent.loc[idx, "low"]
        
        # Предыдущая свеча
        prev_close = recent.loc[prev_idx, "close"]
        
        # Проверяем нисходящий тренд
        if close_price >= prev_close:
            continue
        
        # Вычисляем характеристики свечи
        body_height = abs(close_price - open_price)
        candle_height = high_price - low_price
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        
        if candle_height == 0:
            continue
        
        # Проверяем условия Hammer
        upper_shadow_pct = upper_shadow / candle_height if candle_height > 0 else 0
        lower_to_body = lower_shadow / body_height if body_height > 0 else 0
        
        # Маленькое тело (меньше средней высоты тела за период)
        avg_body = recent["close"].sub(recent["open"]).abs().tail(20).mean()
        is_small_body = body_height <= avg_body * 1.3 if avg_body > 0 else True
        
        # Условия Hammer из Patternz
        if (
            upper_shadow_pct <= 0.05 and  # Верхняя тень <= 5%
            2.0 <= lower_to_body <= 3.0 and  # Нижняя тень 2-3x тела
            is_small_body
        ):
            return idx
    
    return None


def detect_engulfing(df: pd.DataFrame, bullish: bool = True) -> Optional[int]:
    """
    Обнаруживает паттерн Engulfing (поглощение).
    
    Bullish Engulfing:
    - Вчера: черная свеча (close < open)
    - Сегодня: белая свеча (close > open)
    - Сегодняшний open <= вчерашний close
    - Сегодняшний close >= вчерашний open
    - Хотя бы одно неравенство строгое
    
    Bearish Engulfing:
    - Вчера: белая свеча (close > open)
    - Сегодня: черная свеча (close < open)
    - Сегодняшний open >= вчерашний close
    - Сегодняшний close <= вчерашний open
    - Хотя бы одно неравенство строгое
    
    Args:
        df: DataFrame с колонками open, high, low, close
        bullish: True для Bullish Engulfing, False для Bearish
    
    Returns:
        Индекс свечи с паттерном или None
    """
    if len(df) < 2:
        return None
    
    recent = df.tail(20).copy()
    
    for i in range(1, len(recent)):
        idx = recent.index[i]
        prev_idx = recent.index[i - 1]
        
        # Текущая свеча
        open_today = recent.loc[idx, "open"]
        close_today = recent.loc[idx, "close"]
        
        # Предыдущая свеча
        open_yesterday = recent.loc[prev_idx, "open"]
        close_yesterday = recent.loc[prev_idx, "close"]
        
        if bullish:
            # Bullish Engulfing
            is_yesterday_black = close_yesterday < open_yesterday
            is_today_white = close_today > open_today
            
            if (
                is_yesterday_black
                and is_today_white
                and open_today <= close_yesterday
                and close_today >= open_yesterday
                and (open_today < close_yesterday or close_today > open_yesterday)
            ):
                return idx
        else:
            # Bearish Engulfing
            is_yesterday_white = close_yesterday > open_yesterday
            is_today_black = close_today < open_today
            
            if (
                is_yesterday_white
                and is_today_black
                and open_today >= close_yesterday
                and close_today <= open_yesterday
                and (open_today > close_yesterday or close_today < open_yesterday)
            ):
                return idx
    
    return None


def detect_doji(df: pd.DataFrame, doji_range: float = 0.01) -> Optional[int]:
    """
    Обнаруживает паттерн Doji.
    
    Условия:
    - Тело свечи очень маленькое (open ≈ close)
    - Отношение тела к диапазону свечи <= doji_range (по умолчанию 1%)
    
    Args:
        df: DataFrame с колонками open, high, low, close
        doji_range: Максимальное отношение тела к диапазону (0.01 = 1%)
    
    Returns:
        Индекс свечи с паттерном или None
    """
    if len(df) < 1:
        return None
    
    recent = df.tail(20).copy()
    
    for idx in recent.index:
        open_price = recent.loc[idx, "open"]
        close_price = recent.loc[idx, "close"]
        high_price = recent.loc[idx, "high"]
        low_price = recent.loc[idx, "low"]
        
        body_height = abs(close_price - open_price)
        candle_height = high_price - low_price
        
        if candle_height == 0:
            continue
        
        body_ratio = body_height / candle_height
        
        # Doji: тело <= doji_range от диапазона свечи
        if body_ratio <= doji_range:
            return idx
    
    return None

