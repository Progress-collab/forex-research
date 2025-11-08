from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Literal, Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class StrategyState(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    THROTTLED = "THROTTLED"


@dataclass(slots=True)
class Order:
    strategy_id: str
    secid: str
    side: OrderSide
    quantity: float
    price: Optional[float]
    order_type: OrderType = OrderType.MARKET
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class ExecutionReport:
    order: Order
    status: Literal["accepted", "rejected", "filled", "partial"]
    executed_quantity: float
    average_price: float | None = None
    rejection_reason: str | None = None
    latency_ms: float | None = None
    broker_payload: Dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyConfig:
    strategy_id: str
    max_notional: float
    max_leverage: float
    max_orders_per_minute: int
    state: StrategyState = StrategyState.ENABLED

