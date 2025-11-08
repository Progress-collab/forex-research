from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from src.data_pipeline.ctrader_client import CTraderTrendbarFetcher, TREND_BAR_PERIODS
from src.data_pipeline.curation import TrendbarFrame, to_dataframe


def iso_to_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def period_duration(period: str) -> timedelta:
    mapping = {
        "m1": timedelta(minutes=1),
        "m5": timedelta(minutes=5),
        "m15": timedelta(minutes=15),
        "m30": timedelta(minutes=30),
        "h1": timedelta(hours=1),
        "h4": timedelta(hours=4),
        "d1": timedelta(days=1),
    }
    try:
        return mapping[period.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported period '{period}'.") from exc


def fetch_range(
    fetcher: CTraderTrendbarFetcher,
    symbol: str,
    period: str,
    start: datetime,
    end: datetime,
    chunk_size: int,
) -> TrendbarFrame:
    if period.lower() not in TREND_BAR_PERIODS:
        raise ValueError(f"Unsupported period {period}")

    all_bars: List[Dict[str, object]] = []
    to_time = end

    while to_time > start:
        bars = fetcher.get_trendbars(symbol=symbol, period=period, bars=chunk_size, to_time=to_time)
        if not bars:
            break

        all_bars.extend(bars)
        oldest = min(bar["utc_time"] for bar in bars)
        oldest_dt = iso_to_datetime(oldest)
        if oldest_dt <= start:
            break
        to_time = oldest_dt - period_duration(period)
        if to_time <= start:
            break

    frame = to_dataframe(symbol, period, all_bars)
    frame.frame = frame.frame[frame.frame["utc_time"].between(start, end)]
    return frame


def build_raw_path(root: Path, symbol: str, period: str, start: datetime, end: datetime) -> Path:
    root = root / symbol / period
    filename = f"{symbol}_{period}_{start:%Y%m%d}_{end:%Y%m%d}.jsonl"
    return root / filename

