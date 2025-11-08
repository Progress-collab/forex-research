from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.data_pipeline.symbol_info import SymbolInfoCache
from src.strategies import Signal, Strategy

log = logging.getLogger(__name__)


@dataclass(slots=True)
class StopTakeHistoryEntry:
    """Запись истории изменения стоп-лосса или тейк-профита."""
    timestamp: datetime
    stop_loss: float
    take_profit: float
    notional: float  # Размер позиции на этот момент
    reason: Optional[str] = None  # Причина изменения (trailing_stop, partial_close, etc.)


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
    stop_take_history: List[StopTakeHistoryEntry] = field(default_factory=list)
    exit_reason: Optional[str] = None


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
        verbose_cache_load: bool = False,
    ):
        self.curated_dir = curated_dir
        self.symbol_cache = SymbolInfoCache(cache_path=symbol_info_path)
        self.symbol_cache.load(verbose=verbose_cache_load)
        self.initial_capital = initial_capital
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps

    def _load_data(self, instrument: str, period: str = "m15") -> pd.DataFrame:
        """Загружает данные для инструмента."""
        data_path = self.curated_dir / f"{instrument}_{period}.parquet"
        if not data_path.exists():
            raise FileNotFoundError(f"Данные не найдены: {data_path}")
        
        df = pd.read_parquet(data_path)
        df["utc_time"] = pd.to_datetime(df["utc_time"])
        df = df.set_index("utc_time").sort_index()
        return df

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
        use_trailing_stop: bool = True,
        trailing_stop_pct: float = 0.5,  # Перемещать стоп при достижении 50% прибыли
        use_partial_close: bool = True,
        partial_close_pct: float = 0.5,  # Закрыть 50% позиции
        partial_close_at_pct: float = 0.5,  # При достижении 50% тейк-профита
    ) -> Optional[Trade]:
        """
        Симулирует сделку на основе сигнала и будущих данных.
        Поддерживает trailing stop и частичное закрытие позиций.
        """
        if future_data.empty:
            return None

        # Ограничиваем количество баров для поиска выхода
        search_data = future_data.head(max_bars)

        entry_price = signal.entry_price
        initial_stop_loss = signal.stop_loss
        take_profit = signal.take_profit
        direction = signal.direction
        initial_notional = signal.notional
        
        # Текущие значения для trailing stop и partial close
        current_stop_loss = initial_stop_loss
        remaining_notional = initial_notional
        partial_closed = False
        trailing_stop_activated = False
        
        # История изменений стоп-лоссов и тейк-профитов
        stop_take_history: List[StopTakeHistoryEntry] = []
        # Добавляем начальное состояние
        stop_take_history.append(StopTakeHistoryEntry(
            timestamp=entry_time,
            stop_loss=initial_stop_loss,
            take_profit=take_profit,
            notional=initial_notional,
            reason="entry"
        ))

        # Ищем точку выхода (стоп или тейк)
        exit_time = None
        exit_price = None
        exit_reason = None

        for idx, row in search_data.iterrows():
            high = row["high"]
            low = row["low"]
            close = row["close"]

            if direction == "LONG":
                # Вычисляем текущую прибыль
                current_profit_pct = (close - entry_price) / entry_price
                profit_to_take_pct = (take_profit - entry_price) / entry_price
                
                # Частичное закрытие при достижении 50% тейк-профита
                if use_partial_close and not partial_closed and profit_to_take_pct > 0:
                    if current_profit_pct >= profit_to_take_pct * partial_close_at_pct:
                        # Закрываем часть позиции
                        remaining_notional = initial_notional * (1 - partial_close_pct)
                        partial_closed = True
                        # Перемещаем стоп в безубыток после частичного закрытия
                        current_stop_loss = entry_price
                        # Сохраняем изменение в историю
                        stop_take_history.append(StopTakeHistoryEntry(
                            timestamp=idx,
                            stop_loss=current_stop_loss,
                            take_profit=take_profit,
                            notional=remaining_notional,
                            reason="partial_close"
                        ))
                
                # Trailing stop: перемещаем стоп при движении в прибыль
                if use_trailing_stop:
                    if current_profit_pct > 0:
                        # Активируем trailing stop при достижении определенного процента прибыли
                        if current_profit_pct >= profit_to_take_pct * trailing_stop_pct:
                            trailing_stop_activated = True
                            # Перемещаем стоп на определенный процент от текущей прибыли
                            trailing_stop_distance = (close - entry_price) * (1 - trailing_stop_pct)
                            new_stop = entry_price + trailing_stop_distance
                            if new_stop > current_stop_loss:
                                current_stop_loss = new_stop
                                # Сохраняем изменение в историю
                                stop_take_history.append(StopTakeHistoryEntry(
                                    timestamp=idx,
                                    stop_loss=current_stop_loss,
                                    take_profit=take_profit,
                                    notional=remaining_notional,
                                    reason="trailing_stop"
                                ))
                
                # Проверяем стоп-лосс (включая trailing stop)
                if low <= current_stop_loss:
                    exit_time = idx
                    exit_price = current_stop_loss
                    exit_reason = "stop_loss" if not trailing_stop_activated else "trailing_stop"
                    break
                # Проверяем тейк-профит
                if high >= take_profit:
                    exit_time = idx
                    exit_price = take_profit
                    exit_reason = "take_profit"
                    break
            else:  # SHORT
                # Вычисляем текущую прибыль
                current_profit_pct = (entry_price - close) / entry_price
                profit_to_take_pct = (entry_price - take_profit) / entry_price
                
                # Частичное закрытие при достижении 50% тейк-профита
                if use_partial_close and not partial_closed and profit_to_take_pct > 0:
                    if current_profit_pct >= profit_to_take_pct * partial_close_at_pct:
                        # Закрываем часть позиции
                        remaining_notional = initial_notional * (1 - partial_close_pct)
                        partial_closed = True
                        # Перемещаем стоп в безубыток после частичного закрытия
                        current_stop_loss = entry_price
                        # Сохраняем изменение в историю
                        stop_take_history.append(StopTakeHistoryEntry(
                            timestamp=idx,
                            stop_loss=current_stop_loss,
                            take_profit=take_profit,
                            notional=remaining_notional,
                            reason="partial_close"
                        ))
                
                # Trailing stop: перемещаем стоп при движении в прибыль
                if use_trailing_stop:
                    if current_profit_pct > 0:
                        # Активируем trailing stop при достижении определенного процента прибыли
                        if current_profit_pct >= profit_to_take_pct * trailing_stop_pct:
                            trailing_stop_activated = True
                            # Перемещаем стоп на определенный процент от текущей прибыли
                            trailing_stop_distance = (entry_price - close) * (1 - trailing_stop_pct)
                            new_stop = entry_price - trailing_stop_distance
                            if new_stop < current_stop_loss:
                                current_stop_loss = new_stop
                                # Сохраняем изменение в историю
                                stop_take_history.append(StopTakeHistoryEntry(
                                    timestamp=idx,
                                    stop_loss=current_stop_loss,
                                    take_profit=take_profit,
                                    notional=remaining_notional,
                                    reason="trailing_stop"
                                ))
                
                # Проверяем стоп-лосс (включая trailing stop)
                if high >= current_stop_loss:
                    exit_time = idx
                    exit_price = current_stop_loss
                    exit_reason = "stop_loss" if not trailing_stop_activated else "trailing_stop"
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
        
        # Добавляем финальное состояние в историю
        stop_take_history.append(StopTakeHistoryEntry(
            timestamp=exit_time,
            stop_loss=current_stop_loss,
            take_profit=take_profit,
            notional=remaining_notional,
            reason=exit_reason or "exit"
        ))

        # Рассчитываем PnL с учетом частичного закрытия
        if direction == "LONG":
            pnl = (exit_price - entry_price) / entry_price
        else:
            pnl = (entry_price - exit_price) / entry_price

        # Учитываем slippage и spread
        slippage_pct = self.slippage_bps / 10000
        
        # Получаем спред из symbol_info
        symbol_info = self.symbol_cache.get(signal.instrument)
        spread_pips = symbol_info.spread if symbol_info else 0.0
        # Переводим пипсы в проценты (для большинства валютных пар pip_location = -4, значит 1 пипс = 0.0001)
        pip_location = symbol_info.pip_location if symbol_info else -4
        spread_multiplier = 10 ** pip_location
        spread_pct = (spread_pips * spread_multiplier) / entry_price if entry_price > 0 else 0.0
        
        # Применяем slippage и spread
        if direction == "LONG":
            # LONG: вход по ask (close + spread/2), выход по bid (close - spread/2)
            entry_price_adj = entry_price * (1 + slippage_pct + spread_pct / 2)
            exit_price_adj = exit_price * (1 - slippage_pct - spread_pct / 2)
        else:
            # SHORT: вход по bid (close - spread/2), выход по ask (close + spread/2)
            entry_price_adj = entry_price * (1 - slippage_pct - spread_pct / 2)
            exit_price_adj = exit_price * (1 + slippage_pct + spread_pct / 2)

        pnl_adj = (exit_price_adj - entry_price_adj) / entry_price_adj if direction == "LONG" else (entry_price_adj - exit_price_adj) / entry_price_adj

        # Комиссия (на весь notional, включая частично закрытую позицию)
        commission_pct = self.commission_bps / 10000
        # Комиссия за вход
        entry_commission = initial_notional * commission_pct
        # Комиссия за частичное закрытие (если было)
        partial_commission = (initial_notional - remaining_notional) * commission_pct if partial_closed else 0.0
        # Комиссия за финальный выход
        exit_commission = remaining_notional * commission_pct
        commission = entry_commission + partial_commission + exit_commission

        # Своп (упрощенно - считаем дни удержания)
        # symbol_info уже получен выше для спреда
        swap_per_day = 0.0
        if symbol_info:
            swap_per_day = symbol_info.swap_long if direction == "LONG" else symbol_info.swap_short
            # Переводим в проценты от notional (упрощенно)
            swap_per_day_pct = swap_per_day / initial_notional if initial_notional > 0 else 0.0

        days_held = (exit_time - entry_time).total_seconds() / 86400
        
        # Своп начальной позиции до частичного закрытия
        swap_before_partial = initial_notional * swap_per_day_pct * days_held if not partial_closed else 0.0
        # Своп оставшейся позиции после частичного закрытия
        swap_after_partial = remaining_notional * swap_per_day_pct * days_held if partial_closed else 0.0
        swap_total = swap_before_partial + swap_after_partial

        # Итоговый PnL
        # PnL от частично закрытой позиции (если было)
        partial_pnl = 0.0
        if partial_closed:
            partial_close_price = take_profit * partial_close_at_pct + entry_price * (1 - partial_close_at_pct) if direction == "LONG" else entry_price * (1 + partial_close_at_pct) - take_profit * partial_close_at_pct
            partial_pnl_pct = (partial_close_price - entry_price) / entry_price if direction == "LONG" else (entry_price - partial_close_price) / entry_price
            partial_pnl = (initial_notional - remaining_notional) * partial_pnl_pct
        
        # PnL от оставшейся позиции
        remaining_pnl = remaining_notional * pnl_adj
        
        pnl_amount = partial_pnl + remaining_pnl
        net_pnl = pnl_amount - commission - swap_total

        return Trade(
            entry_time=entry_time,
            exit_time=exit_time,
            instrument=signal.instrument,
            direction=direction,
            entry_price=entry_price_adj,
            exit_price=exit_price_adj,
            stop_loss=current_stop_loss,  # Финальный стоп (может быть trailing)
            take_profit=take_profit,
            notional=initial_notional,  # Исходный размер позиции
            pnl=pnl_amount,
            pnl_pct=pnl_adj,
            commission=commission,
            swap=swap_total,
            net_pnl=net_pnl,
            stop_take_history=stop_take_history,
            exit_reason=exit_reason,
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

