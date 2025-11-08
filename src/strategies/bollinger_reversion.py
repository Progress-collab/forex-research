from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class BollingerReversionStrategy(Strategy):
    """
    Стратегия mean reversion на основе Bollinger Bands.
    Вход при касании нижней полосы (для LONG) или верхней (для SHORT).
    """
    strategy_id: str = "bollinger_reversion"
    
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_oversold: float = 30.0  # RSI для подтверждения перепроданности
    rsi_overbought: float = 70.0  # RSI для подтверждения перекупленности
    adx_ceiling: float = 25.0  # Максимальный ADX (избегаем сильных трендов)
    atr_multiplier: float = 1.5
    min_atr: float = 0.0003
    risk_reward_ratio: float = 1.5  # Для mean reversion можно использовать меньший R/R
    
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.006, max_notional=150_000.0, min_notional=15_000.0)
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """
        Генерирует сигналы на основе Bollinger Bands для mean reversion.
        """
        if df.empty or len(df) < 100:
            return []
        
        # Вычисляем индикаторы
        features = compute_features(
            df.tail(100),
            FeatureConfig(
                name="bollinger_reversion",
                window_short=20,
                window_long=50,
                additional_params={
                    "atr_period": 14,
                    "adx_period": 14,
                    "rsi_period": 14,
                    "bb_period": self.bb_period,
                    "bb_std": self.bb_std,
                },
            ),
        )
        
        bb_upper = features.get("bb_upper", default=0.0)
        bb_middle = features.get("bb_middle", default=0.0)
        bb_lower = features.get("bb_lower", default=0.0)
        bb_position = features.get("bb_position", default=50.0)  # Позиция цены в полосах (0-100)
        rsi = features.get("rsi", default=50.0)
        adx = features.get("adx", default=0.0)
        atr = features.get("atr", default=0.0)
        
        signals: List[Signal] = []
        
        # Базовые фильтры
        if atr < self.min_atr:
            return signals
        # Для mean reversion избегаем сильных трендов
        if pd.isna(adx) or adx > self.adx_ceiling:
            return signals
        
        price = float(df["close"].iloc[-1])
        instrument = df.iloc[-1]["instrument"]
        
        # LONG: цена касается нижней полосы (перепроданность) и RSI < 30
        if bb_position < 10.0 and rsi < self.rsi_oversold:
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
                    confidence=adjust_confidence(adx, self.adx_ceiling * 0.5),  # Низкая уверенность для mean reversion
                )
            )
        
        # SHORT: цена касается верхней полосы (перекупленность) и RSI > 70
        elif bb_position > 90.0 and rsi > self.rsi_overbought:
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
                    confidence=adjust_confidence(adx, self.adx_ceiling * 0.5),  # Низкая уверенность для mean reversion
                )
            )
        
        return signals

