from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from ctrader_open_api import Protobuf

log = logging.getLogger(__name__)


@dataclass(slots=True)
class SymbolInfo:
    """Информация о символе FXPro из cTrader API."""

    symbol_id: int
    symbol_name: str
    description: str = ""
    digits: int = 5
    pip_location: int = -4  # для большинства валютных пар
    swap_long: float = 0.0  # своп за лот в день для long позиции
    swap_short: float = 0.0  # своп за лот в день для short позиции
    swap_rollover3days: int = 3  # день недели rollover (обычно среда=3)
    commission: float = 0.0  # комиссия за лот
    spread: float = 0.0  # текущий спред в пипсах
    min_volume: float = 0.01  # минимальный объём лота
    max_volume: float = 100.0  # максимальный объём лота
    volume_step: float = 0.01  # шаг объёма
    currency: str = "USD"
    quote_currency: str = "USD"
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def extract_symbol_info(symbol_proto) -> SymbolInfo:  # noqa: ANN001
    """
    Извлекает информацию о символе из ProtoOASymbol.
    """
    return SymbolInfo(
        symbol_id=symbol_proto.symbolId,
        symbol_name=symbol_proto.symbolName,
        description=getattr(symbol_proto, "description", ""),
        digits=getattr(symbol_proto, "digits", 5),
        pip_location=getattr(symbol_proto, "pipLocation", -4),
        swap_long=getattr(symbol_proto, "swapLong", 0.0) / 1e6,  # обычно в микро-единицах
        swap_short=getattr(symbol_proto, "swapShort", 0.0) / 1e6,
        swap_rollover3days=getattr(symbol_proto, "swapRollover3Days", 3),
        commission=getattr(symbol_proto, "commission", 0.0) / 1e6,
        spread=getattr(symbol_proto, "spreadTable", [0.0])[0] if hasattr(symbol_proto, "spreadTable") else 0.0,
        min_volume=getattr(symbol_proto, "minVolume", 0.01),
        max_volume=getattr(symbol_proto, "maxVolume", 100.0),
        volume_step=getattr(symbol_proto, "volumeStep", 0.01),
        currency=getattr(symbol_proto, "currency", "USD"),
        quote_currency=getattr(symbol_proto, "quoteCurrency", "USD"),
    )


class SymbolInfoCache:
    """Кэш информации о символах с возможностью сохранения/загрузки."""

    def __init__(self, cache_path: Optional[Path] = None):
        self._cache_path = cache_path or Path("data/v1/ref/symbols_info.json")
        self._symbols: Dict[str, SymbolInfo] = {}
        self._lock = threading.Lock()

    def update_from_proto(self, symbols_proto_list) -> None:  # noqa: ANN001
        """Обновляет кэш из списка ProtoOASymbol."""
        with self._lock:
            for symbol_proto in symbols_proto_list:
                info = extract_symbol_info(symbol_proto)
                self._symbols[info.symbol_name] = info
            log.info("Updated symbol info cache: %s symbols", len(self._symbols))

    def get(self, symbol_name: str) -> Optional[SymbolInfo]:
        """Получает информацию о символе."""
        with self._lock:
            return self._symbols.get(symbol_name.upper())

    def save(self) -> None:
        """Сохраняет кэш в JSON."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "symbols": {
                name: {
                    "symbol_id": info.symbol_id,
                    "symbol_name": info.symbol_name,
                    "description": info.description,
                    "digits": info.digits,
                    "pip_location": info.pip_location,
                    "swap_long": info.swap_long,
                    "swap_short": info.swap_short,
                    "swap_rollover3days": info.swap_rollover3days,
                    "commission": info.commission,
                    "spread": info.spread,
                    "min_volume": info.min_volume,
                    "max_volume": info.max_volume,
                    "volume_step": info.volume_step,
                    "currency": info.currency,
                    "quote_currency": info.quote_currency,
                }
                for name, info in self._symbols.items()
            },
        }
        with self._cache_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    def load(self, verbose: bool = False) -> None:
        """Загружает кэш из JSON.
        
        Args:
            verbose: Если True, выводит лог о загрузке. По умолчанию False для уменьшения шума в логах при параллельной обработке.
        """
        if not self._cache_path.exists():
            return
        with self._cache_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        with self._lock:
            for name, raw in data.get("symbols", {}).items():
                self._symbols[name] = SymbolInfo(
                    symbol_id=raw["symbol_id"],
                    symbol_name=raw["symbol_name"],
                    description=raw.get("description", ""),
                    digits=raw.get("digits", 5),
                    pip_location=raw.get("pip_location", -4),
                    swap_long=raw.get("swap_long", 0.0),
                    swap_short=raw.get("swap_short", 0.0),
                    swap_rollover3days=raw.get("swap_rollover3days", 3),
                    commission=raw.get("commission", 0.0),
                    spread=raw.get("spread", 0.0),
                    min_volume=raw.get("min_volume", 0.01),
                    max_volume=raw.get("max_volume", 100.0),
                    volume_step=raw.get("volume_step", 0.01),
                    currency=raw.get("currency", "USD"),
                    quote_currency=raw.get("quote_currency", "USD"),
                    updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                )
        if verbose:
            log.info("Loaded symbol info cache: %s symbols", len(self._symbols))

