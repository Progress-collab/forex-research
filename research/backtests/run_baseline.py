from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import mlflow
import pandas as pd

from src.strategies import (
    CarryMomentumStrategy,
    MeanReversionStrategy,
    MomentumBreakoutStrategy,
    Signal,
    Strategy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_ROOT = Path("data/v1/raw")
CURATED_ROOT = Path("data/v1/curated/ctrader")
REPORTS_ROOT = Path("research/reports")
REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
PROM_EXPORT_PATH = Path("monitoring/data/baseline_metrics.json")


PIP_CONFIG = {
    "EURUSD": {"pip_size": 0.0001, "pip_value": 10.0},
    "GBPUSD": {"pip_size": 0.0001, "pip_value": 10.0},
    "USDJPY": {"pip_size": 0.01, "pip_value": 9.1},
    "XAUUSD": {"pip_size": 0.1, "pip_value": 10.0},  # 0.1$ move ≈ $10 per стандартный лот (100 oz)
}

HORIZON_MAP = {
    "momentum_breakout": 20,  # 5 часов на M15
    "mean_reversion": 16,     # 4 часа
    "carry_momentum": 96,     # 24 часа
}

MIN_HISTORY_MAP = {
    "momentum_breakout": 60,
    "mean_reversion": 120,
    "carry_momentum": 200,
}


@dataclass
class TradeResult:
    strategy_id: str
    instrument: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str
    entry_price: float
    exit_price: float
    pnl_pips: float
    pnl_usd_per_lot: float
    bars_held: int
    outcome: str


def load_instrument(instrument: str) -> pd.DataFrame:
    curated = CURATED_ROOT / f"{instrument}_m15.parquet"
    if curated.exists():
        df = pd.read_parquet(curated)
    else:
        # fallback to legacy raw path
        path = RAW_ROOT / f"{instrument.lower()}_m15.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Не найдены данные {instrument}: {curated} / {path}")
        df = pd.read_json(path, lines=True)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df["instrument"] = instrument
    return df.sort_values("utc_time").set_index("utc_time")


def walk_forward_signals(df: pd.DataFrame, strategy: Strategy, min_history: int) -> List[tuple[pd.Timestamp, Signal]]:
    signals: List[tuple[pd.Timestamp, Signal]] = []
    rows = df.to_dict("records")
    index = list(df.index)
    for idx in range(min_history, len(df) - 1):
        window = pd.DataFrame(rows[: idx + 1])
        window.index = index[: idx + 1]
        sigs = strategy.generate_signals(window)
        if not sigs:
            continue
        timestamp = index[idx]
        for sig in sigs:
            signals.append((timestamp, sig))
    return signals


