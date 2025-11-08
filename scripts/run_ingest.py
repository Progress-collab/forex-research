from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.data_pipeline import DataPipelineConfig, ingest_instrument_history, list_fx_instruments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Загрузка исторических данных по форекс-инструментам MOEX")
    parser.add_argument("--secid", help="Тикер инструмента (например, USD000UTSTOM)")
    parser.add_argument("--interval", type=int, default=24, help="Интервал свечей в часах (MOEX code)")
    parser.add_argument("--start", type=str, help="Дата начала YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="Дата окончания YYYY-MM-DD")
    parser.add_argument("--list", action="store_true", help="Показать доступные инструменты и завершить")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = DataPipelineConfig()

    if args.list:
        instruments = list_fx_instruments(config)
        print(json.dumps(instruments, ensure_ascii=False, indent=2))
        return

    if not args.secid:
        raise SystemExit("Необходимо указать --secid или использовать --list для просмотра доступных инструментов")

    start_dt = datetime.fromisoformat(args.start) if args.start else None
    end_dt = datetime.fromisoformat(args.end) if args.end else None

    report = ingest_instrument_history(
        config=config,
        secid=args.secid,
        interval=args.interval,
        start=start_dt,
        end=end_dt,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

