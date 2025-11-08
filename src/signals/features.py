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

        values: Dict[str, float] = {
            "ema_short": float(ema_short.iloc[-1]),
            "ema_long": float(ema_long.iloc[-1]),
            "sma_long": float(sma.iloc[-1]),
            "atr": float(atr.iloc[-1]),
            "rsi": float(rsi.iloc[-1]),
            "adx": float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0,
        }
        return FeatureSet(values=values)


def compute_features(df: pd.DataFrame, config: FeatureConfig) -> FeatureSet:
    calculator = FeatureCalculator(config)
    return calculator.compute(df)

