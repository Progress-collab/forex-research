from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()


def analyze_backtest_results(report_path: Path) -> Dict:
    """
    Анализирует результаты батч-бэктеста и выбирает лучшие стратегии.
    """
    with report_path.open("r", encoding="utf-8") as fp:
        results = json.load(fp)

    analysis = {
        "best_strategies": [],
        "summary": {},
        "recommendations": [],
    }

    # Собираем все результаты в таблицу
    rows = []
    for strategy_id, instruments in results.items():
        for instrument, periods in instruments.items():
            for period, metrics in periods.items():
                if "error" in metrics:
                    continue
                rows.append(
                    {
                        "strategy": strategy_id,
                        "instrument": instrument,
                        "period": period,
                        "trades": metrics.get("total_trades", 0),
                        "win_rate": metrics.get("win_rate", 0.0),
                        "net_pnl": metrics.get("net_pnl", 0.0),
                        "sharpe": metrics.get("sharpe_ratio", 0.0),
                        "recovery": metrics.get("recovery_factor", 0.0),
                        "max_dd": metrics.get("max_drawdown", 0.0),
                        "profit_factor": metrics.get("profit_factor", 0.0),
                    }
                )

    if not rows:
        logging.warning("Нет результатов для анализа")
        return analysis

    df = pd.DataFrame(rows)

    # Фильтруем по критериям качества
    criteria = {
        "sharpe > 1.0": df["sharpe"] > 1.0,
        "recovery > 2.0": df["recovery"] > 2.0,
        "max_dd < 0.2": df["max_dd"] > -0.2,
        "profit_factor > 1.5": df["profit_factor"] > 1.5,
        "trades > 10": df["trades"] > 10,
    }

    # Находим стратегии, удовлетворяющие критериям
    good_strategies = df[
        criteria["sharpe > 1.0"]
        & criteria["recovery > 2.0"]
        & criteria["max_dd < 0.2"]
        & criteria["profit_factor > 1.5"]
        & criteria["trades > 10"]
    ]

    if not good_strategies.empty:
        # Сортируем по Sharpe Ratio
        good_strategies = good_strategies.sort_values("sharpe", ascending=False)
        analysis["best_strategies"] = good_strategies.head(10).to_dict("records")

        logging.info("Найдено %s стратегий, удовлетворяющих критериям", len(good_strategies))
        for idx, row in good_strategies.head(5).iterrows():
            logging.info(
                "  %s %s %s: Sharpe=%.2f, Recovery=%.2f, PnL=%.2f",
                row["strategy"],
                row["instrument"],
                row["period"],
                row["sharpe"],
                row["recovery"],
                row["net_pnl"],
            )
    else:
        logging.warning("Не найдено стратегий, удовлетворяющих всем критериям")
        # Показываем лучшие по Sharpe
        best_by_sharpe = df[df["sharpe"] > 0].sort_values("sharpe", ascending=False).head(5)
        analysis["best_strategies"] = best_by_sharpe.to_dict("records")
        logging.info("Лучшие стратегии по Sharpe Ratio:")
        for idx, row in best_by_sharpe.iterrows():
            logging.info(
                "  %s %s %s: Sharpe=%.2f, Recovery=%.2f, PnL=%.2f",
                row["strategy"],
                row["instrument"],
                row["period"],
                row["sharpe"],
                row["recovery"],
                row["net_pnl"],
            )

    # Статистика по стратегиям
    analysis["summary"] = {
        "total_combinations": len(df),
        "profitable": len(df[df["net_pnl"] > 0]),
        "meets_sharpe": len(df[df["sharpe"] > 1.0]),
        "meets_recovery": len(df[df["recovery"] > 2.0]),
        "avg_sharpe": float(df["sharpe"].mean()),
        "avg_recovery": float(df["recovery"].mean()),
        "best_sharpe": float(df["sharpe"].max()) if not df.empty else 0.0,
        "best_recovery": float(df["recovery"].max()) if not df.empty else 0.0,
    }

    # Рекомендации
    if analysis["summary"]["profitable"] == 0:
        analysis["recommendations"].append("Нет прибыльных стратегий. Требуется пересмотр логики.")
    elif len(good_strategies) == 0:
        analysis["recommendations"].append(
            "Есть прибыльные стратегии, но они не удовлетворяют всем критериям качества. Рекомендуется оптимизация параметров."
        )
    else:
        analysis["recommendations"].append(
            f"Найдено {len(good_strategies)} стратегий высокого качества. Рекомендуется провести оптимизацию параметров и walk-forward валидацию."
        )

    return analysis


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Анализ результатов батч-бэктеста.")
    parser.add_argument(
        "report_path",
        type=Path,
        help="Путь к JSON файлу с результатами бэктеста.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Путь для сохранения анализа (по умолчанию рядом с отчетом).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    analysis = analyze_backtest_results(args.report_path)

    # Сохраняем анализ
    output_path = args.output or args.report_path.parent / f"analysis_{args.report_path.stem}.json"
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(analysis, fp, ensure_ascii=False, indent=2)

    logging.info("Анализ сохранен в %s", output_path)


if __name__ == "__main__":
    main()

