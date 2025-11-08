from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
from src.data_pipeline.symbol_info import SymbolInfoCache


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Обновление справочной информации о символах FXPro (swaps, комиссии).")
    parser.add_argument(
        "--output",
        default="data/v1/ref/symbols_info.json",
        help="Путь к файлу для сохранения информации о символах.",
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

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=args.environment,
    )

    cache_path = Path(args.output)
    # Создаём fetcher, который автоматически создаст кэш с нужным путём
    # Но нужно передать путь в fetcher, что требует изменения класса
    # Пока используем простой подход: создаём fetcher, он создаст кэш, затем сохраним
    fetcher = CTraderTrendbarFetcher(creds)
    try:
        # Ждём загрузки символов
        import time

        time.sleep(5)  # Даём время на загрузку символов
        # Кэш автоматически обновится через _handle_symbols_list
        # Сохраняем через close()
    finally:
        fetcher.close()  # Это сохранит кэш
    
    # Пересохраняем в нужное место, если путь отличается
    if fetcher._symbol_info_cache._cache_path != cache_path:
        fetcher._symbol_info_cache._cache_path = cache_path
        fetcher._symbol_info_cache.save()
    
    print(f"Обновлена информация о символах")
    print(f"Сохранено в {cache_path}")


if __name__ == "__main__":
    main()

