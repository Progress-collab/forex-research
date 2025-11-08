from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from src.data_pipeline.ctrader_backfill import fetch_range, iso_to_datetime
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import TrendbarFrame, append_parquet, save_jsonl, validate_continuity
from src.data_pipeline.gap_analysis import analyze_gaps, classify_gaps, generate_backfill_requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Анализ разрывов и дозагрузка пропущенных данных.")
    parser.add_argument("--symbol", required=True, help="Символ (например EURUSD).")
    parser.add_argument("--period", default="m15", help="Период баров (m1, m5, m15, m30, h1, h4, d1).")
    parser.add_argument(
        "--curated-path",
        default="data/v1/curated/ctrader",
        help="Путь к curated данным.",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/v1/raw/ctrader",
        help="Каталог для сохранения сырых JSONL.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=200,
        help="Количество баров за запрос для дозагрузки.",
    )
    parser.add_argument(
        "--environment",
        default="live",
        choices=("live", "demo"),
        help="Окружение cTrader.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Только анализ, без дозагрузки.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    load_dotenv()

    curated_path = Path(args.curated_path) / f"{args.symbol}_{args.period}.parquet"
    if not curated_path.exists():
        logging.error("Не найден файл %s", curated_path)
        return

    df = pd.read_parquet(curated_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.sort_values("utc_time")

    period_minutes = {"m1": 1, "m5": 5, "m15": 15, "m30": 30, "h1": 60, "h4": 240, "d1": 1440}[args.period]
    gaps = analyze_gaps(df, period_minutes)
    classification = classify_gaps(gaps, args.symbol)

    logging.info("Анализ разрывов для %s %s:", args.symbol, args.period)
    logging.info("  Всего разрывов: %s", classification["total"])
    logging.info("  Выходные: %s", len(classification["weekend"]))
    logging.info("  Подозрительные (>72ч): %s", len(classification["suspicious"]))

    if classification["suspicious"]:
        logging.warning("Обнаружены подозрительные разрывы:")
        for start, end, duration in classification["suspicious"]:
            logging.warning("  %s -> %s (длительность: %s)", start, end, duration)

    if args.dry_run:
        logging.info("Dry-run режим: дозагрузка не выполняется")
        return

    # Генерируем запросы для дозагрузки (исключая выходные)
    backfill_requests = generate_backfill_requests(classification["suspicious"], args.period, args.chunk_size)
    if not backfill_requests:
        logging.info("Нет данных для дозагрузки")
        return

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=args.environment,
    )

    fetcher = CTraderTrendbarFetcher(creds)
    try:
        for start, end in backfill_requests:
            logging.info("Дозагрузка %s %s [%s -> %s]", args.symbol, args.period, start.isoformat(), end.isoformat())
            frame = fetch_range(fetcher, args.symbol, args.period, start, end, args.chunk_size)
            if frame.frame.empty:
                logging.warning("Не получены данные для периода %s -> %s", start, end)
                continue

            # Сохраняем в raw
            from src.data_pipeline.ctrader_backfill import build_raw_path

            raw_path = build_raw_path(Path(args.raw_dir), args.symbol, args.period, start, end)
            from src.data_pipeline.curation import save_jsonl

            save_jsonl(frame.frame, raw_path)
            logging.info("Сохранено в %s", raw_path)

            # Обновляем curated
            append_parquet(frame, curated_path)
            logging.info("Обновлён curated файл %s", curated_path)

        # Финальная проверка
        df_updated = pd.read_parquet(curated_path)
        df_updated["utc_time"] = pd.to_datetime(df_updated["utc_time"])
        frame_updated = TrendbarFrame(symbol=args.symbol, period=args.period, frame=df_updated)
        summary = validate_continuity(frame_updated, strict=False)
        logging.info("Финальная статистика: %s строк, макс. разрыв %.2f мин", summary["rows"], summary.get("max_gap_minutes", 0))
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()

