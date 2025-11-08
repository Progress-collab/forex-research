from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.data_pipeline.gap_analysis import analyze_gaps, classify_gaps


def analyze_all_gaps(
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    symbols: List[str] | None = None,
    periods: List[str] | None = None,
    output_path: Path = Path("data/v1/reports/gap_analysis_report.json"),
) -> Dict:
    """
    Анализирует разрывы для всех символов и периодов.
    """
    if symbols is None:
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    if periods is None:
        periods = ["m5", "m15", "h1"]

    period_minutes = {"m5": 5, "m15": 15, "m30": 30, "h1": 60, "h4": 240, "d1": 1440}

    report = {
        "generated_at": datetime.now().isoformat(),
        "symbols": {},
    }

    for symbol in symbols:
        report["symbols"][symbol] = {}
        for period in periods:
            file_path = curated_dir / f"{symbol}_{period}.parquet"
            if not file_path.exists():
                report["symbols"][symbol][period] = {"status": "missing", "error": "File not found"}
                continue

            try:
                df = pd.read_parquet(file_path)
                df["utc_time"] = pd.to_datetime(df["utc_time"])
                df = df.sort_values("utc_time")

                if df.empty:
                    report["symbols"][symbol][period] = {"status": "empty", "rows": 0}
                    continue

                minutes = period_minutes.get(period, 15)
                gaps = analyze_gaps(df, minutes)
                classification = classify_gaps(gaps, symbol)

                start = df["utc_time"].min().isoformat()
                end = df["utc_time"].max().isoformat()
                days = (df["utc_time"].max() - df["utc_time"].min()).days

                report["symbols"][symbol][period] = {
                    "status": "ok",
                    "rows": len(df),
                    "start": start,
                    "end": end,
                    "days": days,
                    "total_gaps": classification["total"],
                    "weekend_gaps": len(classification["weekend"]),
                    "suspicious_gaps": len(classification["suspicious"]),
                    "suspicious_gaps_details": [
                        {
                            "start": start_gap.isoformat(),
                            "end": end_gap.isoformat(),
                            "duration_hours": duration.total_seconds() / 3600,
                        }
                        for start_gap, end_gap, duration in classification["suspicious"]
                    ],
                }
                logging.info(
                    "%s %s: %s строк, %s дней, %s подозрительных разрывов",
                    symbol,
                    period,
                    len(df),
                    days,
                    len(classification["suspicious"]),
                )
            except Exception as e:  # noqa: BLE001
                logging.error("Ошибка при анализе %s %s: %s", symbol, period, e)
                report["symbols"][symbol][period] = {"status": "error", "error": str(e)}

    # Сохраняем отчет
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    logging.info("Отчет сохранен в %s", output_path)
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Массовый анализ разрывов данных.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
        help="Список символов для анализа.",
    )
    parser.add_argument(
        "--periods",
        nargs="+",
        default=["m5", "m15", "h1"],
        help="Периоды для анализа.",
    )
    parser.add_argument(
        "--curated-dir",
        default="data/v1/curated/ctrader",
        help="Каталог с curated данными.",
    )
    parser.add_argument(
        "--output",
        default="data/v1/reports/gap_analysis_report.json",
        help="Путь к файлу отчета.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    analyze_all_gaps(
        curated_dir=Path(args.curated_dir),
        symbols=args.symbols,
        periods=args.periods,
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()

