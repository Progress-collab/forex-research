from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class FeatureConfig:
    """
    Конфигурация вычисления индикаторов для стратегии.

    Attributes:
        name: Название набора индикаторов.
        window_short: Короткое окно (например, для EMA, RSI).
        window_long: Длинное окно (например, для EMA).
        additional_params: Произвольные настройки (ATR период, ADX и т.п.).
    """

    name: str
    window_short: int
    window_long: int
    additional_params: Dict[str, float | int] = field(default_factory=dict)


@dataclass(slots=True)
class FeatureSet:
    """
    Представление рассчитанных индикаторов (ключ -> значение).
    """

    values: Dict[str, float]

    def get(self, key: str, default: float = 0.0) -> float:
        return float(self.values.get(key, default))

