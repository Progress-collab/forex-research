"""Скрипт для детального тестирования Head & Shoulders паттернов."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import pandas as pd
from src.patterns.chart import detect_head_shoulders_top, detect_head_shoulders_bottom

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def test_head_shoulders_detailed():
    """Детальное тестирование Head & Shoulders с отладочной информацией."""
    log.info("=" * 80)
    log.info("ДЕТАЛЬНОЕ ТЕСТИРОВАНИЕ HEAD & SHOULDERS")
    log.info("=" * 80)
    
    curated_dir = Path("data/v1/curated/ctrader")
    instrument = "EURUSD"
    period = "m15"
    
    data_path = curated_dir / f"{instrument}_{period}.parquet"
    if not data_path.exists():
        log.error("Данные не найдены: %s", data_path)
        return
    
    df = pd.read_parquet(data_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.set_index("utc_time").sort_index()
    
    log.info("\nЗагружено данных: %s баров", len(df))
    log.info("Период: %s - %s", df.index[0], df.index[-1])
    
    # Тестируем с разными параметрами
    lookbacks = [50, 100, 150, 200]
    tolerances = [0.01, 0.02, 0.03, 0.05]
    
    for lookback in lookbacks:
        for tolerance in tolerances:
            log.info("\n" + "-" * 80)
            log.info("Параметры: lookback=%s, tolerance=%.2f%%", lookback, tolerance * 100)
            log.info("-" * 80)
            
            # Тестируем на разных участках данных
            window_size = lookback * 2
            step = lookback
            
            found_hst = 0
            found_hsb = 0
            
            for start_idx in range(0, len(df) - window_size, step):
                window_df = df.iloc[start_idx:start_idx + window_size]
                
                hst = detect_head_shoulders_top(window_df, lookback=lookback, shoulder_tolerance=tolerance)
                hsb = detect_head_shoulders_bottom(window_df, lookback=lookback, shoulder_tolerance=tolerance)
                
                if hst:
                    found_hst += 1
                    left_idx, head_idx, right_idx = hst
                    log.info("  HST найден: %s - %s - %s", left_idx, head_idx, right_idx)
                    log.info("    Цены: %.5f - %.5f - %.5f", 
                            window_df.loc[left_idx, "high"],
                            window_df.loc[head_idx, "high"],
                            window_df.loc[right_idx, "high"])
                
                if hsb:
                    found_hsb += 1
                    left_idx, head_idx, right_idx = hsb
                    log.info("  HSB найден: %s - %s - %s", left_idx, head_idx, right_idx)
                    log.info("    Цены: %.5f - %.5f - %.5f", 
                            window_df.loc[left_idx, "low"],
                            window_df.loc[head_idx, "low"],
                            window_df.loc[right_idx, "low"])
            
            log.info("\nИтого найдено: HST=%s, HSB=%s", found_hst, found_hsb)
            
            if found_hst > 0 or found_hsb > 0:
                log.info("✓ Паттерны найдены с этими параметрами!")
                break
    
    # Теперь проверим на всем датасете с оптимальными параметрами
    log.info("\n" + "=" * 80)
    log.info("ПРОВЕРКА НА ВСЕМ ДАТАСЕТЕ")
    log.info("=" * 80)
    
    hst = detect_head_shoulders_top(df, lookback=150, shoulder_tolerance=0.03)
    hsb = detect_head_shoulders_bottom(df, lookback=150, shoulder_tolerance=0.03)
    
    log.info("HST (Top): %s", hst if hst else "не найден")
    log.info("HSB (Bottom): %s", hsb if hsb else "не найден")
    
    if hst:
        left_idx, head_idx, right_idx = hst
        log.info("\nHST детали:")
        log.info("  Левый индекс: %s", left_idx)
        log.info("  Голова индекс: %s", head_idx)
        log.info("  Правый индекс: %s", right_idx)
        log.info("  Левый high: %.5f", df.loc[left_idx, "high"])
        log.info("  Голова high: %.5f", df.loc[head_idx, "high"])
        log.info("  Правый high: %.5f", df.loc[right_idx, "high"])
    
    if hsb:
        left_idx, head_idx, right_idx = hsb
        log.info("\nHSB детали:")
        log.info("  Левый индекс: %s", left_idx)
        log.info("  Голова индекс: %s", head_idx)
        log.info("  Правый индекс: %s", right_idx)
        log.info("  Левый low: %.5f", df.loc[left_idx, "low"])
        log.info("  Голова low: %.5f", df.loc[head_idx, "low"])
        log.info("  Правый low: %.5f", df.loc[right_idx, "low"])


if __name__ == "__main__":
    test_head_shoulders_detailed()

