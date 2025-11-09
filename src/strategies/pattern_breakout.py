"""
Стратегия на основе графических паттернов (Double Top/Bottom).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.patterns.chart import detect_double_top, detect_double_bottom
from src.signals import FeatureConfig, compute_features
from .base import Signal, Strategy
from .utils import RiskSettings, compute_position_size


@dataclass(slots=True)
class PatternBreakoutStrategy(Strategy):
    """
    Стратегия на основе графических паттернов:
    - Double Bottom -> пробой вверх (LONG)
    - Double Top -> пробой вниз (SHORT)
    
    Эти паттерны работают как сигналы разворота после формирования
    классических графических фигур.
    """

    strategy_id: str = "pattern_breakout"
    atr_multiplier: float = 1.5
    min_atr: float = 0.0004
    risk_reward_ratio: float = 2.5
    breakout_confirmation_bars: int = 1  # Уменьшено с 2 до 1 для большего количества сигналов
    max_pattern_age_bars: int = 20  # Максимальный возраст паттерна (в барах)
    min_neckline_distance_pct: float = 0.001  # Минимальное расстояние до neckline для пробоя (0.1%)
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(
            risk_per_trade_pct=0.008, max_notional=150_000.0, min_notional=20_000.0
        )
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """
        Генерирует сигналы на основе графических паттернов.
        
        Args:
            df: DataFrame с колонками open, high, low, close, instrument
        
        Returns:
            Список сигналов для входа в позицию
        """
        if df.empty or len(df) < 100:
            return []

        signals: List[Signal] = []
        instrument = df.iloc[-1]["instrument"]
        price = float(df["close"].iloc[-1])

        # Вычисляем индикаторы
        config = FeatureConfig(
            name="pattern_breakout",
            window_short=20,
            window_long=50,
            additional_params={"adx_period": 14, "atr_period": 14},
        )
        features = compute_features(df.tail(150), config)

        atr = features.get("atr", default=0.0)
        if atr < self.min_atr:
            return signals

        # Обнаруживаем паттерны
        double_top = detect_double_top(df)
        double_bottom = detect_double_bottom(df)

        # LONG: Double Bottom с пробоем вверх
        if double_bottom is not None:
            bottom1_idx, bottom2_idx = double_bottom
            
            # Проверяем, что паттерн не слишком старый
            last_bottom_idx = max(bottom1_idx, bottom2_idx)
            if last_bottom_idx not in df.index:
                # Если индексы не совпадают, пропускаем
                pass
            else:
                # Находим позицию последнего дна в DataFrame
                last_bottom_pos = df.index.get_loc(last_bottom_idx)
                current_pos = len(df) - 1
                pattern_age = current_pos - last_bottom_pos
                
                if pattern_age <= self.max_pattern_age_bars:
                    # Neckline - максимум между двумя днами
                    between_data = df.loc[min(bottom1_idx, bottom2_idx):max(bottom1_idx, bottom2_idx)]
                    neckline = between_data["high"].max()
                    
                    # Проверяем пробой вверх (текущая цена выше neckline)
                    if price > neckline * (1 + self.min_neckline_distance_pct):
                        stop_distance = self.atr_multiplier * atr
                        notional = compute_position_size(instrument, stop_distance, self.risk)
                        
                        # Стоп-лосс ниже последнего дна
                        last_bottom_price = min(df.loc[bottom1_idx, "low"], df.loc[bottom2_idx, "low"])
                        stop_loss = last_bottom_price - (atr * 0.5)  # Немного ниже дна
                        
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
                                confidence=0.7,
                            )
                        )

        # SHORT: Double Top с пробоем вниз
        if double_top is not None:
            top1_idx, top2_idx = double_top
            
            # Проверяем, что паттерн не слишком старый
            last_top_idx = max(top1_idx, top2_idx)
            if last_top_idx not in df.index:
                # Если индексы не совпадают, пропускаем
                pass
            else:
                # Находим позицию последней вершины в DataFrame
                last_top_pos = df.index.get_loc(last_top_idx)
                current_pos = len(df) - 1
                pattern_age = current_pos - last_top_pos
                
                if pattern_age <= self.max_pattern_age_bars:
                    # Neckline - минимум между двумя вершинами
                    between_data = df.loc[min(top1_idx, top2_idx):max(top1_idx, top2_idx)]
                    neckline = between_data["low"].min()
                    
                    # Проверяем пробой вниз (текущая цена ниже neckline)
                    if price < neckline * (1 - self.min_neckline_distance_pct):
                        stop_distance = self.atr_multiplier * atr
                        notional = compute_position_size(instrument, stop_distance, self.risk)
                        
                        # Стоп-лосс выше последней вершины
                        last_top_price = max(df.loc[top1_idx, "high"], df.loc[top2_idx, "high"])
                        stop_loss = last_top_price + (atr * 0.5)  # Немного выше вершины
                        
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
                                confidence=0.7,
                            )
                        )

        return signals

