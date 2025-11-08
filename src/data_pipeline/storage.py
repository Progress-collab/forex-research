from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .config import DataPipelineConfig


def ensure_directories(config: DataPipelineConfig) -> None:
    for path in (config.raw_root(), config.curated_root(), config.metadata_root()):
        path.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False))
            fp.write("\n")


def save_raw_candles(
    config: DataPipelineConfig,
    secid: str,
    interval: int,
    candles: Sequence[Mapping[str, object]],
) -> Path:
    ensure_directories(config)
    file_name = f"{secid.lower()}_candles_{interval}_{_timestamp()}.jsonl"
    path = config.raw_root() / "candles" / file_name
    write_jsonl(path, candles)
    return path


def save_metadata_report(
    config: DataPipelineConfig,
    secid: str,
    report: Mapping[str, object],
) -> Path:
    ensure_directories(config)
    file_name = f"{secid.lower()}_{_timestamp()}_metadata.json"
    path = config.metadata_root() / "securities" / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    return path

