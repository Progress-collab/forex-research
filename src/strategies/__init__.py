"""
Набор прототипов форекс-стратегий.
"""

from .base import Signal, Strategy
from .momentum_breakout import MomentumBreakoutStrategy
from .mean_reversion import MeanReversionStrategy
from .carry_momentum import CarryMomentumStrategy
from .intraday_liquidity_breakout import IntradayLiquidityBreakoutStrategy
from .volatility_compression import VolatilityCompressionBreakoutStrategy
from .pairs_trading import PairsTradingStrategy
from .news_momentum import NewsMomentumStrategy

__all__ = [
    "Signal",
    "Strategy",
    "MomentumBreakoutStrategy",
    "MeanReversionStrategy",
    "CarryMomentumStrategy",
    "IntradayLiquidityBreakoutStrategy",
    "VolatilityCompressionBreakoutStrategy",
    "PairsTradingStrategy",
    "NewsMomentumStrategy",
]

