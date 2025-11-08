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
    atr_multiplier: float = 2.0  # Увеличено с 1.8 для большего расстояния стоп-лосса
    min_atr: float = 0.0003
    adx_threshold: float = 20.0  # Увеличено с 18.0 для более сильных трендов
    risk_reward_ratio: float = 2.0  # Соотношение risk/reward (минимум 1:2)
    confirmation_bars: int = 2  # Количество баров подтверждения пробития
    min_pos_di_advantage: float = 2.0  # Минимальное преимущество +DI над -DI для LONG (и наоборот)
    avoid_hours: List[int] = field(default_factory=lambda: [22, 23, 0, 1, 2, 3, 4, 5])  # Часы для избегания (низкая ликвидность)
    use_support_resistance: bool = True  # Использовать уровни поддержки/сопротивления вместо простых max/min
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
        signals: List[Signal] = []

        # Проверяем базовые фильтры
        if atr < self.min_atr:
            return signals
        if pd.isna(adx) or adx < self.adx_threshold:
            return signals

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
                        breakout_long = True
                        entry_price = float(df.iloc[idx]["close"])  # Входим на цене закрытия последнего подтверждающего бара
            
            # Пробитие вниз: проверяем подтверждение несколькими барами
            if bar["low"] < low_break and not breakout_short:
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
                        breakout_short = True
                        entry_price_short = float(df.iloc[idx]["close"])  # Входим на цене закрытия последнего подтверждающего бара

        # Генерируем сигналы на основе пробитий
        # Улучшенное соотношение risk/reward: минимум 1:2
        if breakout_long and atr > 0:
            stop_distance = self.atr_multiplier * atr
            stop = entry_price - stop_distance
            take = entry_price + stop_distance * self.risk_reward_ratio  # Risk/Reward 1:2
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

