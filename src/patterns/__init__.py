"""
Модуль распознавания свечных и графических паттернов.
Основан на логике Patternz (Thomas Bulkowski).
"""

from .candlestick import detect_hammer, detect_engulfing, detect_doji
from .chart import detect_double_top, detect_double_bottom, detect_head_shoulders_top, detect_head_shoulders_bottom

__all__ = [
    "detect_hammer",
    "detect_engulfing",
    "detect_doji",
    "detect_double_top",
    "detect_double_bottom",
    "detect_head_shoulders_top",
    "detect_head_shoulders_bottom",
]

