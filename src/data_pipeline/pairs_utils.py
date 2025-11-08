from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import pandas as pd

log = logging.getLogger(__name__)


def load_pair_data(
    symbol1: str, symbol2: str, period: str, curated_dir: Path = Path("data/v1/curated/ctrader")
) -> pd.DataFrame | None:
    """
    Загружает данные для двух символов и синхронизирует их по времени.
    Возвращает DataFrame с колонками:
    - utc_time (индекс)
    - {symbol1}_open, {symbol1}_close, {symbol1}_high, {symbol1}_low, {symbol1}_volume
    - {symbol2}_open, {symbol2}_close, {symbol2}_high, {symbol2}_low, {symbol2}_volume
    """
    path1 = curated_dir / f"{symbol1}_{period}.parquet"
    path2 = curated_dir / f"{symbol2}_{period}.parquet"

    if not path1.exists() or not path2.exists():
        log.error("Не найдены файлы: %s или %s", path1, path2)
        return None

    df1 = pd.read_parquet(path1)
    df2 = pd.read_parquet(path2)

    df1["utc_time"] = pd.to_datetime(df1["utc_time"])
    df2["utc_time"] = pd.to_datetime(df2["utc_time"])

    df1 = df1.set_index("utc_time").sort_index()
    df2 = df2.set_index("utc_time").sort_index()

    # Переименовываем колонки для первого символа
    df1_renamed = df1.rename(columns={col: f"{symbol1}_{col}" for col in df1.columns if col != "instrument"})
    df2_renamed = df2.rename(columns={col: f"{symbol2}_{col}" for col in df2.columns if col != "instrument"})

    # Объединяем по времени (inner join - только общие временные метки)
    merged = pd.merge(df1_renamed, df2_renamed, left_index=True, right_index=True, how="inner")

    if merged.empty:
        log.warning("Нет общих временных меток для %s и %s", symbol1, symbol2)
        return None

    log.info("Синхронизировано %s строк для пары %s/%s", len(merged), symbol1, symbol2)
    return merged


def compute_spread(
    df: pd.DataFrame, symbol1: str, symbol2: str, method: str = "ratio"
) -> pd.Series:
    """
    Вычисляет спред между двумя символами.
    
    Args:
        df: DataFrame с синхронизированными данными
        symbol1: Первый символ
        symbol2: Второй символ
        method: "ratio" (отношение цен) или "diff" (разница)
    
    Returns:
        Series со спредом
    """
    close1 = df[f"{symbol1}_close"]
    close2 = df[f"{symbol2}_close"]

    if method == "ratio":
        return close1 / close2
    elif method == "diff":
        return close1 - close2
    else:
        raise ValueError(f"Неизвестный метод: {method}")


def compute_zscore(series: pd.Series, window: int = 100) -> pd.Series:
    """
    Вычисляет z-score для временного ряда (для pairs trading).
    """
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    return (series - rolling_mean) / rolling_std


def find_pairs_candidates(
    curated_dir: Path = Path("data/v1/curated/ctrader"), period: str = "m15", min_correlation: float = 0.7
) -> List[Tuple[str, str, float]]:
    """
    Находит потенциальные пары для pairs trading на основе корреляции.
    
    Returns:
        Список кортежей (symbol1, symbol2, correlation)
    """
    curated_dir = Path(curated_dir)
    parquet_files = list(curated_dir.glob(f"*_{period}.parquet"))
    symbols = [f.stem.replace(f"_{period}", "") for f in parquet_files]

    candidates = []
    for i, sym1 in enumerate(symbols):
        for sym2 in symbols[i + 1 :]:
            try:
                df = load_pair_data(sym1, sym2, period, curated_dir)
                if df is None or len(df) < 100:
                    continue
                spread = compute_spread(df, sym1, sym2, method="ratio")
                correlation = spread.corr(spread.shift(1))  # Автокорреляция для стабильности
                if correlation >= min_correlation:
                    candidates.append((sym1, sym2, correlation))
            except Exception as e:  # noqa: BLE001
                log.debug("Ошибка при анализе пары %s/%s: %s", sym1, sym2, e)
                continue

    return sorted(candidates, key=lambda x: x[2], reverse=True)

