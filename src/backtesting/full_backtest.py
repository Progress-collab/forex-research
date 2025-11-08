from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.data_pipeline.symbol_info import SymbolInfoCache
from src.strategies import Signal, Strategy

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Trade:
    """Информация о сделке."""

    entry_time: datetime
    exit_time: datetime
    instrument: str
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    notional: float
    pnl: float
    pnl_pct: float
    commission: float
    swap: float
    net_pnl: float


@dataclass(slots=True)
class FullBacktestResult:
    """Результаты полного бэктеста."""

    strategy_id: str
    instrument: str
    period: str
    start_date: datetime
    end_date: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_commission: float
    total_swap: float
    net_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    recovery_factor: float
    profit_factor: float
    average_win: float
    average_loss: float
    equity_curve: List[float]
    trades: List[Trade]


class FullBacktestRunner:
    """Расширенный бэктестер для полных годовых данных."""

    def __init__(
        self,
        curated_dir: Path = Path("data/v1/curated/ctrader"),
        symbol_info_path: Path = Path("data/v1/ref/symbols_info.json"),
        initial_capital: float = 100_000.0,
        commission_bps: float = 0.5,
        slippage_bps: float = 1.5,
    ):
        self.curated_dir = curated_dir
        self.symbol_cache = SymbolInfoCache(cache_path=symbol_info_path)
        self.symbol_cache.load()
        self.initial_capital = initial_capital
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps

    def run(
        self,
        strategy: Strategy,
        instrument: str,
        period: str = "m15",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> FullBacktestResult:
        """
        Запускает полный бэктест стратегии на исторических данных.
        """
        # Загружаем данные
        data_path = self.curated_dir / f"{instrument}_{period}.parquet"
        if not data_path.exists():
            raise FileNotFoundError(f"Данные не найдены: {data_path}")

        df = pd.read_parquet(data_path)
        df["utc_time"] = pd.to_datetime(df["utc_time"])
        df = df.set_index("utc_time").sort_index()

        # Фильтруем по датам
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]

        if df.empty:
            raise ValueError(f"Нет данных для периода {start_date} - {end_date}")

        # Генерируем сигналы по скользящему окну
        trades: List[Trade] = []
        equity = [self.initial_capital]

        # Используем окно для генерации сигналов (например, последние 500 баров)
        window_size = 500
        step_size = 50  # Шаг для генерации сигналов

        i = window_size
        while i < len(df):
            window_df = df.iloc[i - window_size : i].copy()
            # Убеждаемся, что есть колонка instrument
            if "instrument" not in window_df.columns:
                if "symbol" in window_df.columns:
                    window_df["instrument"] = window_df["symbol"]
                else:
                    window_df["instrument"] = instrument
            
            # Убеждаемся, что индекс - это время
            if not isinstance(window_df.index, pd.DatetimeIndex):
                if "utc_time" in window_df.columns:
                    window_df = window_df.set_index("utc_time")

            try:
                signals = strategy.generate_signals(window_df)
                for signal in signals:
                    # Используем текущее время из индекса
                    entry_time = window_df.index[-1]
                    trade = self._simulate_trade(signal, df.iloc[i:], entry_time)
                    if trade:
                        trades.append(trade)
                        # Обновляем equity
                        new_equity = equity[-1] + trade.net_pnl
                        equity.append(max(0, new_equity))  # Не даем уйти в минус
            except Exception as e:  # noqa: BLE001
                log.debug("Ошибка при генерации сигналов: %s", e)

            i += step_size

        # Рассчитываем метрики
        return self._build_result(strategy.strategy_id, instrument, period, df.index[0], df.index[-1], trades, equity)

    def _simulate_trade(
        self,
        signal: Signal,
        future_data: pd.DataFrame,
        entry_time: datetime,
        max_bars: int = 200,
    ) -> Optional[Trade]:
        """
        Симулирует сделку на основе сигнала и будущих данных.
        """
        if future_data.empty:
            return None

        # Ограничиваем количество баров для поиска выхода
        search_data = future_data.head(max_bars)

        entry_price = signal.entry_price
        stop_loss = signal.stop_loss
        take_profit = signal.take_profit
        direction = signal.direction

        # Ищем точку выхода (стоп или тейк)
        exit_time = None
        exit_price = None
        exit_reason = None

        for idx, row in search_data.iterrows():
            high = row["high"]
            low = row["low"]
            close = row["close"]

            if direction == "LONG":
                # Проверяем стоп-лосс
                if low <= stop_loss:
                    exit_time = idx
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                    break
                # Проверяем тейк-профит
                if high >= take_profit:
                    exit_time = idx
                    exit_price = take_profit
                    exit_reason = "take_profit"
                    break
            else:  # SHORT
                # Проверяем стоп-лосс
                if high >= stop_loss:
                    exit_time = idx
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                    break
                # Проверяем тейк-профит
                if low <= take_profit:
                    exit_time = idx
                    exit_price = take_profit
                    exit_reason = "take_profit"
                    break

        # Если не нашли выхода, используем последнюю цену
        if exit_time is None:
            exit_time = search_data.index[-1]
            exit_price = search_data.iloc[-1]["close"]
            exit_reason = "timeout"

        # Рассчитываем PnL
        if direction == "LONG":
            pnl = (exit_price - entry_price) / entry_price
        else:
            pnl = (entry_price - exit_price) / entry_price

        # Учитываем slippage
        slippage_pct = self.slippage_bps / 10000
        if direction == "LONG":
            entry_price_adj = entry_price * (1 + slippage_pct)
            exit_price_adj = exit_price * (1 - slippage_pct)
        else:
            entry_price_adj = entry_price * (1 - slippage_pct)
            exit_price_adj = exit_price * (1 + slippage_pct)

        pnl_adj = (exit_price_adj - entry_price_adj) / entry_price_adj if direction == "LONG" else (entry_price_adj - exit_price_adj) / entry_price_adj

        # Комиссия
        commission_pct = self.commission_bps / 10000
        commission = signal.notional * commission_pct * 2  # Вход и выход

        # Своп (упрощенно - считаем дни удержания)
        symbol_info = self.symbol_cache.get(signal.instrument)
        swap_per_day = 0.0
        if symbol_info:
            swap_per_day = symbol_info.swap_long if direction == "LONG" else symbol_info.swap_short
            # Переводим в проценты от notional (упрощенно)
            swap_per_day_pct = swap_per_day / signal.notional if signal.notional > 0 else 0.0

        days_held = (exit_time - entry_time).total_seconds() / 86400
        swap_total = signal.notional * swap_per_day_pct * days_held

        # Итоговый PnL
        pnl_amount = signal.notional * pnl_adj
        net_pnl = pnl_amount - commission - swap_total

        return Trade(
            entry_time=entry_time,
            exit_time=exit_time,
            instrument=signal.instrument,
            direction=direction,
            entry_price=entry_price_adj,
            exit_price=exit_price_adj,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notional=signal.notional,
            pnl=pnl_amount,
            pnl_pct=pnl_adj,
            commission=commission,
            swap=swap_total,
            net_pnl=net_pnl,
        )

    def _build_result(
        self,
        strategy_id: str,
        instrument: str,
        period: str,
        start_date: datetime,
        end_date: datetime,
        trades: List[Trade],
        equity: List[float],
    ) -> FullBacktestResult:
        """Строит результат бэктеста из списка сделок."""
        if not trades:
            # Возвращаем пустой результат
            return FullBacktestResult(
                strategy_id=strategy_id,
                instrument=instrument,
                period=period,
                start_date=start_date,
                end_date=end_date,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                total_commission=0.0,
                total_swap=0.0,
                net_pnl=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                recovery_factor=0.0,
                profit_factor=0.0,
                average_win=0.0,
                average_loss=0.0,
                equity_curve=equity,
                trades=trades,
            )

        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl < 0]

        total_pnl = sum(t.pnl for t in trades)
        total_commission = sum(t.commission for t in trades)
        total_swap = sum(t.swap for t in trades)
        net_pnl = sum(t.net_pnl for t in trades)

        win_rate = len(winning_trades) / len(trades) if trades else 0.0

        # Sharpe Ratio (на основе daily returns)
        equity_series = pd.Series(equity)
        returns = equity_series.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            sharpe_ratio = float(np.sqrt(252) * returns.mean() / returns.std())
        else:
            sharpe_ratio = 0.0

        # Max Drawdown
        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak
        max_drawdown = float(drawdown.min())

        # Recovery Factor
        recovery_factor = net_pnl / abs(max_drawdown * self.initial_capital) if max_drawdown != 0 else float("inf")

        # Profit Factor
        gross_profit = sum(t.net_pnl for t in winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(t.net_pnl for t in losing_trades)) if losing_trades else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        # Average Win/Loss
        average_win = float(np.mean([t.net_pnl for t in winning_trades])) if winning_trades else 0.0
        average_loss = float(np.mean([t.net_pnl for t in losing_trades])) if losing_trades else 0.0

        return FullBacktestResult(
            strategy_id=strategy_id,
            instrument=instrument,
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_commission=total_commission,
            total_swap=total_swap,
            net_pnl=net_pnl,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            recovery_factor=recovery_factor,
            profit_factor=profit_factor,
            average_win=average_win,
            average_loss=average_loss,
            equity_curve=equity,
            trades=trades,
        )

