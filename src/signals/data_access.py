from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.data_pipeline.config import DataPipelineConfig


@dataclass(slots=True)
class CandleLoader:
    config: DataPipelineConfig

    def load_recent(self, instrument: str, limit: int = 500) -> pd.DataFrame:
        """
        Загружает последние `limit` свечей из директории raw/candles.
        Предполагается наличие файлов вида `{instrument}_candles_*.jsonl`.
        """

        root = self.config.raw_root() / "candles"
        pattern = f"{instrument.lower()}_candles_"
        files = sorted(root.glob(f"{pattern}*.jsonl"))
        if not files:
            raise FileNotFoundError(f"Не найдены свечи для {instrument} в {root}")

        frames = [pd.read_json(path, lines=True) for path in files[-3:]]
        df = pd.concat(frames, ignore_index=True)
        df = df.drop_duplicates(subset=["end"]).sort_values("end")
        df = df.tail(limit)
        df["instrument"] = instrument
        df = df.rename(columns=str.lower)
        df["end"] = pd.to_datetime(df["end"])
        return df


def merge_instruments(loader: CandleLoader, instruments: Iterable[str], limit: int = 500) -> dict[str, pd.DataFrame]:
    return {inst: loader.load_recent(inst, limit=limit) for inst in instruments}

