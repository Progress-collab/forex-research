from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.backtesting.full_backtest import FullBacktestRunner, FullBacktestResult


def analyze_losing_trades(
    strategy_id: str,
    instrument: str,
    period: str = "m15",
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    output_path: Path = Path("data/v1/reports/trade_analysis"),
) -> Dict:
    """
    Анализирует паттерны убыточных сделок.
    """
    from src.strategies import (
        CarryMomentumStrategy,
        MeanReversionStrategy,
        MomentumBreakoutStrategy,
    )

    # Создаем стратегию
    strategy_map = {
        "mean_reversion": MeanReversionStrategy,
        "carry_momentum": CarryMomentumStrategy,
        "momentum_breakout": MomentumBreakoutStrategy,
    }

    if strategy_id not in strategy_map:
        raise ValueError(f"Неизвестная стратегия: {strategy_id}")

    strategy = strategy_map[strategy_id]()

    # Запускаем бэктест
    runner = FullBacktestRunner(curated_dir=curated_dir)
    result = runner.run(strategy, instrument, period)

    if result.total_trades == 0:
        logging.warning("Нет сделок для анализа")
        return {"error": "No trades"}

    # Анализируем сделки
    trades_df = pd.DataFrame(
        [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.net_pnl,
                "pnl_pct": t.pnl_pct,
                "duration_hours": (t.exit_time - t.entry_time).total_seconds() / 3600,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
            }
            for t in result.trades
        ]
    )

    # Разделяем на прибыльные и убыточные
    winning_trades = trades_df[trades_df["pnl"] > 0]
    losing_trades = trades_df[trades_df["pnl"] < 0]

    analysis = {
        "strategy": strategy_id,
        "instrument": instrument,
        "period": period,
        "total_trades": len(trades_df),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": len(winning_trades) / len(trades_df) if len(trades_df) > 0 else 0.0,
        "patterns": {},
    }

    if len(losing_trades) > 0:
        # Анализ убыточных сделок
        analysis["patterns"]["losing_trades"] = {
            "avg_duration_hours": float(losing_trades["duration_hours"].mean()),
            "avg_loss": float(losing_trades["pnl"].mean()),
            "avg_loss_pct": float(losing_trades["pnl_pct"].mean()),
            "max_loss": float(losing_trades["pnl"].min()),
            "long_vs_short": {
                "long": int((losing_trades["direction"] == "LONG").sum()),
                "short": int((losing_trades["direction"] == "SHORT").sum()),
            },
        }

        # Проверяем, сколько сделок закрылись по стоп-лоссу
        stop_loss_hits = 0
        take_profit_hits = 0
        for _, trade in losing_trades.iterrows():
            if trade["direction"] == "LONG":
                if abs(trade["exit_price"] - trade["stop_loss"]) < abs(trade["exit_price"] - trade["take_profit"]):
                    stop_loss_hits += 1
            else:  # SHORT
                if abs(trade["exit_price"] - trade["stop_loss"]) < abs(trade["exit_price"] - trade["take_profit"]):
                    stop_loss_hits += 1

        analysis["patterns"]["losing_trades"]["stop_loss_hits"] = stop_loss_hits
        analysis["patterns"]["losing_trades"]["take_profit_hits"] = take_profit_hits

    if len(winning_trades) > 0:
        # Анализ прибыльных сделок для сравнения
        analysis["patterns"]["winning_trades"] = {
            "avg_duration_hours": float(winning_trades["duration_hours"].mean()),
            "avg_win": float(winning_trades["pnl"].mean()),
            "avg_win_pct": float(winning_trades["pnl_pct"].mean()),
            "max_win": float(winning_trades["pnl"].max()),
        }

    # Рекомендации
    recommendations = []
    if len(losing_trades) > len(winning_trades) * 2:
        recommendations.append("Слишком много убыточных сделок. Рассмотреть более строгие фильтры входа.")
    if len(losing_trades) > 0 and analysis["patterns"]["losing_trades"]["avg_loss"] < -100:
        recommendations.append("Средний убыток слишком большой. Рассмотреть уменьшение размера позиции или улучшение стоп-лоссов.")
    if len(losing_trades) > 0 and analysis["patterns"]["losing_trades"]["stop_loss_hits"] > len(losing_trades) * 0.7:
        recommendations.append("Большинство убыточных сделок закрываются по стоп-лоссу. Рассмотреть увеличение расстояния стоп-лосса или улучшение фильтров входа.")

    analysis["recommendations"] = recommendations

    # Сохраняем анализ
    output_path.mkdir(parents=True, exist_ok=True)
    report_file = output_path / f"{strategy_id}_{instrument}_{period}_analysis.json"
    with report_file.open("w", encoding="utf-8") as fp:
        json.dump(analysis, fp, ensure_ascii=False, indent=2, default=str)

    logging.info("Анализ сохранен в %s", report_file)
    return analysis


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Анализ паттернов убыточных сделок.")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["mean_reversion", "carry_momentum", "momentum_breakout"],
        help="Стратегия для анализа.",
    )
    parser.add_argument(
        "--instrument",
        default="EURUSD",
        help="Инструмент для анализа.",
    )
    parser.add_argument(
        "--period",
        default="m15",
        help="Период данных.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    analyze_losing_trades(
        strategy_id=args.strategy,
        instrument=args.instrument,
        period=args.period,
    )


if __name__ == "__main__":
    main()

