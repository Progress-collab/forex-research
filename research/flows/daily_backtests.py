from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from datetime import timedelta
from typing import Iterable, Sequence

from prefect import flow, get_run_logger, task

from src.backtesting import BacktestRunner
from src.data_pipeline import DataPipelineConfig
from src.strategies import (
    CarryMomentumStrategy,
    IntradayLiquidityBreakoutStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
    Strategy,
    VolatilityCompressionBreakoutStrategy,
)


@task
def run_backtests(strategies: Sequence[Strategy], instruments: Iterable[str]) -> list[dict]:
    logger = get_run_logger()
    runner = BacktestRunner(DataPipelineConfig(dataset_version="v1", data_root="data"))
    results = runner.run(strategies=strategies, instruments=instruments, limit=500)
    records = [
        {
            "strategy_id": r.strategy_id,
            "instrument": r.instrument,
            "trades": r.trades,
            "pnl": r.pnl,
            "sharpe": r.sharpe,
            "max_drawdown": r.max_drawdown,
            "recovery_factor": r.recovery_factor,
        }
        for r in results
    ]
    for record in records:
        logger.info("Backtest result: %s", record)
    return records


@flow(name="daily_backtest_flow")
def daily_backtest_flow() -> list[dict]:
    strategies: Sequence[Strategy] = [
        MomentumBreakoutStrategy(),
        MeanReversionStrategy(),
        CarryMomentumStrategy(),
        IntradayLiquidityBreakoutStrategy(),
        VolatilityCompressionBreakoutStrategy(),
    ]
    instruments = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    return run_backtests(strategies, instruments)


def build_flow() -> None:
    """
    Шаблон регистрации расписания Prefect:

    ```python
    from prefect.deployments import Deployment
    from prefect.server.schemas.schedules import IntervalSchedule

    deployment = Deployment.build_from_flow(
        flow=daily_backtest_flow,
        name="daily-backtests",
        schedule=IntervalSchedule(interval=timedelta(hours=1)),
    )
    deployment.apply()
    ```
    """

    _ = timedelta  # заглушка, чтобы импорт не считался неиспользованным

