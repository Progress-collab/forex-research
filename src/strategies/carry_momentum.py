from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class CarryMomentumStrategy(Strategy):
    strategy_id: str = "carry_momentum"
    atr_multiplier: float = 2.0  # Увеличено с 1.5 для большего расстояния стоп-лосса
    min_adx: float = 20.0  # Увеличено с 18.0 для более сильных трендов
    min_atr: float = 0.0004
    swap_bias_threshold: float = 0.0
    risk_reward_ratio: float = 2.0  # Соотношение risk/reward (минимум 1:2)
    min_pos_di_advantage: float = 2.0  # Минимальное преимущество +DI над -DI для LONG (и наоборот)
    trend_confirmation_bars: int = 3  # Количество баров подтверждения тренда
    max_volatility_pct: float = 5.0  # Максимальная волатильность в процентах (ATR/price)
    min_volatility_pct: float = 0.1  # Минимальная волатильность в процентах
    avoid_hours: List[int] = field(default_factory=lambda: [22, 23, 0, 1, 2, 3, 4, 5])  # Часы для избегания
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.008, max_notional=180_000.0, min_notional=20_000.0)
    )
    session_windows: Dict[str, tuple[time, time]] = field(
        default_factory=lambda: {
            "USDJPY": (time(0, 0), time(12, 0)),
            "AUDJPY": (time(0, 0), time(10, 0)),
        }
    )

    def generate_signals(self, df: pd.DataFrame, swap_bias: float = 0.0) -> List[Signal]:
        """
        swap_bias > 0 означает предпочтение длинных позиций (положительный своп),
        swap_bias < 0 — коротких.
        """

        if df.empty or len(df) < 100:
            return []

        config = FeatureConfig(
            name="carry",
            window_short=20,
            window_long=50,
            additional_params={"adx_period": 14, "atr_period": 14},
        )
        features = compute_features(df.tail(150), config)

        ema_short = features.get("ema_short")
        ema_long = features.get("ema_long")
        adx = features.get("adx", default=0.0)
        atr = features.get("atr", default=0.0)
        pos_di = features.get("pos_di", default=0.0)
        neg_di = features.get("neg_di", default=0.0)
        price = float(df["close"].iloc[-1])
        instrument = df.iloc[-1]["instrument"]
        ts_time = df.index[-1].time() if isinstance(df.index, pd.DatetimeIndex) else time(12, 0)

        signals: List[Signal] = []
        
        # Базовые фильтры
        if adx < self.min_adx or atr < self.min_atr:
            return signals
        if not self._within_session(instrument, ts_time):
            return signals
        
        # Фильтр по времени дня
        if isinstance(df.index, pd.DatetimeIndex):
            current_hour = df.index[-1].hour
            if current_hour in self.avoid_hours:
                return signals
        
        # Фильтр по волатильности
        volatility_pct = (atr / price) * 100 if price > 0 else 0.0
        if volatility_pct > self.max_volatility_pct or volatility_pct < self.min_volatility_pct:
            return signals
        
        # Проверяем подтверждение тренда (последние N баров в одном направлении)
        if len(df) >= self.trend_confirmation_bars:
            recent_bars = df.tail(self.trend_confirmation_bars)
            # Для LONG: все последние бары должны быть выше EMA_long
            # Для SHORT: все последние бары должны быть ниже EMA_long
            long_confirmation = all(recent_bars["close"] > ema_long) if ema_long else False
            short_confirmation = all(recent_bars["close"] < ema_long) if ema_long else False
        else:
            long_confirmation = True
            short_confirmation = True

        # Улучшенное размещение стоп-лоссов и тейк-профитов с соотношением risk/reward 1:2
        stop_distance = self.atr_multiplier * atr
        notional = compute_position_size(instrument, stop_distance, self.risk)
        confidence = adjust_confidence(adx, self.min_adx)

        # LONG: EMA короткая > длинная, +DI > -DI, подтверждение тренда
        if (ema_short > ema_long and 
            swap_bias >= self.swap_bias_threshold and
            pos_di > neg_di + self.min_pos_di_advantage and
            long_confirmation):
            stop = price - stop_distance
            take = price + stop_distance * self.risk_reward_ratio  # Risk/Reward 1:2
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="LONG",
                    entry_price=price,
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=confidence,
                )
            )
        # SHORT: EMA короткая < длинная, -DI > +DI, подтверждение тренда
        elif (ema_short < ema_long and 
              swap_bias <= -self.swap_bias_threshold and
              neg_di > pos_di + self.min_pos_di_advantage and
              short_confirmation):
            stop = price + stop_distance
            take = price - stop_distance * self.risk_reward_ratio  # Risk/Reward 1:2
            signals.append(
                Signal(
                    strategy_id=self.strategy_id,
                    instrument=instrument,
                    direction="SHORT",
                    entry_price=price,
                    stop_loss=float(stop),
                    take_profit=float(take),
                    notional=notional,
                    confidence=confidence,
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

