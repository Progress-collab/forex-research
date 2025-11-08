from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

from itertools import product

import mlflow
import numpy as np
import pandas as pd

from src.strategies import (
    CarryMomentumStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
)

from src.data_pipeline import DataPipelineConfig
from src.data_pipeline.storage import ensure_directories


@dataclass(slots=True)
class BacktestConfig:
    instrument: str
    strategy_id: str
    capital: float
    slippage_bps: float
    commission_bps: float


def load_candles(config: DataPipelineConfig, instrument: str) -> pd.DataFrame:
    raw_dir = config.raw_root() / "candles"
    files = sorted(raw_dir.glob(f"{instrument.lower()}_candles_*"))
    if not files:
        raise FileNotFoundError(f"Не найдены данные для {instrument} в {raw_dir}")

    frames = [pd.read_json(file, lines=True) for file in files]
    df = pd.concat(frames).drop_duplicates(subset=["end"]).sort_values("end")
    df["end"] = pd.to_datetime(df["end"])
    df["instrument"] = instrument
    return df.tail(500)


STRATEGY_FACTORY = {
    "momentum_breakout": MomentumBreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "carry_momentum": CarryMomentumStrategy,
}


def run_backtest(
    bt_config: BacktestConfig,
    data_config: DataPipelineConfig,
    strategy_kwargs: Dict[str, float] | None = None,
) -> dict[str, float]:
    ensure_directories(data_config)
    df = load_candles(data_config, bt_config.instrument)
    strategy_cls = STRATEGY_FACTORY[bt_config.strategy_id]
    strategy = strategy_cls(**(strategy_kwargs or {}))
    signals = strategy.generate_signals(df)
    if not signals:
        raise RuntimeError("Стратегия не сгенерировала сигналов на текущем срезе.")

    closes = df["close"]
    returns = []
    equity = [bt_config.capital]
    commission = bt_config.commission_bps / 10000
    slippage = bt_config.slippage_bps / 10000

    for signal in signals:
        delta = closes.iloc[-1] - signal.entry_price if signal.direction == "LONG" else signal.entry_price - closes.iloc[-1]
        net = delta / signal.entry_price - commission - slippage
        returns.append(net)
        equity.append(equity[-1] * (1 + net))

    ret_series = np.array(returns)
    pnl = float(np.sum(ret_series) * bt_config.capital)
    sharpe = float(np.sqrt(252) * ret_series.mean() / (ret_series.std(ddof=1) + 1e-9))
    equity_series = pd.Series(equity)
    max_drawdown = float((equity_series / equity_series.cummax() - 1).min())
    recovery_factor = pnl / abs(max_drawdown) if max_drawdown != 0 else float("inf")

    return {
        "pnl": pnl,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "recovery_factor": recovery_factor,
        "equity_curve": equity_series.tolist(),
        "signals": len(signals),
    }


def track_with_mlflow(metrics: dict[str, float], params: dict[str, float], artifacts: dict[str, Iterable[float]]) -> None:
    mlflow.log_params(params)
    mlflow.log_metrics({k: v for k, v in metrics.items() if k != "equity_curve"})

    equity_path = Path("artifacts") / "equity_curve.json"
    equity_path.parent.mkdir(parents=True, exist_ok=True)
    with equity_path.open("w", encoding="utf-8") as fp:
        json.dump({"equity_curve": list(artifacts["equity_curve"])}, fp, ensure_ascii=False, indent=2)
    mlflow.log_artifact(str(equity_path))


def generate_param_grid(grid: Dict[str, Iterable[float]]) -> Iterator[Dict[str, float]]:
    keys = list(grid.keys())
    values = [list(v) for v in grid.values()]
    for combo in product(*values):
        yield dict(zip(keys, combo, strict=False))


def run_grid_search(
    bt_config: BacktestConfig,
    data_config: DataPipelineConfig,
    param_grid: Dict[str, Iterable[float]],
) -> List[dict[str, float]]:
    results: List[dict[str, float]] = []
    for params in generate_param_grid(param_grid):
        metrics = run_backtest(bt_config, data_config, strategy_kwargs=params)
        artifacts = {"equity_curve": metrics.pop("equity_curve")}
        payload = {"params": params, "metrics": metrics}
        results.append(payload)
        track_with_mlflow(metrics, {**params, "strategy_id": bt_config.strategy_id}, artifacts)
    return results

