from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.data_pipeline.ctrader_backfill import build_raw_path, fetch_range
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import append_parquet, save_jsonl, validate_continuity


def main() -> None:
    load_dotenv()

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment="live",
    )

    # Дозагрузка XAUUSD m15 с 2024-11-08 до 2025-07-06
    start = datetime(2024, 11, 8, 8, 0, tzinfo=timezone.utc)
    end = datetime(2025, 7, 6, 22, 0, tzinfo=timezone.utc)

    print(f"Дозагрузка XAUUSD m15 с {start} до {end}")

    fetcher = CTraderTrendbarFetcher(creds)
    try:
        frame = fetch_range(fetcher, "XAUUSD", "m15", start, end, chunk_size=200)
        if frame.frame.empty:
            print("Нет данных для загрузки")
            return

        summary = validate_continuity(frame, strict=False)
        print(f"Загружено {summary['rows']} строк (макс. разрыв {summary.get('max_gap_minutes', 0):.2f} мин)")

        raw_path = build_raw_path(Path("data/v1/raw/ctrader"), "XAUUSD", "m15", start, end)
        save_jsonl(frame.frame, raw_path)
        print(f"Сохранено в {raw_path}")

        curated_path = Path("data/v1/curated/ctrader/XAUUSD_m15.parquet")
        append_parquet(frame, curated_path)
        print(f"Обновлён curated: {curated_path}")

        # Попробуем загрузить XAUUSD m5
        print("\nПопытка загрузки XAUUSD m5 за последние 5 дней...")
        start_m5 = datetime(2025, 11, 3, 0, 0, tzinfo=timezone.utc)
        end_m5 = datetime(2025, 11, 8, 0, 0, tzinfo=timezone.utc)
        frame_m5 = fetch_range(fetcher, "XAUUSD", "m5", start_m5, end_m5, chunk_size=200)
        if frame_m5.frame.empty:
            print("XAUUSD m5 недоступен через API")
        else:
            print(f"XAUUSD m5 доступен! Загружено {len(frame_m5.frame)} строк")
            raw_path_m5 = build_raw_path(Path("data/v1/raw/ctrader"), "XAUUSD", "m5", start_m5, end_m5)
            save_jsonl(frame_m5.frame, raw_path_m5)
            curated_path_m5 = Path("data/v1/curated/ctrader/XAUUSD_m5.parquet")
            append_parquet(frame_m5, curated_path_m5)
            print(f"Сохранено XAUUSD m5 в {curated_path_m5}")
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()

