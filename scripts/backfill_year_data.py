from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from dotenv import load_dotenv

from src.data_pipeline.ctrader_backfill import build_raw_path, fetch_range, iso_to_datetime
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import append_parquet, save_jsonl, validate_continuity


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Массовая загрузка исторических данных FXPro за год.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
        help="Список символов.",
    )
    parser.add_argument(
        "--periods",
        nargs="+",
        default=["m1", "m5", "m15", "h1"],
        help="Периоды баров (m1, m5, m15, m30, h1, h4, d1).",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=1,
        help="Количество лет истории (по умолчанию 1).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=200,
        help="Количество баров за запрос (200 по умолчанию для меньших разрывов).",
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
        help="Окружение cTrader.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    load_dotenv()

    end = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = end - timedelta(days=365 * args.years)

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=args.environment,
    )

    fetcher = CTraderTrendbarFetcher(creds)
    try:
        total_combinations = len(args.symbols) * len(args.periods)
        current = 0
        for symbol in args.symbols:
            for period in args.periods:
                current += 1
                logging.info(
                    "[%s/%s] Загрузка %s %s [%s -> %s]",
                    current,
                    total_combinations,
                    symbol,
                    period,
                    start.isoformat(),
                    end.isoformat(),
                )
                try:
                    frame = fetch_range(fetcher, symbol, period, start, end, args.chunk_size)
                    if frame.frame.empty:
                        logging.warning("Нет данных для %s %s", symbol, period)
                        continue

                    summary = validate_continuity(frame, strict=False)  # Не падаем на выходных разрывах
                    logging.info(
                        "Загружено %s строк для %s %s (макс. разрыв %.2f мин)",
                        summary["rows"],
                        symbol,
                        period,
                        summary.get("max_gap_minutes", 0),
                    )

                    raw_path = build_raw_path(Path(args.raw_dir), symbol, period, start, end)
                    save_jsonl(frame.frame, raw_path)
                    logging.info("Сохранено raw: %s", raw_path)

                    curated_path = Path(args.curated_dir) / f"{symbol}_{period}.parquet"
                    append_parquet(frame, curated_path)
                    logging.info("Обновлён curated: %s", curated_path)
                except Exception as e:  # noqa: BLE001
                    logging.error("Ошибка при загрузке %s %s: %s", symbol, period, e, exc_info=True)
                    continue
    finally:
        fetcher.close()
    logging.info("Загрузка завершена")


if __name__ == "__main__":
    main()

