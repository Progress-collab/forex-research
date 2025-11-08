from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Выгрузка исторических баров из cTrader Open API.")
    parser.add_argument("--symbol", required=True, help="Символ, например EURUSD.")
    parser.add_argument("--period", default="m15", help="Период: m1, m5, m15, m30, h1, h4, d1.")
    parser.add_argument("--bars", type=int, default=500, help="Количество баров (по умолчанию 500).")
    parser.add_argument(
        "--output",
        default="data/v1/raw/ctrader_trendbars.jsonl",
        help="Путь к файлу JSONL для сохранения баров.",
    )
    parser.add_argument(
        "--environment",
        default="live",
        choices=("live", "demo"),
        help="Окружение cTrader Open API (по умолчанию live).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    args = parse_args()
    load_dotenv()

    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment=args.environment,
    )

    fetcher = CTraderTrendbarFetcher(creds)
    try:
        bars = fetcher.get_trendbars(symbol=args.symbol, period=args.period, bars=args.bars)
    finally:
        fetcher.close()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        for bar in bars:
            fp.write(json.dumps(bar, ensure_ascii=False))
            fp.write("\n")

    print(f"Сохранено {len(bars)} баров в {output_path}")


if __name__ == "__main__":
    main()

