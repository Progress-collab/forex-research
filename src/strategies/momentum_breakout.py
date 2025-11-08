from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class MomentumBreakoutStrategy(Strategy):
    strategy_id: str = "momentum_breakout"
    lookback_hours: int = 24
    atr_multiplier: float = 2.8  # Баланс между защитой и возможностью входа
    min_atr: float = 0.0003
    adx_threshold: float = 26.0  # Баланс между силой тренда и количеством сигналов
    risk_reward_ratio: float = 2.5  # Улучшенное соотношение риск/прибыль
    confirmation_bars: int = 3  # Баланс между подтверждением и количеством сигналов
    min_pos_di_advantage: float = 3.5  # Баланс между силой направления и количеством сигналов
    avoid_hours: List[int] = field(default_factory=lambda: [13, 15, 16, 17, 21, 22, 23, 0, 1, 2, 3, 4, 5])  # Только худшие часы
    use_support_resistance: bool = True
    min_rsi_long: float = 56.0  # Баланс между качеством и количеством сигналов
    max_rsi_short: float = 44.0  # Для SHORT сделок (если включены)
    max_volatility_pct: float = 0.13  # Баланс между избежанием высокой волатильности и возможностью входа
    avoid_down_trend_long: bool = True
    min_trend_strength: float = 0.0015  # Баланс между силой тренда и количеством сигналов
    enable_short_trades: bool = False  # Отключаем SHORT сделки, так как они не работают
    min_breakout_strength: float = 0.0003  # Минимальная сила пробития (более мягкий фильтр)
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.0075, max_notional=200_000.0, min_notional=20_000.0)
    )
    session_windows: Dict[str, tuple[time, time]] = field(
        default_factory=lambda: {
            "EURUSD": (time(7, 0), time(21, 0)),
            "GBPUSD": (time(7, 0), time(20, 0)),
            "XAUUSD": (time(10, 0), time(22, 0)),
        }
    )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        # Минимум баров для расчета индикаторов
        min_bars = 100
        lookback_bars = max(self.lookback_hours, 50)
        
        if df.empty or len(df) < min_bars + lookback_bars:
            return []

        # Разделяем данные на два периода:
        # 1. Предыдущий период (для определения максимума/минимума)
        # 2. Текущий период (для проверки пробития)
        check_window = 20  # Проверяем последние 20 баров на пробития
        prev_period = df.iloc[-lookback_bars-check_window:-check_window]  # Предыдущий период
        current_period = df.iloc[-check_window:]  # Окно для проверки пробития
        
        if len(prev_period) < lookback_bars or len(current_period) < 1:
            return []

        last_row = df.iloc[-1]

        # Рассчитываем индикаторы
        features = compute_features(
            df.tail(min_bars),
            FeatureConfig(
                name="momentum",
                window_short=5,
                window_long=20,
                additional_params={
                    "atr_period": 14,
                    "adx_period": 14,
                    "sr_period": 20,  # Для поддержки/сопротивления
                },
            ),
        )
        atr = features.get("atr", default=0.0)
        adx = features.get("adx", default=0.0)
        pos_di = features.get("pos_di", default=0.0)
        neg_di = features.get("neg_di", default=0.0)
        rsi = features.get("rsi", default=50.0)
        ema_short = features.get("ema_short", default=0.0)
        ema_long = features.get("ema_long", default=0.0)
        volatility_pct = features.get("volatility_pct", default=0.0)
        signals: List[Signal] = []

        # Проверяем базовые фильтры
        if atr < self.min_atr:
            return signals
        if pd.isna(adx) or adx < self.adx_threshold:
            return signals
        
        # Фильтр по волатильности (избегаем высокой волатильности)
        if volatility_pct > self.max_volatility_pct:
            return signals
        
        # Фильтр по силе тренда
        if len(df) >= 50:
            price_change = (df["close"].iloc[-1] - df["close"].iloc[-50]) / df["close"].iloc[-50]
            trend_strength = abs(price_change)
            if trend_strength < self.min_trend_strength:
                return signals
        
        # Определяем направление тренда
        trend_direction = "UP" if ema_short > ema_long else "DOWN" if ema_short < ema_long else "FLAT"

        # Фильтр по времени дня
        if isinstance(df.index, pd.DatetimeIndex):
            current_hour = df.index[-1].hour
            if current_hour in self.avoid_hours:
                return signals

        # Определяем уровни breakouts
        if self.use_support_resistance:
            # Используем уровни поддержки/сопротивления
            resistance_level = features.get("resistance_level", default=prev_period["high"].max())
            support_level = features.get("support_level", default=prev_period["low"].min())
            high_break = float(resistance_level)
            low_break = float(support_level)
        else:
            # Простые max/min
            high_break = prev_period["high"].max()
            low_break = prev_period["low"].min()

        # Проверяем пробития в текущем периоде
        # Ищем случаи, когда текущая или предыдущие свечи пробили уровни
        # Требуем подтверждения: цена должна закрыться выше/ниже уровня пробития
        breakout_long = False
        breakout_short = False
        entry_price = 0.0
        entry_price_short = 0.0
        
        # Проверяем последние бары на пробития с подтверждением
        for i in range(min(check_window, len(current_period))):
            idx = -1 - i
            bar = df.iloc[idx]
            
            # Пробитие вверх: проверяем подтверждение несколькими барами
            if bar["high"] > high_break and not breakout_long:
                # Проверяем силу пробития (цена должна пробить уровень на определенный процент)
                breakout_strength = (bar["high"] - high_break) / high_break
                if breakout_strength < self.min_breakout_strength:
                    continue
                
                # Проверяем подтверждение: последние N баров должны закрыться выше уровня
                confirmation_count = 0
                for j in range(min(self.confirmation_bars, check_window - i)):
                    check_idx = idx + j
                    if check_idx < len(df):
                        check_bar = df.iloc[check_idx]
                        if check_bar["close"] > high_break:
                            confirmation_count += 1
                
                if confirmation_count >= self.confirmation_bars:
                    # Проверяем направление ADX (+DI > -DI для LONG)
                    if pos_di > neg_di + self.min_pos_di_advantage:
                        # Фильтр по RSI для LONG (прибыльные сделки имеют RSI > 58)
                        if rsi >= self.min_rsi_long:
                            # Избегаем LONG в нисходящем тренде
                            if not (self.avoid_down_trend_long and trend_direction == "DOWN"):
                                # Дополнительная проверка: цена должна быть выше EMA short (подтверждение тренда)
                                if bar["close"] > ema_short:
                                    breakout_long = True
                                    entry_price = float(df.iloc[idx]["close"])  # Входим на цене закрытия последнего подтверждающего бара
            
            # Пробитие вниз: проверяем подтверждение несколькими барами (только если включены SHORT сделки)
            if self.enable_short_trades and bar["low"] < low_break and not breakout_short:
                # Проверяем силу пробития
                breakout_strength = (low_break - bar["low"]) / low_break
                if breakout_strength < self.min_breakout_strength:
                    continue
                
                # Проверяем подтверждение: последние N баров должны закрыться ниже уровня
                confirmation_count = 0
                for j in range(min(self.confirmation_bars, check_window - i)):
                    check_idx = idx + j
                    if check_idx < len(df):
                        check_bar = df.iloc[check_idx]
                        if check_bar["close"] < low_break:
                            confirmation_count += 1
                
                if confirmation_count >= self.confirmation_bars:
                    # Проверяем направление ADX (-DI > +DI для SHORT)
                    if neg_di > pos_di + self.min_pos_di_advantage:
                        # Фильтр по RSI для SHORT (очень строгий)
                        if rsi <= self.max_rsi_short:
                            # Дополнительная проверка: SHORT только в очень сильном нисходящем тренде
                            if trend_direction == "DOWN" and adx > self.adx_threshold + 10:
                                # Цена должна быть ниже EMA short
                                if bar["close"] < ema_short:
                                    breakout_short = True
                                    entry_price_short = float(df.iloc[idx]["close"])  # Входим на цене закрытия последнего подтверждающего бара

        # Генерируем сигналы на основе пробитий
        # Улучшенное соотношение risk/reward: минимум 1:2.5
        if breakout_long and atr > 0:
            stop_distance = self.atr_multiplier * atr
            stop = entry_price - stop_distance
            
            # Улучшенный расчет тейк-профита: используем более консервативный подход
            # Берем расстояние до следующего уровня сопротивления или используем risk/reward
            take = entry_price + stop_distance * self.risk_reward_ratio
            
            # Дополнительная проверка: стоп-лосс не должен быть слишком близко к текущей цене
            # и не должен быть ниже важного уровня поддержки
            if stop < entry_price * 0.998:  # Минимум 0.2% от цены входа
                notional = compute_position_size(last_row["instrument"], stop_distance, self.risk)
                signals.append(
                    Signal(
                        strategy_id=self.strategy_id,
                        instrument=last_row["instrument"],
                        direction="LONG",
                        entry_price=float(entry_price),
                        stop_loss=float(stop),
                        take_profit=float(take),
                        notional=notional,
                        confidence=adjust_confidence(adx, self.adx_threshold),
                    )
                )

        if breakout_short and atr > 0:
            stop_distance = self.atr_multiplier * atr
            stop = entry_price_short + stop_distance
            take = entry_price_short - stop_distance * self.risk_reward_ratio  # Risk/Reward 1:2
            notional = compute_position_size(last_row["instrument"], stop_distance, self.risk)
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=last_row["instrument"],
                    direction="SHORT",
                    entry_price=float(entry_price_short),
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=adjust_confidence(adx, self.adx_threshold),
                )
            )

        return signals

    def _within_session(self, instrument: str, ts_time: time) -> bool:
        window = self.session_windows.get(instrument.upper())
        if window is None:
            return True
        start, end = window
        if start <= end:
            return start <= ts_time <= end
        return ts_time >= start or ts_time <= end

