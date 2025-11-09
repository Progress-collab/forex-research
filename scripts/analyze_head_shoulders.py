"""Скрипт для детального анализа почему Head & Shoulders не находится."""
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
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def find_peaks_detailed(df: pd.DataFrame, window: int = 3):
    """Находит пики с детальной информацией."""
    highs = df["high"]
    peaks = []
    
    for i in range(window, len(highs) - window):
        is_peak = True
        for j in range(i - window, i + window + 1):
            if j != i and highs.iloc[j] >= highs.iloc[i]:
                is_peak = False
                break
        if is_peak:
            peaks.append((i, highs.iloc[i]))
    
    return peaks


def analyze_head_shoulders_candidates(df: pd.DataFrame, lookback: int = 150):
    """Анализирует кандидатов на Head & Shoulders."""
    log.info("=" * 80)
    log.info("АНАЛИЗ КАНДИДАТОВ НА HEAD & SHOULDERS")
    log.info("=" * 80)
    
    recent = df.tail(lookback).copy()
    highs = recent["high"]
    
    # Находим пики
    peaks = find_peaks_detailed(recent, window=3)
    log.info("\nНайдено пиков: %s", len(peaks))
    
    if len(peaks) < 3:
        log.warning("Недостаточно пиков для Head & Shoulders")
        return
    
    # Показываем первые 10 пиков
    log.info("\nПервые 10 пиков:")
    for idx, (pos, price) in enumerate(peaks[:10]):
        log.info("  %s: позиция=%s, цена=%.5f, дата=%s", 
                idx, pos, price, recent.index[pos])
    
    # Ищем кандидатов на Head & Shoulders
    candidates = []
    
    for i in range(len(peaks) - 2):
        left_shoulder_idx, left_shoulder_price = peaks[i]
        
        for j in range(i + 1, len(peaks) - 1):
            head_idx, head_price = peaks[j]
            
            # Голова должна быть выше левого плеча
            if head_price <= left_shoulder_price:
                continue
            
            for k in range(j + 1, len(peaks)):
                right_shoulder_idx, right_shoulder_price = peaks[k]
                
                # Голова должна быть выше правого плеча
                if head_price <= right_shoulder_price:
                    continue
                
                # Плечи должны быть примерно на одном уровне
                shoulder_diff = abs(left_shoulder_price - right_shoulder_price) / max(left_shoulder_price, right_shoulder_price)
                
                # Голова должна быть заметно выше плеч
                avg_shoulder_price = (left_shoulder_price + right_shoulder_price) / 2
                head_advantage = (head_price - avg_shoulder_price) / avg_shoulder_price
                
                # Проверяем neckline
                between_left_head = recent.iloc[left_shoulder_idx:head_idx]
                between_head_right = recent.iloc[head_idx:right_shoulder_idx]
                neckline_left = between_left_head["low"].min()
                neckline_right = between_head_right["low"].min()
                neckline = max(neckline_left, neckline_right)
                
                candidates.append({
                    "left_idx": left_shoulder_idx,
                    "head_idx": head_idx,
                    "right_idx": right_shoulder_idx,
                    "left_price": left_shoulder_price,
                    "head_price": head_price,
                    "right_price": right_shoulder_price,
                    "shoulder_diff": shoulder_diff,
                    "head_advantage": head_advantage,
                    "neckline": neckline,
                    "avg_shoulder": avg_shoulder_price,
                })
    
    log.info("\nНайдено кандидатов: %s", len(candidates))
    
    if len(candidates) == 0:
        log.warning("Нет кандидатов, которые прошли базовые проверки")
        return
    
    # Показываем лучших кандидатов
    log.info("\nТоп-10 кандидатов (по head_advantage):")
    candidates_sorted = sorted(candidates, key=lambda x: x["head_advantage"], reverse=True)
    
    for idx, cand in enumerate(candidates_sorted[:10]):
        log.info("\nКандидат %s:", idx + 1)
        log.info("  Плечи: %.5f (левый) - %.5f (правый), разница=%.2f%%", 
                cand["left_price"], cand["right_price"], cand["shoulder_diff"] * 100)
        log.info("  Голова: %.5f, преимущество=%.2f%%", 
                cand["head_price"], cand["head_advantage"] * 100)
        log.info("  Neckline: %.5f, среднее плечо=%.5f", 
                cand["neckline"], cand["avg_shoulder"])
        log.info("  Neckline ниже плеч на: %.2f%%", 
                (cand["avg_shoulder"] - cand["neckline"]) / cand["avg_shoulder"] * 100)
        
        # Проверяем условия
        tolerance = 0.05  # 5%
        head_min = 0.01  # 1% минимум
        
        checks = {
            "shoulder_diff <= tolerance": cand["shoulder_diff"] <= tolerance,
            "head_advantage >= head_min": cand["head_advantage"] >= head_min,
            "neckline < avg_shoulder * 0.98": cand["neckline"] < cand["avg_shoulder"] * 0.98,
        }
        
        log.info("  Проверки:")
        for check, passed in checks.items():
            log.info("    %s: %s", check, "✓" if passed else "✗")
        
        if all(checks.values()):
            log.info("  ✓ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")


if __name__ == "__main__":
    curated_dir = Path("data/v1/curated/ctrader")
    instrument = "EURUSD"
    period = "m15"
    
    data_path = curated_dir / f"{instrument}_{period}.parquet"
    if not data_path.exists():
        log.error("Данные не найдены: %s", data_path)
        sys.exit(1)
    
    df = pd.read_parquet(data_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.set_index("utc_time").sort_index()
    
    log.info("Загружено данных: %s баров", len(df))
    log.info("Период: %s - %s", df.index[0], df.index[-1])
    
    # Анализируем на разных участках
    lookback = 200
    for start_idx in [0, len(df) // 4, len(df) // 2, len(df) * 3 // 4]:
        window_df = df.iloc[start_idx:start_idx + lookback * 2]
        log.info("\n" + "=" * 80)
        log.info("Анализ участка: %s - %s", window_df.index[0], window_df.index[-1])
        analyze_head_shoulders_candidates(window_df, lookback=lookback)

