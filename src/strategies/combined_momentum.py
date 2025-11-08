from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src.signals import FeatureConfig, compute_features

from .base import Signal, Strategy
from .carry_momentum import CarryMomentumStrategy
from .momentum_breakout import MomentumBreakoutStrategy
from .utils import RiskSettings, adjust_confidence, compute_position_size


@dataclass(slots=True)
class CombinedMomentumStrategy(Strategy):
    """
    Комбинированная стратегия, объединяющая Momentum Breakout и Carry Momentum.
    Требует подтверждения от обеих стратегий для входа.
    """
    strategy_id: str = "combined_momentum"
    
    # Параметры для Momentum Breakout
    lookback_hours: int = 24
    atr_multiplier: float = 2.0
    min_atr: float = 0.0003
    adx_threshold: float = 20.0
    risk_reward_ratio: float = 2.0
    
    # Параметры для Carry Momentum
    min_adx_carry: float = 20.0
    swap_bias_threshold: float = 0.0
    
    # Комбинированные параметры
    require_both_signals: bool = True  # Требовать сигналы от обеих стратегий
    min_confidence: float = 0.6  # Минимальная уверенность для входа
    
    risk: RiskSettings = field(
        default_factory=lambda: RiskSettings(risk_per_trade_pct=0.007, max_notional=180_000.0, min_notional=20_000.0)
    )

    def generate_signals(self, df: pd.DataFrame, swap_bias: float = 0.0) -> List[Signal]:
        """
        Генерирует сигналы, комбинируя Momentum Breakout и Carry Momentum.
        """
        if df.empty or len(df) < 150:
            return []
        
        # Создаем экземпляры стратегий
        momentum_strategy = MomentumBreakoutStrategy(
            lookback_hours=self.lookback_hours,
            atr_multiplier=self.atr_multiplier,
            min_atr=self.min_atr,
            adx_threshold=self.adx_threshold,
            risk_reward_ratio=self.risk_reward_ratio,
            risk=self.risk,
        )
        
        carry_strategy = CarryMomentumStrategy(
            atr_multiplier=self.atr_multiplier,
            min_adx=self.min_adx_carry,
            swap_bias_threshold=self.swap_bias_threshold,
            risk_reward_ratio=self.risk_reward_ratio,
            risk=self.risk,
        )
        
        # Генерируем сигналы от обеих стратегий
        momentum_signals = momentum_strategy.generate_signals(df)
        carry_signals = carry_strategy.generate_signals(df, swap_bias=swap_bias)
        
        # Комбинируем сигналы
        combined_signals: List[Signal] = []
        
        # Если требуем обе стратегии, ищем совпадения
        if self.require_both_signals:
            for mom_sig in momentum_signals:
                for carry_sig in carry_signals:
                    # Проверяем совпадение направления и инструмента
                    if (mom_sig.direction == carry_sig.direction and 
                        mom_sig.instrument == carry_sig.instrument):
                        # Используем средние значения для цены входа и стопов
                        entry_price = (mom_sig.entry_price + carry_sig.entry_price) / 2
                        stop_loss = (mom_sig.stop_loss + carry_sig.stop_loss) / 2
                        take_profit = (mom_sig.take_profit + carry_sig.take_profit) / 2
                        confidence = (mom_sig.confidence + carry_sig.confidence) / 2
                        notional = (mom_sig.notional + carry_sig.notional) / 2
                        
                        # Проверяем минимальную уверенность
                        if confidence >= self.min_confidence:
                            combined_signals.append(
                                Signal(
                                    strategy_id=self.strategy_id,
                                    instrument=mom_sig.instrument,
                                    direction=mom_sig.direction,
                                    entry_price=entry_price,
                                    stop_loss=stop_loss,
                                    take_profit=take_profit,
                                    notional=notional,
                                    confidence=confidence,
                                )
                            )
        else:
            # Используем сигналы от любой стратегии, но с повышенной уверенностью
            all_signals = momentum_signals + carry_signals
            for sig in all_signals:
                if sig.confidence >= self.min_confidence:
                    combined_signals.append(sig)
        
        return combined_signals

