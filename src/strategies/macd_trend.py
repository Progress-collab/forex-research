from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class MACDTrendStrategy(Strategy):
    """
    Стратегия на основе MACD индикатора для определения тренда.
    Вход при пересечении MACD линии и сигнальной линии.
    """
    strategy_id: str = "macd_trend"
    
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    adx_threshold: float = 20.0  # Минимальный ADX для фильтрации
    atr_multiplier: float = 2.0
    min_atr: float = 0.0003
    risk_reward_ratio: float = 2.0
    
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.0075, max_notional=200_000.0, min_notional=20_000.0)
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """
        Генерирует сигналы на основе MACD.
        """
        if df.empty or len(df) < 100:
            return []
        
        # Вычисляем индикаторы
        features = compute_features(
            df.tail(100),
            FeatureConfig(
                name="macd_trend",
                window_short=20,
                window_long=50,
                additional_params={
                    "atr_period": 14,
                    "adx_period": 14,
                    "macd_fast": self.macd_fast,
                    "macd_slow": self.macd_slow,
                    "macd_signal": self.macd_signal,
                },
            ),
        )
        
        macd = features.get("macd", default=0.0)
        macd_signal = features.get("macd_signal", default=0.0)
        macd_histogram = features.get("macd_histogram", default=0.0)
        adx = features.get("adx", default=0.0)
        atr = features.get("atr", default=0.0)
        
        signals: List[Signal] = []
        
        # Базовые фильтры
        if atr < self.min_atr:
            return signals
        if pd.isna(adx) or adx < self.adx_threshold:
            return signals
        
        price = float(df["close"].iloc[-1])
        instrument = df.iloc[-1]["instrument"]
        
        # Определяем направление тренда
        # LONG: MACD пересекает сигнальную линию снизу вверх (бычий крест)
        # SHORT: MACD пересекает сигнальную линию сверху вниз (медвежий крест)
        
        # Проверяем предыдущее значение MACD для определения пересечения
        if len(df) >= 2:
            prev_features = compute_features(
                df.tail(100).iloc[:-1],
                FeatureConfig(
                    name="macd_trend",
                    window_short=20,
                    window_long=50,
                    additional_params={
                        "atr_period": 14,
                        "adx_period": 14,
                        "macd_fast": self.macd_fast,
                        "macd_slow": self.macd_slow,
                        "macd_signal": self.macd_signal,
                    },
                ),
            )
            prev_macd = prev_features.get("macd", default=0.0)
            prev_macd_signal = prev_features.get("macd_signal", default=0.0)
            
            # Бычий крест: MACD пересекает сигнальную линию снизу вверх
            if (prev_macd <= prev_macd_signal and macd > macd_signal and macd_histogram > 0):
                stop_distance = self.atr_multiplier * atr
                stop = price - stop_distance
                take = price + stop_distance * self.risk_reward_ratio
                notional = compute_position_size(instrument, stop_distance, self.risk)
                
                signals.append(
                    Signal(
                        strategy_id=self.strategy_id,
                        instrument=instrument,
                        direction="LONG",
                        entry_price=price,
                        stop_loss=float(stop),
                        take_profit=float(take),
                        notional=notional,
                        confidence=adjust_confidence(adx, self.adx_threshold),
                    )
                )
            
            # Медвежий крест: MACD пересекает сигнальную линию сверху вниз
            elif (prev_macd >= prev_macd_signal and macd < macd_signal and macd_histogram < 0):
                stop_distance = self.atr_multiplier * atr
                stop = price + stop_distance
                take = price - stop_distance * self.risk_reward_ratio
                notional = compute_position_size(instrument, stop_distance, self.risk)
                
                signals.append(
                    Signal(
                        strategy_id=self.strategy_id,
                        instrument=instrument,
                        direction="SHORT",
                        entry_price=price,
                        stop_loss=float(stop),
                        take_profit=float(take),
                        notional=notional,
                        confidence=adjust_confidence(adx, self.adx_threshold),
                    )
                )
        
        return signals

