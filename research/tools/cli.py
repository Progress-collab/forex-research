from __future__ import annotations

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import mlflow
import typer
import yaml

from src.data_pipeline import DataPipelineConfig, ingest_instrument_history

from ..templates.backtest_template import BacktestConfig, run_backtest, track_with_mlflow

app = typer.Typer(help="Инструменты исследования форекс-стратегий")


def load_experiment_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


@app.command()
def ingest(
    secid: str = typer.Option(..., help="Код инструмента MOEX"),
    interval: int = typer.Option(24, help="Интервал свечей"),
    start: Optional[str] = typer.Option(None, help="Дата начала YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, help="Дата окончания YYYY-MM-DD"),
):
    config = DataPipelineConfig()
    report = ingest_instrument_history(config, secid=secid, interval=interval)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@app.command()
def backtest(
    config_path: Path = typer.Option(Path("research/configs/experiment.yaml"), help="Путь к конфигурации"),
    variant: str = typer.Option("default", help="Раздел конфигурации"),
):
    config_data = load_experiment_config(config_path)
    defaults = config_data.get("default", {})
    bt_params = config_data.get("backtest", {})

    mlflow.set_tracking_uri(defaults["mlflow"]["tracking_uri"])
    mlflow.set_experiment(defaults["mlflow"]["experiment_name"])

    data_config = DataPipelineConfig(
        dataset_version=defaults["dataset_version"],
        data_root=Path(defaults["data_root"]),
    )

    bt_config = BacktestConfig(
        instrument=bt_params["instrument"],
        strategy_id=bt_params["strategy_id"],
        capital=bt_params["capital"],
        slippage_bps=defaults["evaluation"]["slippage_bps"],
        commission_bps=defaults["evaluation"]["commission_bps"],
    )

    with mlflow.start_run(run_name=f"backtest_{bt_config.instrument}"):
        metrics = run_backtest(bt_config, data_config)
        params = asdict(bt_config)
        track_with_mlflow(metrics, params, {"equity_curve": metrics["equity_curve"]})
        typer.echo(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()

