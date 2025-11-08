from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from src.data_pipeline.ctrader_backfill import build_raw_path, fetch_range, iso_to_datetime
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import (
    append_parquet,
    save_jsonl,
    validate_continuity,
)


log = logging.getLogger("backfill_ctrader_history")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Бэктестовая выгрузка исторических баров из cTrader.")
    parser.add_argument("--symbols", nargs="+", required=True, help="Список символов FXPro (например EURUSD GBPUSD).")
    parser.add_argument(
        "--periods",
        nargs="+",
        default=["m15"],
        help="Периоды баров (m1, m5, m15, m30, h1, h4, d1). Можно указать несколько.",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Начало периода в ISO формате (например 2025-05-01T00:00:00Z или 2025-05-01).",
    )
    parser.add_argument(
        "--end",
        default=datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        help="Окончание периода в ISO (по умолчанию текущее UTC время).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Количество баров за запрос (500 по умолчанию).",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/v1/raw/ctrader",
        help="Каталог для сохранения сырых JSONL.",
    )
    parser.add_argument(
        "--curated-dir",
        default="data/v1/curated/ctrader",
        help="Каталог для сохранения очищенных parquet.",
    )
    parser.add_argument(
        "--environment",
        default="live",
        choices=("live", "demo"),
        help="Окружение cTrader (live или demo).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    load_dotenv()

    start = iso_to_datetime(args.start)
    end = iso_to_datetime(args.end)
    if start >= end:
        raise ValueError("Start must be earlier than end.")

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=args.environment,
    )

    fetcher = CTraderTrendbarFetcher(creds)
    try:
        for symbol in args.symbols:
            for period in args.periods:
                log.info("Fetching %s %s [%s -> %s]", symbol, period, start.isoformat(), end.isoformat())
                frame = fetch_range(fetcher, symbol, period, start, end, args.chunk_size)
                summary = validate_continuity(frame, strict=False)
                log.info(
                    "Fetched %s rows for %s %s (max gap %.2f min)",
                    summary["rows"],
                    symbol,
                    period,
                    summary["max_gap_minutes"] or 0.0,
                )
                if summary.get("gap_violation"):
                    log.warning(
                        "Gap violation detected for %s %s (max gap %.2f min)",
                        symbol,
                        period,
                        summary["max_gap_minutes"] or 0.0,
                    )
                if frame.frame.empty:
                    log.warning("No data received for %s %s", symbol, period)
                    continue

                raw_path = build_raw_path(Path(args.raw_dir), symbol, period, start, end)
                save_jsonl(frame.frame, raw_path)
                log.info("Saved raw data to %s", raw_path)

                curated_path = Path(args.curated_dir) / f"{symbol}_{period}.parquet"
                append_parquet(frame, curated_path)
                log.info("Updated curated dataset %s", curated_path)
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
