from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from prefect import flow, task

from src.data_pipeline.ctrader_backfill import build_raw_path, fetch_range
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import append_parquet, save_jsonl, validate_continuity

DEFAULT_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "XAUUSD")
DEFAULT_PERIODS = ("m1", "m5", "m15")


@task
def _load_credentials(environment: str = "live") -> CTraderCredentials:
    load_dotenv()
    return CTraderCredentials(
        client_id=_env("CTRADER_CLIENT_ID"),
        client_secret=_env("CTRADER_CLIENT_SECRET"),
        access_token=_env("CTRADER_ACCESS_TOKEN"),
        refresh_token=_env("CTRADER_REFRESH_TOKEN", required=False),
        environment=environment,
    )


@task
def _collect_day(
    creds: CTraderCredentials,
    symbol: str,
    period: str,
    day: datetime,
    chunk_size: int,
    raw_root: Path,
    curated_root: Path,
) -> None:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    fetcher = CTraderTrendbarFetcher(creds)
    try:
        frame = fetch_range(fetcher, symbol, period, start, end, chunk_size)
    finally:
        fetcher.close()

    summary = validate_continuity(frame)
    raw_path = build_raw_path(raw_root, symbol, period, start, end)
    save_jsonl(frame.frame, raw_path)
    curated_path = curated_root / f"{symbol}_{period}.parquet"
    append_parquet(frame, curated_path)
    from prefect import get_run_logger

    logger = get_run_logger()
    logger.info(
        "Collected %s rows for %s %s (%s - %s, max gap %.2f)",
        summary["rows"],
        symbol,
        period,
        summary["start"],
        summary["end"],
        summary["max_gap_minutes"] or 0.0,
    )


@flow(name="ctrader-daily-backfill")
def ctrader_daily_backfill(
    symbols: Iterable[str] = DEFAULT_SYMBOLS,
    periods: Iterable[str] = DEFAULT_PERIODS,
    days_back: int = 1,
    chunk_size: int = 500,
    raw_dir: str = "data/v1/raw/ctrader",
    curated_dir: str = "data/v1/curated/ctrader",
    environment: str = "live",
) -> None:
    creds = _load_credentials(environment)
    today = datetime.utcnow().replace(tzinfo=timezone.utc, hour=0, minute=0, second=0, microsecond=0)
    raw_root = Path(raw_dir)
    curated_root = Path(curated_dir)

    for offset in range(days_back):
        day = today - timedelta(days=offset)
        for symbol in symbols:
            for period in periods:
                _collect_day.submit(
                    creds,
                    symbol,
                    period,
                    day,
                    chunk_size,
                    raw_root,
                    curated_root,
                )


def _env(name: str, required: bool = True) -> str:
    value = os.getenv(name)
    if value is None:
        if required:
            raise RuntimeError(f"Environment variable {name} is required for cTrader flow.")
        return ""
    return value


if __name__ == "__main__":
    ctrader_daily_backfill()

