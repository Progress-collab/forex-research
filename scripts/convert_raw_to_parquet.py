"""Конвертация raw JSONL данных в parquet формат."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.data_pipeline.curation import TrendbarFrame, append_parquet, to_dataframe


def convert_raw_to_parquet(symbol: str, period: str = "m15") -> None:
    """Конвертирует raw JSONL данные в parquet."""
    raw_path = Path(f"data/v1/raw/ctrader/{symbol}/{period}")
    jsonl_files = list(raw_path.glob("*.jsonl"))
    
    if not jsonl_files:
        print(f"Нет raw данных для {symbol} {period}")
        return
    
    print(f"Обработка {symbol} {period}...")
    all_bars = []
    for jsonl_file in jsonl_files:
        with jsonl_file.open("r", encoding="utf-8") as fp:
            for line in fp:
                all_bars.append(json.loads(line))
    
    frame = to_dataframe(symbol, period, all_bars)
    curated_path = Path(f"data/v1/curated/ctrader/{symbol}_{period}.parquet")
    curated_path.parent.mkdir(parents=True, exist_ok=True)
    append_parquet(frame, curated_path)
    print(f"Сохранено {symbol} в {curated_path} ({len(frame.frame)} строк)")


if __name__ == "__main__":
    for symbol in ["EURUSD", "USDJPY", "GBPUSD"]:
        convert_raw_to_parquet(symbol, "m15")

