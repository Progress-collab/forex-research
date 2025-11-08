from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from .models import ExecutionReport, Order, StrategyConfig, StrategyState
from .router import ExecutionRouter


log = logging.getLogger(__name__)


@dataclass(slots=True)
class EngineConfig:
    state_path: Path = Path("state/execution_strategies.json")


class ExecutionEngine:
    """
    Высокоуровневый интерфейс для управления стратегиями и отправки ордеров.
    """

    def __init__(
        self,
        broker_dispatch: Callable[[Order], ExecutionReport],
        risk_check: Optional[Callable[[Order], bool]] = None,
        engine_config: EngineConfig | None = None,
    ):
        self._engine_config = engine_config or EngineConfig()
        self._configs: Dict[str, StrategyConfig] = {}
        self._router = ExecutionRouter(self._configs, broker_dispatch, risk_check)
        self._load_state()

    def _load_state(self) -> None:
        path = self._engine_config.state_path
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
        for raw in payload:
            cfg = StrategyConfig(**raw)
            self._configs[cfg.strategy_id] = cfg
            self._router.update_strategy(cfg)

    def _persist_state(self) -> None:
        path = self._engine_config.state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            json.dump([asdict(cfg) for cfg in self._configs.values()], fp, ensure_ascii=False, indent=2)

    def register_strategy(self, config: StrategyConfig) -> None:
        self._configs[config.strategy_id] = config
        self._router.update_strategy(config)
        self._persist_state()

    def enable_strategy(self, strategy_id: str) -> None:
        config = self._configs[strategy_id]
        config.state = StrategyState.ENABLED
        self._router.update_strategy(config)
        self._persist_state()

    def disable_strategy(self, strategy_id: str) -> None:
        config = self._configs[strategy_id]
        config.state = StrategyState.DISABLED
        self._router.update_strategy(config)
        self._persist_state()

    def throttle_strategy(self, strategy_id: str, max_orders_per_minute: int) -> None:
        config = self._configs[strategy_id]
        config.state = StrategyState.THROTTLED
        config.max_orders_per_minute = max_orders_per_minute
        self._router.update_strategy(config)
        self._persist_state()

    def submit_order(self, order: Order) -> ExecutionReport:
        report = self._router.route(order)
        log.info("Order report: %s", report)
        return report

    def aggregate_metrics(self) -> Dict[str, Dict[str, float]]:
        stats = defaultdict(lambda: {"orders_sent": 0, "orders_rejected": 0})
        # В реальной системе метрики собираются из брокера/базы. Здесь — заготовка.
        return stats

    def list_strategies(self) -> Iterable[StrategyConfig]:
        return self._router.list_configs()

