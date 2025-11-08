from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping

import pandas as pd


@dataclass(slots=True)
class TrendbarFrame:
    symbol: str
    period: str
    frame: pd.DataFrame


def to_dataframe(symbol: str, period: str, bars: Iterable[Mapping[str, object]]) -> TrendbarFrame:
    df = pd.DataFrame(bars)
    if df.empty:
        df = pd.DataFrame(columns=["utc_time", "open", "high", "low", "close", "volume"])
    if "utc_time" not in df.columns:
        raise ValueError("Bars payload must include 'utc_time' field.")
    df["utc_time"] = pd.to_datetime(df["utc_time"], utc=True)
    df = df.sort_values("utc_time").drop_duplicates(subset="utc_time")
    df["symbol"] = symbol
    df["period"] = period
    columns = ["utc_time", "symbol", "period", "open", "high", "low", "close", "volume"]
    df = df.reindex(columns=columns)
    return TrendbarFrame(symbol=symbol, period=period, frame=df)


def validate_continuity(
    trendbars: TrendbarFrame,
    max_gap: int = 3,
    *,
    strict: bool = True,
) -> MutableMapping[str, object]:
    df = trendbars.frame
    result: MutableMapping[str, object] = {
        "symbol": trendbars.symbol,
        "period": trendbars.period,
        "rows": int(len(df)),
        "start": df["utc_time"].min().isoformat() if not df.empty else None,
        "end": df["utc_time"].max().isoformat() if not df.empty else None,
        "max_gap_minutes": None,
        "duplicates": False,
        "gap_violation": False,
    }
    if df.empty:
        return result

    duplicates = df["utc_time"].duplicated().any()
    result["duplicates"] = bool(duplicates)

    deltas = df["utc_time"].diff().dropna().dt.total_seconds().div(60)
    result["max_gap_minutes"] = float(deltas.max()) if not deltas.empty else 0.0
    if duplicates:
        raise ValueError(f"Duplicate timestamps found for {trendbars.symbol} {trendbars.period}.")
    gap_limit = max_gap * _period_to_minutes(trendbars.period)
    if deltas.gt(gap_limit).any():
        result["gap_violation"] = True
        if strict:
            raise ValueError(
                f"Gaps exceed allowed threshold for {trendbars.symbol} {trendbars.period}: "
                f"max gap {result['max_gap_minutes']} min"
            )
    return result


def save_jsonl(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path, orient="records", lines=True, force_ascii=False, date_format="iso")


def save_parquet(trendbars: TrendbarFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trendbars.frame.to_parquet(path, index=False)


def append_parquet(trendbars: TrendbarFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, trendbars.frame], ignore_index=True)
        combined = combined.drop_duplicates(subset="utc_time").sort_values("utc_time")
    else:
        combined = trendbars.frame
    combined.to_parquet(path, index=False)


def _period_to_minutes(period: str) -> int:
    mapping = {"m1": 1, "m5": 5, "m15": 15, "m30": 30, "h1": 60, "h4": 240, "d1": 1440}
    try:
        return mapping[period.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported period '{period}'.") from exc


