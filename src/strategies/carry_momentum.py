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
    atr_multiplier: float = 2.2  # Увеличено с 1.8 для большего расстояния стоп-лосса (все убыточные сделки закрылись по стопу)
    min_adx: float = 14.0  # Ослаблено с 18.0 для увеличения количества сделок
    min_atr: float = 0.0004
    swap_bias_threshold: float = 0.0
    risk_reward_ratio: float = 2.5  # Улучшенное соотношение risk/reward
    min_pos_di_advantage: float = 1.0  # Оптимизировано
    trend_confirmation_bars: int = 2  # Ослаблено с 4 до 2 для увеличения количества сделок
    max_volatility_pct: float = 0.15  # Максимальная волатильность в процентах (ATR/price)
    min_volatility_pct: float = 0.08  # Минимальная волатильность в процентах
    min_rsi_long: float = 50.0  # Минимальный RSI для LONG сделок
    max_rsi_short: float = 50.0  # Максимальный RSI для SHORT сделок
    enable_short_trades: bool = False  # Отключаем SHORT сделки, так как они плохо работают
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
        rsi = features.get("rsi", default=50.0)
        price = float(df["close"].iloc[-1])
        instrument = df.iloc[-1]["instrument"]
        ts_time = df.index[-1].time() if isinstance(df.index, pd.DatetimeIndex) else time(12, 0)

        signals: List[Signal] = []
        
        # Базовые фильтры
        if adx < self.min_adx or atr < self.min_atr:
            return signals
        if not self._within_session(instrument, ts_time):
            return signals
        
        # Фильтр по времени дня удален - стратегия торгует в любые часы
        
        # Фильтр по волатильности (используем volatility_pct из features)
        volatility_pct = features.get("volatility_pct", default=0.0)
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
            long_confirmation and
            rsi >= self.min_rsi_long):  # Добавлен фильтр по RSI
            stop = price - stop_distance
            take = price + stop_distance * self.risk_reward_ratio  # Risk/Reward 1:2.5
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
        # SHORT: EMA короткая < длинная, -DI > +DI, подтверждение тренда (только если включены)
        elif (self.enable_short_trades and
              ema_short < ema_long and 
              swap_bias <= -self.swap_bias_threshold and
              neg_di > pos_di + self.min_pos_di_advantage and
              short_confirmation and
              rsi <= self.max_rsi_short):  # Добавлен фильтр по RSI
            stop = price + stop_distance
            take = price - stop_distance * self.risk_reward_ratio  # Risk/Reward 1:2.5
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

