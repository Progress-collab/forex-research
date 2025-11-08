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
    lookback_hours: int = 16  # Уменьшено с 24 до 16 для более реалистичных breakouts
    atr_multiplier: float = 1.8
    min_atr: float = 0.0001  # Ослаблено с 0.0003 для большего количества сигналов
    adx_threshold: float = 15.0  # Снижено с 18.0 для более мягкого фильтра
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
        # Используем меньший check_window для проверки свежих пробитий
        check_window = 5  # Проверяем последние 5 баров на свежие пробития
        required_bars = lookback_bars + check_window
        
        if len(df) < required_bars:
            return []
        
        # Предыдущий период для определения уровней breakouts
        prev_period = df.iloc[-required_bars:-check_window]
        # Текущий период для проверки пробитий (последние check_window баров)
        current_period = df.iloc[-check_window:]
        
        if len(prev_period) < lookback_bars or len(current_period) < 1:
            return []

        # Определяем уровни breakouts из предыдущего периода
        high_break = prev_period["high"].max()
        low_break = prev_period["low"].min()
        last_row = df.iloc[-1]

        # Рассчитываем индикаторы
        features = compute_features(
            df.tail(min_bars),
            FeatureConfig(
                name="momentum",
                window_short=5,
                window_long=20,
                additional_params={"atr_period": 14, "adx_period": 14},
            ),
        )
        atr = features.get("atr", default=0.0)
        adx = features.get("adx", default=0.0)
        signals: List[Signal] = []

        # Проверяем фильтры
        if atr < self.min_atr:
            return signals
        if pd.isna(adx) or adx < self.adx_threshold:
            return signals

        # Проверяем пробития в текущем периоде
        # Ищем свежие пробития на последних барах (от новых к старым)
        breakout_long = False
        breakout_short = False
        entry_price = 0.0
        entry_price_short = 0.0
        
        # Проверяем последние бары на пробития (от новых к старым, чтобы найти свежие пробития)
        for i in range(min(check_window, len(current_period))):
            # Берем бар от последнего (i=0) к более старым (i увеличивается)
            bar = current_period.iloc[-1 - i]
            
            # Пробитие вверх (high пробил максимум предыдущего периода)
            if bar["high"] > high_break and not breakout_long:
                breakout_long = True
                # Используем high пробивающей свечи или уровень пробития, что выше
                entry_price = max(bar["high"], high_break)
            
            # Пробитие вниз (low пробил минимум предыдущего периода)
            if bar["low"] < low_break and not breakout_short:
                breakout_short = True
                # Используем low пробивающей свечи или уровень пробития, что ниже
                entry_price_short = min(bar["low"], low_break)

        # Генерируем сигналы на основе пробитий
        if breakout_long and atr > 0:
            stop = entry_price - self.atr_multiplier * atr
            take = entry_price + self.atr_multiplier * atr * 1.5
            notional = compute_position_size(last_row["instrument"], self.atr_multiplier * atr, self.risk)
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
            stop = entry_price_short + self.atr_multiplier * atr
            take = entry_price_short - self.atr_multiplier * atr * 1.5
            notional = compute_position_size(last_row["instrument"], self.atr_multiplier * atr, self.risk)
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

