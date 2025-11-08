from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


DATA_ROOT_ENV = "FOREX_DATA_ROOT"
DEFAULT_DATA_ROOT = Path("data")


@dataclass(slots=True)
class ApiCacheConfig:
    """Настройки кэширования HTTP-запросов к источникам данных."""

    cache_dir: Path = Path("cache/api")
    ttl_seconds: int = 900


@dataclass(slots=True)
class DataPipelineConfig:
    """
    Общие настройки конвейера загрузки данных.

    Attributes:
        market: Целевой рынок (например, 'moex').
        engine: Имя движка MOEX ('currency', 'futures' и т.д.).
        data_root: Корневая директория хранения данных.
        dataset_version: Версия набора данных (напр. 'v1', '2025Q1').
        api_cache: Настройки кэширования внешних API.
    """

    market: Literal["moex"] = "moex"
    engine: Literal["currency", "futures"] = "currency"
    board: Literal["CETS", "RFUD"] = "CETS"
    data_root: Path = field(
        default_factory=lambda: Path(os.environ.get(DATA_ROOT_ENV, DEFAULT_DATA_ROOT))
    )
    dataset_version: str = "v1"
    api_cache: ApiCacheConfig = field(default_factory=ApiCacheConfig)

    def versioned_root(self) -> Path:
        """Путь до директории с версией датасета."""
        return self.data_root / self.dataset_version

    def raw_root(self) -> Path:
        """Директория для сырых данных."""
        return self.versioned_root() / "raw"

    def curated_root(self) -> Path:
        """Директория для очищенных данных."""
        return self.versioned_root() / "curated"

    def metadata_root(self) -> Path:
        """Директория для метаданных и журналов валидации."""
        return self.versioned_root() / "meta"

