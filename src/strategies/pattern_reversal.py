"""
Стратегия на основе свечных паттернов разворота.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.patterns.candlestick import detect_hammer, detect_engulfing
from src.signals import FeatureConfig, compute_features
from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class PatternReversalStrategy(Strategy):
    """
    Стратегия на основе свечных паттернов разворота:
    - Hammer (молот) - сигнал на покупку
    - Bullish Engulfing - сигнал на покупку
    - Bearish Engulfing - сигнал на продажу
    
    Эти паттерны работают лучше всего в конце трендов и могут сигнализировать
    о развороте направления движения цены.
    """

    strategy_id: str = "pattern_reversal"
    atr_multiplier: float = 2.0
    min_atr: float = 0.0004
    risk_reward_ratio: float = 2.0
    min_adx: float = 15.0  # Фильтр по силе тренда
    min_rsi_oversold: float = 30.0  # RSI для LONG сигналов (перепроданность)
    max_rsi_overbought: float = 70.0  # RSI для SHORT сигналов (перекупленность)
    trend_confirmation_bars: int = 3  # Количество баров для подтверждения тренда
    require_trend_reversal: bool = True  # Требовать разворот тренда
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(
            risk_per_trade_pct=0.008, max_notional=150_000.0, min_notional=20_000.0
        )
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """
        Генерирует сигналы на основе свечных паттернов разворота.
        
        Args:
            df: DataFrame с колонками open, high, low, close, instrument
        
        Returns:
            Список сигналов для входа в позицию
        """
        if df.empty or len(df) < 50:
            return []

        signals: List[Signal] = []
        instrument = df.iloc[-1]["instrument"]
        price = float(df["close"].iloc[-1])

        # Вычисляем индикаторы для фильтрации
        config = FeatureConfig(
            name="pattern",
            window_short=20,
            window_long=50,
            additional_params={"adx_period": 14, "atr_period": 14},
        )
        features = compute_features(df.tail(100), config)

        adx = features.get("adx", default=0.0)
        atr = features.get("atr", default=0.0)
        rsi = features.get("rsi", default=50.0)
        ema_short = features.get("ema_short", default=price)
        ema_long = features.get("ema_long", default=price)

        # Базовые фильтры
        if adx < self.min_adx or atr < self.min_atr:
            return signals

        # Проверяем тренд для фильтрации разворотов
        is_downtrend = ema_short < ema_long
        is_uptrend = ema_short > ema_long
        
        # Проверяем последние бары для подтверждения тренда
        if len(df) >= self.trend_confirmation_bars:
            recent_closes = df.tail(self.trend_confirmation_bars)["close"]
            recent_downtrend = all(recent_closes.iloc[i] < recent_closes.iloc[i-1] 
                                   for i in range(1, len(recent_closes)))
            recent_uptrend = all(recent_closes.iloc[i] > recent_closes.iloc[i-1] 
                                for i in range(1, len(recent_closes)))
        else:
            recent_downtrend = is_downtrend
            recent_uptrend = is_uptrend

        # Обнаруживаем паттерны
        hammer_idx = detect_hammer(df)
        bullish_engulfing_idx = detect_engulfing(df, bullish=True)
        bearish_engulfing_idx = detect_engulfing(df, bullish=False)

        # LONG сигналы - требуем нисходящий тренд для разворота
        if (hammer_idx is not None or bullish_engulfing_idx is not None):
            # Фильтр: паттерн разворота должен быть в конце нисходящего тренда
            if self.require_trend_reversal and not (is_downtrend or recent_downtrend):
                return signals
            
            # Фильтр по RSI (перепроданность для LONG)
            if rsi > self.min_rsi_oversold + 10:  # Не слишком перепродан, но ниже среднего
                return signals
            
            stop_distance = self.atr_multiplier * atr
            notional = compute_position_size(instrument, stop_distance, self.risk)
            confidence = adjust_confidence(adx, self.min_adx)
            
            # Увеличиваем confidence если RSI в зоне перепроданности
            if rsi < self.min_rsi_oversold:
                confidence = min(1.0, confidence * 1.1)

            # Увеличиваем confidence если оба паттерна
            if hammer_idx is not None and bullish_engulfing_idx is not None:
                confidence = min(1.0, confidence * 1.2)

            entry_price = price
            stop_loss = entry_price - stop_distance
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
                    confidence=confidence,
                )
            )

        # SHORT сигналы - требуем восходящий тренд для разворота
        if bearish_engulfing_idx is not None:
            # Фильтр: паттерн разворота должен быть в конце восходящего тренда
            if self.require_trend_reversal and not (is_uptrend or recent_uptrend):
                return signals
            
            # Фильтр по RSI (перекупленность для SHORT)
            if rsi < self.max_rsi_overbought - 10:  # Не слишком перекуплен, но выше среднего
                return signals
            
            stop_distance = self.atr_multiplier * atr
            notional = compute_position_size(instrument, stop_distance, self.risk)
            confidence = adjust_confidence(adx, self.min_adx)
            
            # Увеличиваем confidence если RSI в зоне перекупленности
            if rsi > self.max_rsi_overbought:
                confidence = min(1.0, confidence * 1.1)

            entry_price = price
            stop_loss = entry_price + stop_distance
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
                    confidence=confidence,
                )
            )

        return signals

