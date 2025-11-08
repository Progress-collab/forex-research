from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from dataclasses import asdict

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.execution.engine import EngineConfig, ExecutionEngine
from src.execution.models import ExecutionReport, Order, OrderSide, OrderType, StrategyConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run регистрация стратегий и отправка тестовых ордеров.")
    parser.add_argument("--config", default="config/strategies.json", help="JSON-файл с конфигурациями стратегий.")
    parser.add_argument(
        "--state-path",
        default="state/paper_dry_run.json",
        help="Путь к файлу состояния (не влияет на рабочую среду).",
    )
    parser.add_argument(
        "--simulate-orders",
        action="store_true",
        help="Отправить тестовый ордер для каждой стратегии после регистрации.",
    )
    parser.add_argument("--instrument", default="EURUSD", help="Инструмент для тестового ордера.")
    parser.add_argument("--notional", type=float, default=10_000, help="Нотионал тестового ордера.")
    return parser.parse_args()


def dummy_dispatch(order: Order) -> ExecutionReport:
    return ExecutionReport(
        order=order,
        status="accepted",
        executed_quantity=order.quantity,
        average_price=order.price or 0.0,
        broker_payload={"order_id": f"SIM-{order.strategy_id}"},
    )


def load_configs(path: Path) -> Iterable[StrategyConfig]:
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    for raw in payload:
        yield StrategyConfig(**raw)


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Не найден файл {config_path}")

    engine = ExecutionEngine(
        broker_dispatch=dummy_dispatch,
        engine_config=EngineConfig(state_path=Path(args.state_path)),
    )

    for cfg in load_configs(config_path):
        engine.register_strategy(cfg)
        engine.enable_strategy(cfg.strategy_id)
        print(f"[OK] Зарегистрирована стратегия {cfg.strategy_id}")

    print("\nТекущее состояние стратегий:")
    for cfg in engine.list_strategies():
        print(json.dumps(asdict(cfg), ensure_ascii=False, indent=2, default=str))

    if args.simulate_orders:
        print("\nОтправка тестовых ордеров:")
        for cfg in engine.list_strategies():
            order = Order(
                strategy_id=cfg.strategy_id,
                secid=args.instrument,
                side=OrderSide.BUY,
                quantity=args.notional,
                price=None,
                order_type=OrderType.MARKET,
            )
            report = engine.submit_order(order)
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

