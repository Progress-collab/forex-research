from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


PIP_CONFIG: Dict[str, Dict[str, float]] = {
    "EURUSD": {"pip_size": 0.0001, "pip_value": 10.0},
    "GBPUSD": {"pip_size": 0.0001, "pip_value": 10.0},
    "USDJPY": {"pip_size": 0.01, "pip_value": 9.1},
    "XAUUSD": {"pip_size": 0.1, "pip_value": 10.0},
}


@dataclass(slots=True)
class RiskSettings:
    equity: float = 100_000.0
    risk_per_trade_pct: float = 0.006  # 0.6%
    max_notional: float = 150_000.0
    min_notional: float = 25_000.0

    def risk_amount(self) -> float:
        return self.equity * self.risk_per_trade_pct


def compute_position_size(instrument: str, stop_distance: float, settings: RiskSettings) -> float:
    info = PIP_CONFIG.get(instrument.upper())
    if info is None:
        return settings.min_notional

    pip_size = info["pip_size"]
    pip_value = info["pip_value"]
    if stop_distance <= 0:
        return settings.min_notional

    stop_pips = stop_distance / pip_size
    if stop_pips <= 0:
        return settings.min_notional

    notional = settings.risk_amount() / (stop_pips * pip_value)
    notional = max(settings.min_notional, min(settings.max_notional, notional))
    return float(notional)


def adjust_confidence(adx: float, threshold: float = 18.0) -> float:
    if adx <= 0:
        return 0.3
    score = min(1.0, max(0.0, (adx - threshold) / (threshold * 1.5)))
    return 0.4 + 0.6 * score


def compute_dynamic_position_size(
    instrument: str,
    stop_distance: float,
    settings: RiskSettings,
    volatility_pct: float = 0.0,
    adx: float = 0.0,
    adx_threshold: float = 20.0,
    current_drawdown_pct: float = 0.0,
    max_drawdown_pct: float = 0.15,  # Максимальный допустимый drawdown
) -> float:
    """
    Вычисляет динамический размер позиции на основе:
    - Волатильности (уменьшаем при высокой волатильности)
    - Силы тренда (увеличиваем при сильном тренде)
    - Текущего drawdown (уменьшаем при большом drawdown)
    
    Args:
        instrument: Инструмент торговли
        stop_distance: Расстояние до стоп-лосса
        settings: Настройки риска
        volatility_pct: Волатильность в процентах (ATR/price * 100)
        adx: Значение ADX (сила тренда)
        adx_threshold: Пороговое значение ADX
        current_drawdown_pct: Текущий drawdown портфеля в процентах
        max_drawdown_pct: Максимальный допустимый drawdown
    
    Returns:
        Размер позиции (notional)
    """
    # Базовый размер позиции
    base_notional = compute_position_size(instrument, stop_distance, settings)
    
    # Множитель на основе волатильности
    # При высокой волатильности уменьшаем размер позиции
    volatility_multiplier = 1.0
    if volatility_pct > 0:
        # Нормализуем волатильность (предполагаем нормальную волатильность ~0.5-1.0%)
        if volatility_pct > 2.0:  # Очень высокая волатильность
            volatility_multiplier = 0.5
        elif volatility_pct > 1.5:  # Высокая волатильность
            volatility_multiplier = 0.7
        elif volatility_pct < 0.3:  # Очень низкая волатильность
            volatility_multiplier = 0.8  # Немного уменьшаем, так как может быть ложный сигнал
    
    # Множитель на основе силы тренда
    # При сильном тренде увеличиваем размер позиции
    trend_multiplier = 1.0
    if adx > 0:
        if adx >= adx_threshold * 1.5:  # Очень сильный тренд
            trend_multiplier = 1.3
        elif adx >= adx_threshold * 1.2:  # Сильный тренд
            trend_multiplier = 1.15
        elif adx < adx_threshold:  # Слабый тренд
            trend_multiplier = 0.8
    
    # Множитель на основе drawdown
    # При большом drawdown уменьшаем размер позиции
    drawdown_multiplier = 1.0
    if current_drawdown_pct > 0:
        if current_drawdown_pct >= max_drawdown_pct * 0.8:  # Близко к максимальному drawdown
            drawdown_multiplier = 0.5
        elif current_drawdown_pct >= max_drawdown_pct * 0.5:  # Средний drawdown
            drawdown_multiplier = 0.7
        elif current_drawdown_pct >= max_drawdown_pct * 0.3:  # Небольшой drawdown
            drawdown_multiplier = 0.9
    
    # Итоговый размер позиции
    dynamic_notional = base_notional * volatility_multiplier * trend_multiplier * drawdown_multiplier
    
    # Ограничиваем минимальным и максимальным значениями
    dynamic_notional = max(settings.min_notional, min(settings.max_notional, dynamic_notional))
    
    return float(dynamic_notional)

