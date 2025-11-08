from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .ctrader_adapter import CTraderClient, CTraderCredentials
from .engine import EngineConfig, ExecutionEngine
from .models import Order, OrderSide, OrderType, StrategyConfig


app = typer.Typer(help="Управление контуром исполнения стратегий")


def dummy_dispatch(order: Order):
    return {
        "order": order.__dict__,
        "status": "accepted",
        "executed_quantity": order.quantity,
        "average_price": order.price,
    }


engine: ExecutionEngine = ExecutionEngine(broker_dispatch=lambda order: dummy_dispatch(order))  # type: ignore[arg-type]
ctrader_client: Optional[CTraderClient] = None


@app.command()
def status():
    strategies = [cfg.__dict__ for cfg in engine.list_strategies()]
    typer.echo(json.dumps(strategies, ensure_ascii=False, indent=2))


@app.command()
def register(
    strategy_id: str,
    max_notional: float,
    max_leverage: float,
    max_orders: int = typer.Option(60, help="Лимит отправки ордеров в минуту"),
):
    cfg = StrategyConfig(
        strategy_id=strategy_id,
        max_notional=max_notional,
        max_leverage=max_leverage,
        max_orders_per_minute=max_orders,
    )
    engine.register_strategy(cfg)
    typer.echo(f"Стратегия {strategy_id} зарегистрирована")


@app.command("register-batch")
def register_batch(config_path: Path = typer.Argument(..., help="JSON-файл со списком стратегий")):
    with config_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, list):
        raise typer.BadParameter("JSON должен содержать массив объектов стратегий.")
    for entry in payload:
        cfg = StrategyConfig(
            strategy_id=entry["strategy_id"],
            max_notional=float(entry["max_notional"]),
            max_leverage=float(entry["max_leverage"]),
            max_orders_per_minute=int(entry.get("max_orders_per_minute", 60)),
        )
        engine.register_strategy(cfg)
        typer.echo(f"Стратегия {cfg.strategy_id} зарегистрирована")


@app.command()
def enable(strategy_id: str):
    engine.enable_strategy(strategy_id)
    typer.echo(f"Стратегия {strategy_id} включена")


@app.command()
def disable(strategy_id: str):
    engine.disable_strategy(strategy_id)
    typer.echo(f"Стратегия {strategy_id} отключена")


@app.command()
def throttle(strategy_id: str, max_orders: int = typer.Option(..., help="Максимум ордеров в минуту")):
    engine.throttle_strategy(strategy_id, max_orders)
    typer.echo(f"Стратегия {strategy_id} переведена в режим THROTTLED ({max_orders}/мин)")


@app.command()
def send_order(
    strategy_id: str,
    secid: str,
    side: OrderSide = OrderSide.BUY,
    quantity: float = typer.Option(...),
    price: float = typer.Option(None),
    order_type: OrderType = OrderType.MARKET,
):
    order = Order(
        strategy_id=strategy_id,
        secid=secid,
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type,
    )
    report = engine.submit_order(order)
    typer.echo(json.dumps(report.__dict__, default=str, ensure_ascii=False, indent=2))


@app.command()
def use_ctrader(config: Path = typer.Option(..., help="Путь к JSON с данными cTrader demo")):
    """
    Формат файла:
    {
        "client_id": "",
        "client_secret": "",
        "access_token": "",
        "account_id": "",
        "base_url": "https://api-demo.ctrader.com"
    }
    """

    global engine, ctrader_client
    with config.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    creds = CTraderCredentials(**payload)
    ctrader_client = CTraderClient(creds)
    engine = ExecutionEngine(broker_dispatch=ctrader_client.place_order)
    typer.echo("Настроено использование cTrader API (demo).")


@app.command()
def set_state_path(path: Path):
    engine._engine_config = EngineConfig(state_path=path)  # type: ignore[attr-defined]
    typer.echo(f"State path изменён на {path}")


if __name__ == "__main__":
    app()

