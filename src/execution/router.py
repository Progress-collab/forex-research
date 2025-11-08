from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, Iterable, Optional

from .models import ExecutionReport, Order, StrategyConfig, StrategyState


@dataclass(slots=True)
class OrderThrottle:
    max_orders_per_minute: int
    _timestamps: Deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self._timestamps = deque()

    def allow(self) -> bool:
        now = time.time()
        window_start = now - 60
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()
        if len(self._timestamps) >= self.max_orders_per_minute:
            return False
        self._timestamps.append(now)
        return True


class ExecutionRouter:
    """
    Маршрутизатор заявок: применяет throttle и risk-check перед отправкой в брокера.
    """

    def __init__(
        self,
        strategy_configs: Dict[str, StrategyConfig],
        broker_dispatch: Callable[[Order], ExecutionReport],
        risk_check: Optional[Callable[[Order], bool]] = None,
    ):
        self._configs = strategy_configs
        self._broker_dispatch = broker_dispatch
        self._risk_check = risk_check
        self._throttles: Dict[str, OrderThrottle] = {
            cfg.strategy_id: OrderThrottle(cfg.max_orders_per_minute)
            for cfg in strategy_configs.values()
        }

    def route(self, order: Order) -> ExecutionReport:
        config = self._configs.get(order.strategy_id)
        if not config:
            return ExecutionReport(
                order=order,
                status="rejected",
                executed_quantity=0.0,
                rejection_reason="UNKNOWN_STRATEGY",
            )

        if config.state != StrategyState.ENABLED:
            return ExecutionReport(
                order=order,
                status="rejected",
                executed_quantity=0.0,
                rejection_reason=f"STRATEGY_{config.state}",
            )

        throttle = self._throttles[order.strategy_id]
        if not throttle.allow():
            return ExecutionReport(
                order=order,
                status="rejected",
                executed_quantity=0.0,
                rejection_reason="THROTTLED",
            )

        if self._risk_check and not self._risk_check(order):
            return ExecutionReport(
                order=order,
                status="rejected",
                executed_quantity=0.0,
                rejection_reason="RISK_CHECK_FAILED",
            )

        return self._broker_dispatch(order)

    def update_strategy(self, config: StrategyConfig) -> None:
        self._configs[config.strategy_id] = config
        self._throttles[config.strategy_id] = OrderThrottle(config.max_orders_per_minute)

    def list_configs(self) -> Iterable[StrategyConfig]:
        return self._configs.values()

