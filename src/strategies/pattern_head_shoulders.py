"""
Стратегия на основе паттерна Head & Shoulders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.patterns.chart import detect_head_shoulders_top, detect_head_shoulders_bottom
from src.signals import FeatureConfig, compute_features
from .base import Signal, Strategy
from .utils import RiskSettings, compute_position_size


@dataclass(slots=True)
class PatternHeadShouldersStrategy(Strategy):
    """
    Стратегия на основе паттерна Head & Shoulders:
    - Head & Shoulders Top -> пробой вниз (SHORT)
    - Head & Shoulders Bottom -> пробой вверх (LONG)
    
    Это один из самых надежных разворотных паттернов в техническом анализе.
    """

    strategy_id: str = "pattern_head_shoulders"
    atr_multiplier: float = 1.5
    min_atr: float = 0.0004
    risk_reward_ratio: float = 2.5
    max_pattern_age_bars: int = 30  # Максимальный возраст паттерна (в барах)
    min_neckline_distance_pct: float = 0.001  # Минимальное расстояние до neckline для пробоя (0.1%)
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(
            risk_per_trade_pct=0.008, max_notional=150_000.0, min_notional=20_000.0
        )
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """
        Генерирует сигналы на основе паттерна Head & Shoulders.
        
        Args:
            df: DataFrame с колонками open, high, low, close, instrument
        
        Returns:
            Список сигналов для входа в позицию
        """
        if df.empty or len(df) < 150:
            return []

        signals: List[Signal] = []
        instrument = df.iloc[-1]["instrument"]
        price = float(df["close"].iloc[-1])

        # Вычисляем индикаторы
        config = FeatureConfig(
            name="pattern_head_shoulders",
            window_short=20,
            window_long=50,
            additional_params={"adx_period": 14, "atr_period": 14},
        )
        features = compute_features(df.tail(200), config)

        atr = features.get("atr", default=0.0)
        if atr < self.min_atr:
            return signals

        # Обнаруживаем паттерны
        hst = detect_head_shoulders_top(df)
        hsb = detect_head_shoulders_bottom(df)

        # LONG: Head & Shoulders Bottom с пробоем вверх
        if hsb is not None:
            left_shoulder_idx, head_idx, right_shoulder_idx = hsb
            
            # Проверяем, что паттерн не слишком старый
            last_shoulder_idx = max(left_shoulder_idx, right_shoulder_idx)
            if last_shoulder_idx in df.index:
                last_shoulder_pos = df.index.get_loc(last_shoulder_idx)
                current_pos = len(df) - 1
                pattern_age = current_pos - last_shoulder_pos
                
                if pattern_age <= self.max_pattern_age_bars:
                    # Neckline - максимум между плечами
                    between_left_head = df.loc[min(left_shoulder_idx, head_idx):max(left_shoulder_idx, head_idx)]
                    between_head_right = df.loc[min(head_idx, right_shoulder_idx):max(head_idx, right_shoulder_idx)]
                    neckline_left = between_left_head["high"].max()
                    neckline_right = between_head_right["high"].max()
                    neckline = max(neckline_left, neckline_right)
                    
                    # Проверяем пробой вверх (текущая цена выше neckline)
                    if price > neckline * (1 + self.min_neckline_distance_pct):
                        stop_distance = self.atr_multiplier * atr
                        notional = compute_position_size(instrument, stop_distance, self.risk)
                        
                        # Стоп-лосс ниже головы
                        head_price = df.loc[head_idx, "low"]
                        stop_loss = head_price - (atr * 0.5)  # Немного ниже головы
                        
                        entry_price = price
                        take_profit = entry_price + (stop_distance * self.risk_reward_ratio)
                        
                        signals.append(
                            Signal(
                                strategy_id=self.strategy_id,
                                instrument=instrument,
                                direction="LONG",
                                entry_price=entry_price,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                notional=notional,
                                confidence=0.75,  # Высокая уверенность для Head & Shoulders
                            )
                        )

        # SHORT: Head & Shoulders Top с пробоем вниз
        if hst is not None:
            left_shoulder_idx, head_idx, right_shoulder_idx = hst
            
            # Проверяем, что паттерн не слишком старый
            last_shoulder_idx = max(left_shoulder_idx, right_shoulder_idx)
            if last_shoulder_idx in df.index:
                last_shoulder_pos = df.index.get_loc(last_shoulder_idx)
                current_pos = len(df) - 1
                pattern_age = current_pos - last_shoulder_pos
                
                if pattern_age <= self.max_pattern_age_bars:
                    # Neckline - минимум между плечами
                    between_left_head = df.loc[min(left_shoulder_idx, head_idx):max(left_shoulder_idx, head_idx)]
                    between_head_right = df.loc[min(head_idx, right_shoulder_idx):max(head_idx, right_shoulder_idx)]
                    neckline_left = between_left_head["low"].min()
                    neckline_right = between_head_right["low"].min()
                    neckline = min(neckline_left, neckline_right)
                    
                    # Проверяем пробой вниз (текущая цена ниже neckline)
                    if price < neckline * (1 - self.min_neckline_distance_pct):
                        stop_distance = self.atr_multiplier * atr
                        notional = compute_position_size(instrument, stop_distance, self.risk)
                        
                        # Стоп-лосс выше головы
                        head_price = df.loc[head_idx, "high"]
                        stop_loss = head_price + (atr * 0.5)  # Немного выше головы
                        
                        entry_price = price
                        take_profit = entry_price - (stop_distance * self.risk_reward_ratio)
                        
                        signals.append(
                            Signal(
                                strategy_id=self.strategy_id,
                                instrument=instrument,
                                direction="SHORT",
                                entry_price=entry_price,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                notional=notional,
                                confidence=0.75,  # Высокая уверенность для Head & Shoulders
                            )
                        )

        return signals

