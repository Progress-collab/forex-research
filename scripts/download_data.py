"""
Скрипт для загрузки исторических данных из cTrader API.
Проверяет наличие данных и загружает недостающие.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from dotenv import load_dotenv

from src.data_pipeline.ctrader_backfill import build_raw_path, fetch_range, iso_to_datetime
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import append_parquet, save_jsonl, validate_continuity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def check_data_exists(symbol: str, period: str, curated_dir: Path, min_days: int = 300) -> bool:
    """Проверяет наличие данных и их достаточность."""
    file_path = curated_dir / f"{symbol}_{period}.parquet"
    if not file_path.exists():
        return False
    
    try:
        import pandas as pd
        df = pd.read_parquet(file_path)
        if df.empty:
            return False
        
        df["utc_time"] = pd.to_datetime(df["utc_time"])
        days_covered = (df["utc_time"].max() - df["utc_time"].min()).days
        return days_covered >= min_days
    except Exception:
        return False


def download_data(
    symbols: list[str],
    periods: list[str],
    years: int = 1,
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    raw_dir: Path = Path("data/v1/raw/ctrader"),
    environment: str = "live",
) -> None:
    """Загружает исторические данные из cTrader API."""
    load_dotenv()
    
    # Проверяем наличие учетных данных
    required_vars = ["CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        log.error("Отсутствуют учетные данные cTrader. Создайте файл .env с переменными:")
        log.error("  CTRADER_CLIENT_ID")
        log.error("  CTRADER_CLIENT_SECRET")
        log.error("  CTRADER_ACCESS_TOKEN")
        log.error("  CTRADER_REFRESH_TOKEN (опционально)")
        log.error("\nСкопируйте .env.example в .env и заполните значения.")
        sys.exit(1)
    
    end = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = end - timedelta(days=365 * years)
    
    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=environment,
    )
    
    fetcher = CTraderTrendbarFetcher(creds)
    try:
        total = len(symbols) * len(periods)
        current = 0
        
        for symbol in symbols:
            for period in periods:
                current += 1
                
                # Проверяем наличие данных
                if check_data_exists(symbol, period, curated_dir):
                    log.info(
                        "[%s/%s] Данные для %s %s уже существуют, пропускаем",
                        current,
                        total,
                        symbol,
                        period,
                    )
                    continue
                
                log.info(
                    "[%s/%s] Загрузка %s %s [%s -> %s]",
                    current,
                    total,
                    symbol,
                    period,
                    start.isoformat(),
                    end.isoformat(),
                )
                
                try:
                    frame = fetch_range(fetcher, symbol, period, start, end, chunk_size=200)
                    if frame.frame.empty:
                        log.warning("Нет данных для %s %s", symbol, period)
                        continue
                    
                    summary = validate_continuity(frame, strict=False)
                    log.info(
                        "Загружено %s строк для %s %s (макс. разрыв %.2f мин)",
                        summary["rows"],
                        symbol,
                        period,
                        summary.get("max_gap_minutes", 0),
                    )
                    
                    # Сохраняем raw данные
                    raw_path = build_raw_path(raw_dir, symbol, period, start, end)
                    save_jsonl(frame.frame, raw_path)
                    log.info("Сохранено raw: %s", raw_path)
                    
                    # Сохраняем curated данные
                    curated_path = curated_dir / f"{symbol}_{period}.parquet"
                    curated_path.parent.mkdir(parents=True, exist_ok=True)
                    append_parquet(frame, curated_path)
                    log.info("Обновлён curated: %s", curated_path)
                    
                except Exception as e:
                    log.error("Ошибка при загрузке %s %s: %s", symbol, period, e, exc_info=True)
                    continue
    finally:
        fetcher.close()
    
    log.info("Загрузка завершена")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Загрузка исторических данных из cTrader API")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["EURUSD", "USDJPY", "GBPUSD"],
        help="Список символов для загрузки",
    )
    parser.add_argument(
        "--periods",
        nargs="+",
        default=["m15"],
        help="Периоды баров (m1, m5, m15, m30, h1, h4, d1)",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=1,
        help="Количество лет истории (по умолчанию 1)",
    )
    parser.add_argument(
        "--environment",
        default="live",
        choices=("live", "demo"),
        help="Окружение cTrader",
    )
    args = parser.parse_args()
    
    download_data(
        symbols=args.symbols,
        periods=args.periods,
        years=args.years,
        environment=args.environment,
    )

