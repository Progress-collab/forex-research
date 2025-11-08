from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Dict

from src.backtesting.full_backtest import FullBacktestRunner
from src.backtesting.walk_forward import WalkForwardTester, WalkForwardResult
from src.strategies import CarryMomentumStrategy, MeanReversionStrategy


def run_walk_forward_validation(
    strategy_name: str,
    instrument: str,
    period: str = "m15",
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    output_path: Path = Path("data/v1/reports/walk_forward"),
) -> WalkForwardResult:
    """
    Проводит walk-forward валидацию стратегии.
    """
    runner = FullBacktestRunner(curated_dir=curated_dir)

    # Создаем factory функцию для стратегии
    if strategy_name == "mean_reversion":
        # Используем оптимизированные параметры
        optimized_params_path = Path("research/configs/optimized/mean_reversion_EURUSD_m15.json")
        if optimized_params_path.exists():
            with optimized_params_path.open("r") as fp:
                params = json.load(fp)
            best_params = params.get("best_params", {})
            
            def strategy_factory() -> MeanReversionStrategy:
                return MeanReversionStrategy(
                    rsi_buy=best_params.get("rsi_buy", 20.0),
                    rsi_sell=best_params.get("rsi_sell", 70.0),
                    atr_multiplier=best_params.get("atr_multiplier", 1.5),
                )
        else:
            def strategy_factory() -> MeanReversionStrategy:
                return MeanReversionStrategy()
    elif strategy_name == "carry_momentum":
        optimized_params_path = Path("research/configs/optimized/carry_momentum_EURUSD_m15.json")
        if optimized_params_path.exists():
            with optimized_params_path.open("r") as fp:
                params = json.load(fp)
            best_params = params.get("best_params", {})
            
            def strategy_factory() -> CarryMomentumStrategy:
                return CarryMomentumStrategy(
                    atr_multiplier=best_params.get("atr_multiplier", 1.5),
                    min_adx=best_params.get("min_adx", 18.0),
                )
        else:
            def strategy_factory() -> CarryMomentumStrategy:
                return CarryMomentumStrategy()
    else:
        raise ValueError(f"Неизвестная стратегия: {strategy_name}")

    tester = WalkForwardTester(runner)
    result = tester.run(
        strategy_factory=strategy_factory,
        instrument=instrument,
        period=period,
        train_months=6,
        test_months=3,
        step_months=1,
    )

    # Сохраняем результаты
    output_path.mkdir(parents=True, exist_ok=True)
    report_file = output_path / f"{strategy_name}_{instrument}_{period}_wf.json"
    
    report_data = {
        "strategy": strategy_name,
        "instrument": instrument,
        "period": period,
        "train_results": [
            {
                "total_trades": r.total_trades,
                "net_pnl": r.net_pnl,
                "sharpe_ratio": r.sharpe_ratio,
                "recovery_factor": r.recovery_factor,
                "max_drawdown": r.max_drawdown,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
            }
            for r in result.train_results
        ],
        "test_results": [
            {
                "total_trades": r.total_trades,
                "net_pnl": r.net_pnl,
                "sharpe_ratio": r.sharpe_ratio,
                "recovery_factor": r.recovery_factor,
                "max_drawdown": r.max_drawdown,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
            }
            for r in result.test_results
        ],
        "parameter_stability": result.parameter_stability,
        "degradation_metrics": result.degradation_metrics,
    }

    with report_file.open("w", encoding="utf-8") as fp:
        json.dump(report_data, fp, ensure_ascii=False, indent=2, default=str)

    logging.info("Walk-forward результаты сохранены в %s", report_file)
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Walk-forward валидация стратегий.")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["mean_reversion", "carry_momentum"],
        help="Стратегия для валидации.",
    )
    parser.add_argument(
        "--instrument",
        default="EURUSD",
        help="Инструмент для валидации.",
    )
    parser.add_argument(
        "--period",
        default="m15",
        help="Период данных.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    result = run_walk_forward_validation(
        strategy_name=args.strategy,
        instrument=args.instrument,
        period=args.period,
    )

    logging.info("Walk-forward валидация завершена")
    logging.info("Деградация Sharpe: %.2f%%", result.degradation_metrics.get("sharpe_degradation_pct", 0))
    logging.info("Деградация Recovery: %.2f%%", result.degradation_metrics.get("recovery_degradation_pct", 0))
    logging.info("Приемлемая деградация: %s", result.degradation_metrics.get("acceptable_degradation", False))


if __name__ == "__main__":
    main()

