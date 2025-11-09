"""
Скрипт для массовой загрузки исторических данных из cTrader API за 7 лет.
Таймфреймы: D1, H1, H4, M15
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from dotenv import load_dotenv

from src.data_pipeline.ctrader_backfill import build_raw_path, fetch_range, iso_to_datetime
from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.curation import (
    append_parquet,
    save_jsonl,
    validate_continuity,
)


log = logging.getLogger("download_7years_ctrader")

# Основные валютные пары для загрузки
DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF", "AUDCAD", "CADJPY"
]

# Таймфреймы для загрузки
DEFAULT_PERIODS = ["d1", "h1", "h4", "m15"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Массовая загрузка исторических данных из cTrader за 7 лет."
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help=f"Список символов (по умолчанию: {', '.join(DEFAULT_SYMBOLS[:5])}...)",
    )
    parser.add_argument(
        "--periods",
        nargs="+",
        default=DEFAULT_PERIODS,
        help=f"Периоды баров (по умолчанию: {', '.join(DEFAULT_PERIODS)})",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=7,
        help="Количество лет исторических данных (по умолчанию 7)",
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
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Пропускать символы/периоды, для которых уже есть данные",
    )
    return parser.parse_args()


def check_existing_data(curated_dir: Path, symbol: str, period: str) -> bool:
    """Проверяет, существует ли уже файл с данными."""
    curated_path = curated_dir / f"{symbol}_{period}.parquet"
    return curated_path.exists() and curated_path.stat().st_size > 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    args = parse_args()
    load_dotenv()

    # Вычисляем дату начала (7 лет назад от текущей даты)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.years * 365)
    
    log.info("Загрузка данных за период: %s -> %s", start.isoformat(), end.isoformat())
    log.info("Символы: %s", ", ".join(args.symbols))
    log.info("Периоды: %s", ", ".join(args.periods))

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=args.environment,
    )

    fetcher = CTraderTrendbarFetcher(creds)
    raw_dir = Path(args.raw_dir)
    curated_dir = Path(args.curated_dir)
    
    # Создаем директории если их нет
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    total_tasks = len(args.symbols) * len(args.periods)
    completed = 0
    skipped = 0
    errors = 0

    try:
        for symbol in args.symbols:
            for period in args.periods:
                completed += 1
                log.info(
                    "[%d/%d] Обработка %s %s",
                    completed,
                    total_tasks,
                    symbol,
                    period
                )

                # Проверяем существующие данные
                if args.skip_existing and check_existing_data(curated_dir, symbol, period):
                    log.info("Пропускаем %s %s - данные уже существуют", symbol, period)
                    skipped += 1
                    continue

                try:
                    log.info(
                        "Загрузка %s %s [%s -> %s]",
                        symbol,
                        period,
                        start.isoformat(),
                        end.isoformat()
                    )
                    frame = fetch_range(fetcher, symbol, period, start, end, args.chunk_size)
                    summary = validate_continuity(frame, strict=False)
                    
                    log.info(
                        "Загружено %s строк для %s %s (максимальный разрыв %.2f мин)",
                        summary["rows"],
                        symbol,
                        period,
                        summary["max_gap_minutes"] or 0.0,
                    )
                    
                    if summary.get("gap_violation"):
                        log.warning(
                            "Обнаружено нарушение непрерывности для %s %s (максимальный разрыв %.2f мин)",
                            symbol,
                            period,
                            summary["max_gap_minutes"] or 0.0,
                        )
                    
                    if frame.frame.empty:
                        log.warning("Нет данных для %s %s", symbol, period)
                        errors += 1
                        continue

                    raw_path = build_raw_path(raw_dir, symbol, period, start, end)
                    save_jsonl(frame.frame, raw_path)
                    log.info("Сохранены сырые данные в %s", raw_path)

                    curated_path = curated_dir / f"{symbol}_{period}.parquet"
                    append_parquet(frame, curated_path)
                    log.info("Обновлен очищенный датасет %s", curated_path)
                    
                except Exception as e:
                    log.error(
                        "Ошибка при загрузке %s %s: %s",
                        symbol,
                        period,
                        str(e),
                        exc_info=True
                    )
                    errors += 1

        log.info("=" * 60)
        log.info("Загрузка завершена!")
        log.info("Всего задач: %d", total_tasks)
        log.info("Успешно: %d", total_tasks - skipped - errors)
        log.info("Пропущено: %d", skipped)
        log.info("Ошибок: %d", errors)
        log.info("=" * 60)

    finally:
        fetcher.close()


if __name__ == "__main__":
    main()