def simulate_trade(df: pd.DataFrame, start_idx: int, signal: Signal) -> TradeResult:
    instrument = signal.instrument
    pip_conf = PIP_CONFIG[instrument]
    horizon = HORIZON_MAP.get(signal.strategy_id, 20)

    future = df.iloc[start_idx + 1 : start_idx + 1 + horizon]
    entry_time = df.index[start_idx]
    entry_price = signal.entry_price
    exit_price = future["close"].iloc[-1] if not future.empty else entry_price
    exit_time = future.index[-1] if not future.empty else entry_time
    outcome = "timeout"

    for ts, row in future.iterrows():
        high = row["high"]
        low = row["low"]
        if signal.direction == "LONG":
            if low <= signal.stop_loss:
                exit_price = signal.stop_loss
                exit_time = ts
                outcome = "stop"
                break
            if high >= signal.take_profit:
                exit_price = signal.take_profit
                exit_time = ts
                outcome = "target"
                break
        else:
            if high >= signal.stop_loss:
                exit_price = signal.stop_loss
                exit_time = ts
                outcome = "stop"
                break
            if low <= signal.take_profit:
                exit_price = signal.take_profit
                exit_time = ts
                outcome = "target"
                break

    if signal.direction == "LONG":
        pnl = exit_price - entry_price
    else:
        pnl = entry_price - exit_price

    pnl_pips = pnl / pip_conf["pip_size"]
    pnl_usd = pnl_pips * pip_conf["pip_value"]
    bars_held = max(1, int((exit_time - entry_time).total_seconds() // (15 * 60)))
    return TradeResult(
        strategy_id=signal.strategy_id,
        instrument=instrument,
        entry_time=entry_time,
        exit_time=exit_time,
        direction=signal.direction,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl_pips=pnl_pips,
        pnl_usd_per_lot=pnl_usd,
        bars_held=bars_held,
        outcome=outcome,
    )


def run_baseline_backtests() -> pd.DataFrame:
    universe = {
        "momentum_breakout": ["EURUSD", "GBPUSD", "XAUUSD"],
        "mean_reversion": ["EURUSD", "USDJPY"],
        "carry_momentum": ["USDJPY"],
    }
    strategy_factory: dict[str, Strategy] = {
        "momentum_breakout": MomentumBreakoutStrategy(),
        "mean_reversion": MeanReversionStrategy(),
        "carry_momentum": CarryMomentumStrategy(),
    }
    all_trades: List[TradeResult] = []

    for strategy_id, instruments in universe.items():
        strategy = strategy_factory[strategy_id]
        min_history = MIN_HISTORY_MAP[strategy_id]
        for instrument in instruments:
            df = load_instrument(instrument)
            signals = walk_forward_signals(df, strategy, min_history)
            for ts, signal in signals:
                start_idx = df.index.get_loc(ts)
                trade = simulate_trade(df, start_idx, signal)
                all_trades.append(trade)

    if not all_trades:
        return pd.DataFrame()

    trades_df = pd.DataFrame([trade.__dict__ for trade in all_trades])
    trades_df["win"] = trades_df["pnl_usd_per_lot"] > 0
    return trades_df


def summarise(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return trades_df

    summary = (
        trades_df.groupby(["strategy_id", "instrument"])
        .agg(
            trades=("pnl_usd_per_lot", "count"),
            win_rate=("win", "mean"),
            avg_pnl_usd=("pnl_usd_per_lot", "mean"),
            total_pnl_usd=("pnl_usd_per_lot", "sum"),
            avg_duration_bars=("bars_held", "mean"),
        )
        .reset_index()
    )
    return summary


def render_report(summary: pd.DataFrame, trades_df: pd.DataFrame, metrics: dict[str, float]) -> None:
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    report_path = REPORTS_ROOT / f"baseline_backtest_{timestamp}.md"
    lines: List[str] = [
        f"# Baseline backtests ({timestamp})",
        "",
        "## Aggregate metrics",
        "",
    ]
    if metrics:
        metrics_table = pd.DataFrame([metrics])
        metrics_table = metrics_table[
            ["trades", "win_rate", "total_pnl_usd", "sharpe", "recovery_factor", "max_dd"]
        ]
        metrics_table["win_rate"] = (metrics_table["win_rate"] * 100).round(2).astype(str) + "%"
        metrics_table["total_pnl_usd"] = metrics_table["total_pnl_usd"].round(2)
        metrics_table["sharpe"] = metrics_table["sharpe"].round(2)
        metrics_table["recovery_factor"] = metrics_table["recovery_factor"].round(2)
        metrics_table["max_dd"] = metrics_table["max_dd"].round(2)
        lines.append(_to_markdown(metrics_table))
        lines.append("")

    lines.extend(
        [
        "## Summary by strategy/instrument",
        "",
    ]
    )
    if summary.empty:
        lines.append("Нет данных для отчёта.")
    else:
        table = summary.copy()
        table["win_rate"] = (table["win_rate"] * 100).round(1).astype(str) + "%"
        table["avg_pnl_usd"] = table["avg_pnl_usd"].round(2)
        table["total_pnl_usd"] = table["total_pnl_usd"].round(2)
        table["avg_duration_bars"] = table["avg_duration_bars"].round(1)
        lines.append(_to_markdown(table))
        lines.append("")
        lines.append("## Trades (top 20 by absolute PnL)")
        lines.append("")
        top = trades_df.reindex(trades_df["pnl_usd_per_lot"].abs().sort_values(ascending=False).index).head(20)
        display_cols = [
            "strategy_id",
            "instrument",
            "entry_time",
            "exit_time",
            "direction",
            "pnl_usd_per_lot",
            "outcome",
        ]
        lines.append(_to_markdown(top[display_cols]))

    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Отчёт сохранён: %s", report_path)


def _to_markdown(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except ImportError:
        return "```\n" + df.to_string(index=False) + "\n```"


def compute_trade_metrics(trades_df: pd.DataFrame) -> dict[str, float]:
    if trades_df.empty:
        return {
            "trades": 0.0,
            "win_rate": 0.0,
            "total_pnl_usd": 0.0,
            "sharpe": 0.0,
            "recovery_factor": 0.0,
            "max_dd": 0.0,
        }

    trades = trades_df.sort_values("entry_time")
    pnl = trades["pnl_usd_per_lot"]
    total = pnl.sum()
    win_rate = (pnl > 0).mean()
    mean = pnl.mean()
    std = pnl.std(ddof=0)
    sharpe = (mean / std * (252 ** 0.5)) if std > 0 else 0.0

    equity_curve = pnl.cumsum()
    rolling_max = equity_curve.cummax()
    drawdowns = equity_curve - rolling_max
    max_dd = float(drawdowns.min())
    recovery = total / abs(max_dd) if max_dd < 0 else 0.0

    return {
        "trades": float(len(trades)),
        "win_rate": float(win_rate),
        "total_pnl_usd": float(total),
        "sharpe": float(sharpe),
        "recovery_factor": float(recovery),
        "max_dd": float(max_dd),
    }


def export_metrics(metrics: dict[str, float], summary: pd.DataFrame) -> None:
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "per_strategy": summary.to_dict(orient="records") if not summary.empty else [],
    }
    PROM_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROM_EXPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def log_metrics_mlflow(metrics: dict[str, float], summary: pd.DataFrame) -> None:
    experiment = os.getenv("BASELINE_MLFLOW_EXPERIMENT")
    if not experiment:
        return
    try:
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=f"baseline-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"):
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
            if not summary.empty:
                for row in summary.to_dict(orient="records"):
                    tag_prefix = f"{row['strategy_id']}_{row['instrument']}"
                    mlflow.log_metrics(
                        {
                            f"{tag_prefix}_pnl": row["total_pnl_usd"],
                            f"{tag_prefix}_win_rate": row["win_rate"],
                        }
                    )
    except Exception:
        pass


if __name__ == "__main__":
    trades = run_baseline_backtests()
    summary = summarise(trades)
    if not summary.empty:
        metrics = compute_trade_metrics(trades)
        render_report(summary, trades, metrics)
        export_metrics(metrics, summary)
        log_metrics_mlflow(metrics, summary)
        log.info("Результаты бэктеста:\n%s", summary)
    else:
        log.warning("Не удалось сгенерировать сделки — проверьте исходные данные.")

