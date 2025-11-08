from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd

from .schemas import FeatureConfig, FeatureSet


@dataclass(slots=True)
class FeatureCalculator:
    config: FeatureConfig

    def compute(self, df: pd.DataFrame) -> FeatureSet:
        """
        Ожидается DataFrame со столбцами:
        - open, high, low, close, volume
        - индекс или столбец datetime (не важно для расчёта)
        """

        data = df.copy()
        short = self.config.window_short
        long = self.config.window_long
        atr_period = int(self.config.additional_params.get("atr_period", 14))
        rsi_period = int(self.config.additional_params.get("rsi_period", 14))
        adx_period = int(self.config.additional_params.get("adx_period", 14))

        ema_short = data["close"].ewm(span=short, adjust=False).mean()
        ema_long = data["close"].ewm(span=long, adjust=False).mean()
        sma = data["close"].rolling(window=long, min_periods=long).mean()

        diff = data["close"].diff()
        gain = diff.clip(lower=0)
        loss = -diff.clip(upper=0)
        avg_gain = gain.rolling(window=rsi_period, min_periods=rsi_period).mean()
        avg_loss = loss.rolling(window=rsi_period, min_periods=rsi_period).mean()
        rs = avg_gain / (avg_loss.replace(0, np.nan))
        rsi = 100 - (100 / (1 + rs))

        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_period, min_periods=atr_period).mean()

        # ADX components
        up_move = data["high"].diff()
        down_move = -data["low"].diff()
        pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        atr_smoothed = tr.rolling(window=adx_period, min_periods=adx_period).mean()
        
        # Вычисляем DI
        pos_dm_rolled = pd.Series(pos_dm, index=data.index).rolling(adx_period).mean()
        neg_dm_rolled = pd.Series(neg_dm, index=data.index).rolling(adx_period).mean()
        
        # Избегаем деления на ноль
        pos_di = pd.Series(index=data.index, dtype=float)
        neg_di = pd.Series(index=data.index, dtype=float)
        
        valid_mask = atr_smoothed > 0
        pos_di.loc[valid_mask] = 100 * (pos_dm_rolled.loc[valid_mask] / atr_smoothed.loc[valid_mask])
        neg_di.loc[valid_mask] = 100 * (neg_dm_rolled.loc[valid_mask] / atr_smoothed.loc[valid_mask])
        
        # Вычисляем DX
        di_sum = pos_di + neg_di
        dx = pd.Series(index=data.index, dtype=float)
        valid_dx_mask = di_sum > 0
        dx.loc[valid_dx_mask] = (abs(pos_di.loc[valid_dx_mask] - neg_di.loc[valid_dx_mask]) / di_sum.loc[valid_dx_mask]) * 100
        dx = dx.replace([np.inf, -np.inf], np.nan)
        
        # ADX - сглаженный DX
        adx = dx.rolling(window=adx_period, min_periods=adx_period).mean()

        # MACD
        macd_fast = int(self.config.additional_params.get("macd_fast", 12))
        macd_slow = int(self.config.additional_params.get("macd_slow", 26))
        macd_signal = int(self.config.additional_params.get("macd_signal", 9))
        
        ema_fast = data["close"].ewm(span=macd_fast, adjust=False).mean()
        ema_slow = data["close"].ewm(span=macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        macd_signal_line = macd_line.ewm(span=macd_signal, adjust=False).mean()
        macd_histogram = macd_line - macd_signal_line

        # Bollinger Bands
        bb_period = int(self.config.additional_params.get("bb_period", 20))
        bb_std = float(self.config.additional_params.get("bb_std", 2.0))
        
        bb_sma = data["close"].rolling(window=bb_period, min_periods=bb_period).mean()
        bb_std_dev = data["close"].rolling(window=bb_period, min_periods=bb_period).std()
        bb_upper = bb_sma + (bb_std_dev * bb_std)
        bb_lower = bb_sma - (bb_std_dev * bb_std)
        bb_width = (bb_upper - bb_lower) / bb_sma * 100  # Ширина полос в процентах
        bb_position = (data["close"] - bb_lower) / (bb_upper - bb_lower) * 100  # Позиция цены в полосах (0-100)

        # Support/Resistance уровни (упрощенный метод на основе локальных минимумов/максимумов)
        sr_period = int(self.config.additional_params.get("sr_period", 20))
        sr_lookback = min(sr_period, len(data))
        
        # Находим локальные максимумы и минимумы
        if sr_lookback > 0:
            recent_data = data.tail(sr_lookback * 2)
            # Локальные максимумы (resistance)
            resistance_levels = recent_data["high"].rolling(window=sr_period, center=True).max()
            # Локальные минимумы (support)
            support_levels = recent_data["low"].rolling(window=sr_period, center=True).min()
            
            # Ближайшие уровни
            current_price = data["close"].iloc[-1]
            resistance_above = resistance_levels[resistance_levels > current_price]
            support_below = support_levels[support_levels < current_price]
            
            nearest_resistance = float(resistance_above.min()) if len(resistance_above) > 0 else float(current_price * 1.01)
            nearest_support = float(support_below.max()) if len(support_below) > 0 else float(current_price * 0.99)
            
            # Расстояние до уровней в процентах
            resistance_distance_pct = (nearest_resistance - current_price) / current_price * 100
            support_distance_pct = (current_price - nearest_support) / current_price * 100
        else:
            nearest_resistance = float(data["close"].iloc[-1] * 1.01)
            nearest_support = float(data["close"].iloc[-1] * 0.99)
            resistance_distance_pct = 1.0
            support_distance_pct = 1.0

        # Добавляем +DI и -DI в значения
        pos_di_value = float(pos_di.iloc[-1]) if not pd.isna(pos_di.iloc[-1]) else 0.0
        neg_di_value = float(neg_di.iloc[-1]) if not pd.isna(neg_di.iloc[-1]) else 0.0

        values: Dict[str, float] = {
            "ema_short": float(ema_short.iloc[-1]),
            "ema_long": float(ema_long.iloc[-1]),
            "sma_long": float(sma.iloc[-1]),
            "atr": float(atr.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "adx": float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0,
            "pos_di": pos_di_value,
            "neg_di": neg_di_value,
            # MACD
            "macd": float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0,
            "macd_signal": float(macd_signal_line.iloc[-1]) if not pd.isna(macd_signal_line.iloc[-1]) else 0.0,
            "macd_histogram": float(macd_histogram.iloc[-1]) if not pd.isna(macd_histogram.iloc[-1]) else 0.0,
            # Bollinger Bands
            "bb_upper": float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else float(data["close"].iloc[-1]),
            "bb_middle": float(bb_sma.iloc[-1]) if not pd.isna(bb_sma.iloc[-1]) else float(data["close"].iloc[-1]),
            "bb_lower": float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else float(data["close"].iloc[-1]),
            "bb_width": float(bb_width.iloc[-1]) if not pd.isna(bb_width.iloc[-1]) else 0.0,
            "bb_position": float(bb_position.iloc[-1]) if not pd.isna(bb_position.iloc[-1]) else 50.0,
            # Support/Resistance
            "resistance_level": nearest_resistance,
            "support_level": nearest_support,
            "resistance_distance_pct": resistance_distance_pct,
            "support_distance_pct": support_distance_pct,
            # Волатильность (ATR относительно цены в процентах)
            "volatility_pct": float((atr.iloc[-1] / data["close"].iloc[-1]) * 100) if data["close"].iloc[-1] > 0 else 0.0,
        }
        
        return FeatureSet(values=values)


def compute_features(df: pd.DataFrame, config: FeatureConfig) -> FeatureSet:
    calculator = FeatureCalculator(config)
    return calculator.compute(df)

