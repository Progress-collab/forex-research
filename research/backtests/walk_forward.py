from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Dict, List

import mlflow
import pandas as pd

from src.strategies import (
    CarryMomentumStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
)

from .run_baseline import (
    MIN_HISTORY_MAP,
    compute_trade_metrics,
    load_instrument,
    simulate_trade,
    summarise,
    walk_forward_signals,
)


PARAM_GRID: Dict[str, List[Dict[str, float]]] = {
    "momentum_breakout": [
        {"lookback_hours": 18, "atr_multiplier": 1.6, "adx_threshold": 16.0},
        {"lookback_hours": 24, "atr_multiplier": 1.8, "adx_threshold": 18.0},
        {"lookback_hours": 32, "atr_multiplier": 2.0, "adx_threshold": 20.0},
    ],
    "mean_reversion": [
        {"rsi_buy": 10.0, "rsi_sell": 90.0, "atr_multiplier": 1.1},
        {"rsi_buy": 15.0, "rsi_sell": 85.0, "atr_multiplier": 1.2},
        {"rsi_buy": 20.0, "rsi_sell": 80.0, "atr_multiplier": 1.3},
    ],
    "carry_momentum": [
        {"atr_multiplier": 1.2, "min_adx": 16.0},
        {"atr_multiplier": 1.5, "min_adx": 18.0},
        {"atr_multiplier": 1.8, "min_adx": 20.0},
    ],
}

STRATEGY_FACTORIES = {
    "momentum_breakout": MomentumBreakoutStrategy,
    "mean_reversion": MeanReversionStrategy,
    "carry_momentum": CarryMomentumStrategy,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk-forward оптимизация стратегий.")
    parser.add_argument("--strategy", choices=list(STRATEGY_FACTORIES.keys()) + ["all"], default="all")
    parser.add_argument("--instrument", default="EURUSD")
    parser.add_argument("--train-bars", type=int, default=96 * 4, help="Размер окна обучения (кол-во баров).")
    parser.add_argument("--test-bars", type=int, default=96, help="Размер окна валидации/форварда.")
    parser.add_argument("--min-history", type=int, default=120, help="Минимальное количество баров для генерации.")
    parser.add_argument("--mlflow-experiment", default="fxpro-walk-forward")
    return parser.parse_args()


def build_strategy(name: str, params: Dict[str, float]):
    factory = STRATEGY_FACTORIES[name]
    return factory(**params)


def evaluate_strategy(
    name: str,
    df: pd.DataFrame,
    params: Dict[str, float],
    min_history: int,
) -> pd.DataFrame:
    strategy = build_strategy(name, params)
    signals = walk_forward_signals(df, strategy, min_history)
    trades = []
    for ts, signal in signals:
        idx = df.index.get_loc(ts)
        trade = simulate_trade(df, idx, signal)
        trades.append(trade)
    return pd.DataFrame([trade.__dict__ for trade in trades]) if trades else pd.DataFrame()


def walk_forward_optimize(
    strategy_name: str,
    instrument: str,
    df: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    min_history: int,
) -> pd.DataFrame:
    param_grid = PARAM_GRID[strategy_name]
    folds: List[pd.DataFrame] = []
    experiment = os.getenv("MLFLOW_EXPERIMENT", "fxpro-walk-forward")
    try:
        mlflow.set_experiment(experiment)
    except Exception:
        experiment = None  # Fall back to no-logging mode

    run = None
    try:
        if experiment:
            run = mlflow.start_run(run_name=f"{strategy_name}-{instrument}-{datetime.utcnow().isoformat()}")
        for fold_index, start in enumerate(range(train_bars, len(df) - test_bars, test_bars)):
            train_df = df.iloc[:start]
            test_df = df.iloc[start : start + test_bars]
            if len(train_df) < min_history:
                continue

            best_params = None
            best_score = float("-inf")
            for params in param_grid:
                trades_train = evaluate_strategy(strategy_name, train_df, params, min_history)
                metrics = compute_trade_metrics(trades_train)
                score = metrics["total_pnl_usd"]
                if score > best_score:
                    best_score = score
                    best_params = params

            if best_params is None:
                continue

            combined_df = df.iloc[: start + test_bars]
            trades_test = evaluate_strategy(strategy_name, combined_df, best_params, min_history)
            if trades_test.empty:
                continue
            trades_test = trades_test[trades_test["entry_time"] >= test_df.index[0]]
            metrics = compute_trade_metrics(trades_test)
            metrics.update({"fold_start": test_df.index[0].isoformat(), "fold_end": test_df.index[-1].isoformat()})
            _safe_mlflow_log_params({f"fold{fold_index}_{k}": v for k, v in best_params.items()})
            _safe_mlflow_log_metrics({f"fold{fold_index}_{k}": v for k, v in metrics.items() if isinstance(v, (int, float))})
            folds.append(trades_test)

        if folds:
            all_trades = pd.concat(folds, ignore_index=True)
            all_trades["win"] = all_trades["pnl_usd_per_lot"] > 0
            aggregate_metrics = compute_trade_metrics(all_trades)
            _safe_mlflow_log_metrics({f"wf_{k}": v for k, v in aggregate_metrics.items()})
            summary = summarise(all_trades)
            print(summary)
            return all_trades
    finally:
        if run:
            mlflow.end_run()

    return pd.DataFrame()


def _safe_mlflow_log_params(payload: Dict[str, float]) -> None:
    try:
        if mlflow.active_run():
            string_payload = {k: str(v) for k, v in payload.items()}
            mlflow.log_params(string_payload)
    except Exception:
        pass


def _safe_mlflow_log_metrics(payload: Dict[str, float]) -> None:
    try:
        if mlflow.active_run():
            mlflow.log_metrics(payload)
    except Exception:
        pass


if __name__ == "__main__":
    args = parse_args()
    if args.mlflow_experiment:
        os.environ["MLFLOW_EXPERIMENT"] = args.mlflow_experiment
    strategies = (
        STRATEGY_FACTORIES.keys()
        if args.strategy == "all"
        else [args.strategy]
    )
    df = load_instrument(args.instrument)
    for strategy_name in strategies:
        min_hist = max(args.min_history, MIN_HISTORY_MAP.get(strategy_name, args.min_history))
        trades = walk_forward_optimize(
            strategy_name=strategy_name,
            instrument=args.instrument,
            df=df,
            train_bars=args.train_bars,
            test_bars=args.test_bars,
            min_history=min_hist,
        )
        metrics = compute_trade_metrics(trades)
        print(f"{strategy_name} metrics:", metrics)

