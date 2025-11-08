from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner, FullBacktestResult
from src.strategies import (
    CarryMomentumStrategy,
    IntradayLiquidityBreakoutStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
    NewsMomentumStrategy,
    PairsTradingStrategy,
    Strategy,
    VolatilityCompressionBreakoutStrategy,
    CombinedMomentumStrategy,
    MACDTrendStrategy,
    BollingerReversionStrategy,
)


def run_batch_backtests(
    strategies: List[Strategy],
    instruments: List[str],
    periods: List[str],
    output_dir: Path = Path("data/v1/reports/backtest_results"),
    curated_dir: Path = Path("data/v1/curated/ctrader"),
) -> Dict:
    """
    Запускает батч-тестирование всех стратегий на всех инструментах и периодах.
    """
    log = logging.getLogger(__name__)
    runner = FullBacktestRunner(curated_dir=curated_dir)

    results: Dict[str, Dict] = {}
    total_combinations = len(strategies) * len(instruments) * len(periods)
    current = 0

    for strategy in strategies:
        strategy_id = strategy.strategy_id
        results[strategy_id] = {}

        for instrument in instruments:
            results[strategy_id][instrument] = {}

            for period in periods:
                current += 1
                log.info(
                    "[%s/%s] Тестируем %s на %s %s",
                    current,
                    total_combinations,
                    strategy_id,
                    instrument,
                    period,
                )

                try:
                    result = runner.run(strategy, instrument, period)
                    results[strategy_id][instrument][period] = {
                        "total_trades": result.total_trades,
                        "win_rate": result.win_rate,
                        "net_pnl": result.net_pnl,
                        "sharpe_ratio": result.sharpe_ratio,
                        "max_drawdown": result.max_drawdown,
                        "recovery_factor": result.recovery_factor,
                        "profit_factor": result.profit_factor,
                        "total_commission": result.total_commission,
                        "total_swap": result.total_swap,
                        "start_date": result.start_date.isoformat(),
                        "end_date": result.end_date.isoformat(),
                    }
                    log.info(
                        "  Результат: %s сделок, Sharpe=%.2f, Recovery=%.2f, Net PnL=%.2f",
                        result.total_trades,
                        result.sharpe_ratio,
                        result.recovery_factor,
                        result.net_pnl,
                    )
                except Exception as e:  # noqa: BLE001
                    log.error("Ошибка при тестировании %s %s %s: %s", strategy_id, instrument, period, e)
                    results[strategy_id][instrument][period] = {"error": str(e)}

    # Сохраняем результаты
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"batch_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with report_path.open("w", encoding="utf-8") as fp:
        json.dump(results, fp, ensure_ascii=False, indent=2)

    log.info("Отчет сохранен в %s", report_path)
    return results


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Батч-тестирование всех стратегий.")
    parser.add_argument(
        "--strategies",
        nargs="+",
        help="Список стратегий для тестирования (по умолчанию все).",
    )
    parser.add_argument(
        "--instruments",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
        help="Список инструментов.",
    )
    parser.add_argument(
        "--periods",
        nargs="+",
        default=["m15", "h1"],
        help="Периоды для тестирования.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/v1/reports/backtest_results",
        help="Каталог для сохранения результатов.",
    )
    parser.add_argument(
        "--curated-dir",
        default="data/v1/curated/ctrader",
        help="Каталог с curated данными.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Создаем стратегии
    all_strategies: List[Strategy] = [
        MomentumBreakoutStrategy(),
        MeanReversionStrategy(),
        CarryMomentumStrategy(),
        IntradayLiquidityBreakoutStrategy(),
        VolatilityCompressionBreakoutStrategy(),
        CombinedMomentumStrategy(),
        MACDTrendStrategy(),
        BollingerReversionStrategy(),
        # PairsTradingStrategy(),  # Требует специальной подготовки данных
        # NewsMomentumStrategy(),  # Требует данных новостей
    ]

    if args.strategies:
        all_strategies = [s for s in all_strategies if s.strategy_id in args.strategies]

    run_batch_backtests(
        strategies=all_strategies,
        instruments=args.instruments,
        periods=args.periods,
        output_dir=Path(args.output_dir),
        curated_dir=Path(args.curated_dir),
    )


if __name__ == "__main__":
    main()

