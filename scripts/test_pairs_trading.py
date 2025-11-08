from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.data_pipeline.pairs_utils import (
    compute_spread,
    compute_zscore,
    find_pairs_candidates,
    load_pair_data,
)


def test_pairs_trading(
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    period: str = "m15",
    pairs: List[tuple[str, str]] | None = None,
    output_path: Path = Path("data/v1/reports/pairs_analysis.json"),
) -> Dict:
    """
    Тестирует pairs trading на синхронизированных данных.
    """
    if pairs is None:
        pairs = [("EURUSD", "GBPUSD"), ("EURUSD", "USDJPY")]

    report = {
        "period": period,
        "pairs": {},
        "candidates": [],
    }

    # Анализ указанных пар
    for symbol1, symbol2 in pairs:
        logging.info("Анализ пары %s/%s", symbol1, symbol2)
        try:
            df_pair = load_pair_data(symbol1, symbol2, period, curated_dir)
            if df_pair is None:
                report["pairs"][f"{symbol1}/{symbol2}"] = {"status": "error", "error": "Failed to load data"}
                continue

            spread = compute_spread(df_pair, symbol1, symbol2, method="ratio")
            zscore = compute_zscore(spread, window=100)

            # Статистика
            spread_mean = float(spread.mean())
            spread_std = float(spread.std())
            zscore_mean = float(zscore.mean())
            zscore_std = float(zscore.std())
            zscore_max = float(zscore.max())
            zscore_min = float(zscore.min())

            # Подсчет сигналов (zscore > 2 или < -2)
            signals_long = int((zscore < -2).sum())  # Покупка когда спред низкий
            signals_short = int((zscore > 2).sum())  # Продажа когда спред высокий

            report["pairs"][f"{symbol1}/{symbol2}"] = {
                "status": "ok",
                "rows": len(df_pair),
                "spread_mean": spread_mean,
                "spread_std": spread_std,
                "zscore_mean": zscore_mean,
                "zscore_std": zscore_std,
                "zscore_max": zscore_max,
                "zscore_min": zscore_min,
                "signals_long": signals_long,
                "signals_short": signals_short,
                "total_signals": signals_long + signals_short,
            }

            logging.info(
                "  %s/%s: %s строк, zscore диапазон [%.2f, %.2f], сигналов: %s",
                symbol1,
                symbol2,
                len(df_pair),
                zscore_min,
                zscore_max,
                signals_long + signals_short,
            )
        except Exception as e:  # noqa: BLE001
            logging.error("Ошибка при анализе пары %s/%s: %s", symbol1, symbol2, e)
            report["pairs"][f"{symbol1}/{symbol2}"] = {"status": "error", "error": str(e)}

    # Поиск кандидатов
    logging.info("Поиск кандидатов для pairs trading...")
    try:
        candidates = find_pairs_candidates(curated_dir, period, min_correlation=0.7)
        report["candidates"] = [
            {"symbol1": s1, "symbol2": s2, "correlation": float(corr)} for s1, s2, corr in candidates
        ]
        logging.info("Найдено %s кандидатов", len(candidates))
        for s1, s2, corr in candidates[:5]:  # Показываем топ-5
            logging.info("  %s/%s: корреляция %.3f", s1, s2, corr)
    except Exception as e:  # noqa: BLE001
        logging.error("Ошибка при поиске кандидатов: %s", e)
        report["candidates_error"] = str(e)

    # Сохраняем отчет
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    logging.info("Отчет сохранен в %s", output_path)
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Тестирование pairs trading.")
    parser.add_argument(
        "--period",
        default="m15",
        help="Период для анализа (m5, m15, h1).",
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        help="Пары для анализа в формате SYMBOL1/SYMBOL2 (например EURUSD/GBPUSD).",
    )
    parser.add_argument(
        "--curated-dir",
        default="data/v1/curated/ctrader",
        help="Каталог с curated данными.",
    )
    parser.add_argument(
        "--output",
        default="data/v1/reports/pairs_analysis.json",
        help="Путь к файлу отчета.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    pairs = None
    if args.pairs:
        pairs = [tuple(pair.split("/")) for pair in args.pairs]

    test_pairs_trading(
        curated_dir=Path(args.curated_dir),
        period=args.period,
        pairs=pairs,
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()

