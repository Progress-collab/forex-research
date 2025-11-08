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

from src.data_pipeline.news_calendar import (
    ForexFactoryAdapter,
    TradingEconomicsAdapter,
    aggregate_events,
    load_events,
    save_events,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Обновление экономического календаря.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Количество дней вперед для загрузки событий.",
    )
    parser.add_argument(
        "--countries",
        nargs="+",
        default=["US", "EU", "GB", "JP"],
        help="Список стран для фильтрации событий.",
    )
    parser.add_argument(
        "--output",
        default="data/v1/raw/news/economic_calendar.jsonl",
        help="Путь к файлу для сохранения событий.",
    )
    args = parser.parse_args()

    load_dotenv()

    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=args.days)

    output_path = Path(args.output)

    # Загружаем существующие события
    existing_events = load_events(output_path)
    log.info("Загружено %s существующих событий", len(existing_events))

    # Загружаем из TradingEconomics
    te_adapter = TradingEconomicsAdapter()
    te_events = te_adapter.fetch_events(start_date=start_date, end_date=end_date, countries=args.countries)

    # Загружаем из ForexFactory (если реализовано)
    ff_adapter = ForexFactoryAdapter()
    ff_events = ff_adapter.fetch_events(start_date=start_date, end_date=end_date)

    # Объединяем события
    all_events = aggregate_events([existing_events, te_events, ff_events])

    # Фильтруем только будущие события и события за последние 7 дней
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
    filtered_events = [e for e in all_events if e.timestamp >= cutoff_date]

    # Сохраняем
    save_events(filtered_events, output_path)
    log.info("Обновлено: всего %s событий, новых: %s", len(filtered_events), len(filtered_events) - len(existing_events))


if __name__ == "__main__":
    main()

