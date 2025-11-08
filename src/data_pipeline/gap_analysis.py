from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

import pandas as pd

log = logging.getLogger(__name__)

# Forex market hours: Friday 22:00 UTC close, Sunday 22:00 UTC open
# Gold (XAUUSD) follows similar schedule
FOREX_WEEKEND_CLOSE = timedelta(hours=48)  # ~Friday 22:00 to Sunday 22:00 UTC


def is_forex_weekend(start: datetime, end: datetime) -> bool:
    """
    Проверяет, попадает ли разрыв на выходные forex (суббота-воскресенье).
    Forex закрывается в пятницу ~22:00 UTC и открывается в воскресенье ~22:00 UTC.
    """
    if end - start < timedelta(hours=20):
        return False
    start_weekday = start.weekday()
    end_weekday = end.weekday()
    # Пятница (4) -> воскресенье (6) или суббота (5) -> воскресенье (6)
    if start_weekday == 4 and end_weekday == 6:
        if start.hour >= 20 and end.hour >= 20:
            return True
    if start_weekday == 5 and end_weekday == 6:
        if end.hour >= 20:
            return True
    return False


def analyze_gaps(df: pd.DataFrame, period_minutes: int = 15) -> List[Tuple[datetime, datetime, timedelta]]:
    """
    Анализирует разрывы в данных и возвращает список (start, end, duration).
    """
    if df.empty or "utc_time" not in df.columns:
        return []
    df_sorted = df.sort_values("utc_time").copy()
    df_sorted["time_diff"] = df_sorted["utc_time"].diff()
    expected_interval = timedelta(minutes=period_minutes)
    threshold = expected_interval * 2  # Разрыв считается если > 2 интервалов
    gaps = df_sorted[df_sorted["time_diff"] > threshold]
    result = []
    for idx, row in gaps.iterrows():
        gap_start = df_sorted.loc[df_sorted.index[df_sorted.index < idx].max(), "utc_time"]
        gap_end = row["utc_time"]
        duration = row["time_diff"]
        result.append((gap_start, gap_end, duration))
    return result


def classify_gaps(gaps: List[Tuple[datetime, datetime, timedelta]], instrument: str) -> dict:
    """
    Классифицирует разрывы: выходные, праздники, проблемы API.
    """
    weekend_gaps = []
    suspicious_gaps = []
    for start, end, duration in gaps:
        if is_forex_weekend(start, end):
            weekend_gaps.append((start, end, duration))
        elif duration > timedelta(hours=72):
            suspicious_gaps.append((start, end, duration))
    return {
        "weekend": weekend_gaps,
        "suspicious": suspicious_gaps,
        "total": len(gaps),
    }


def generate_backfill_requests(
    gaps: List[Tuple[datetime, datetime, timedelta]], period: str, max_chunk_bars: int = 500
) -> List[Tuple[datetime, datetime]]:
    """
    Генерирует список запросов для дозагрузки пропущенных данных.
    """
    period_durations = {
        "m1": timedelta(minutes=1),
        "m5": timedelta(minutes=5),
        "m15": timedelta(minutes=15),
        "m30": timedelta(minutes=30),
        "h1": timedelta(hours=1),
        "h4": timedelta(hours=4),
        "d1": timedelta(days=1),
    }
    delta = period_durations.get(period.lower(), timedelta(minutes=15))
    max_duration = delta * max_chunk_bars
    requests = []
    for start, end, duration in gaps:
        if duration <= max_duration:
            requests.append((start, end))
        else:
            # Разбиваем большой разрыв на чанки
            current = start
            while current < end:
                chunk_end = min(current + max_duration, end)
                requests.append((current, chunk_end))
                current = chunk_end + delta
    return requests

