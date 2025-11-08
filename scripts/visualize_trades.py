"""Скрипт для визуализации сделок на ценовом графике."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional, Dict

# Добавляем корень проекта в sys.path для импорта модулей
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import matplotlib.pyplot as plt
import pandas as pd

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner, Trade
from src.strategies import (
    MomentumBreakoutStrategy,
    CarryMomentumStrategy,
    MeanReversionStrategy,
    CombinedMomentumStrategy,
    MACDTrendStrategy,
    BollingerReversionStrategy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load_trades_from_backtest(
    strategy_name: str,
    instrument: str,
    period: str = "m15",
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    params: Optional[Dict] = None,
) -> tuple[pd.DataFrame, List[Trade]]:
    """Загружает данные и запускает бэктест для получения сделок."""
    runner = FullBacktestRunner(curated_dir=curated_dir)
    
    # Создаем стратегию (можно расширить для других стратегий)
    strategy_map = {
        "momentum_breakout": MomentumBreakoutStrategy,
        "carry_momentum": CarryMomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "combined_momentum": CombinedMomentumStrategy,
        "macd_trend": MACDTrendStrategy,
        "bollinger_reversion": BollingerReversionStrategy,
    }
    
    if strategy_name not in strategy_map:
        raise ValueError(f"Неизвестная стратегия: {strategy_name}. Доступные: {list(strategy_map.keys())}")
    
    # Создаем стратегию с параметрами если они указаны
    if params:
        strategy = strategy_map[strategy_name](**params)
    else:
        strategy = strategy_map[strategy_name]()
    
    result = runner.run(strategy, instrument, period)
    df = runner._load_data(instrument, period)
    return df, result.trades


def load_trades_from_file(trades_file: Path) -> List[Trade]:
    """Загружает сделки из JSON файла."""
    with trades_file.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    
    trades = []
    for trade_data in data.get("trades", []):
        # Преобразуем данные в Trade объект
        trade = Trade(
            entry_time=pd.to_datetime(trade_data["entry_time"]),
            exit_time=pd.to_datetime(trade_data["exit_time"]),
            instrument=trade_data["instrument"],
            direction=trade_data["direction"],
            entry_price=trade_data["entry_price"],
            exit_price=trade_data["exit_price"],
            stop_loss=trade_data["stop_loss"],
            take_profit=trade_data["take_profit"],
            notional=trade_data["notional"],
            pnl=trade_data["pnl"],
            pnl_pct=trade_data["pnl_pct"],
            commission=trade_data["commission"],
            swap=trade_data["swap"],
            net_pnl=trade_data["net_pnl"],
            stop_take_history=[],  # TODO: загрузить историю если есть
            exit_reason=trade_data.get("exit_reason"),
        )
        trades.append(trade)
    
    return trades


def visualize_trades(
    df: pd.DataFrame,
    trades: List[Trade],
    output_path: Optional[Path] = None,
    show_plot: bool = True,
    trade_filter: Optional[str] = None,
) -> None:
    """
    Визуализирует сделки на ценовом графике.
    
    Args:
        df: DataFrame с ценовыми данными (индекс - время, колонки: open, high, low, close)
        trades: Список сделок для визуализации
        output_path: Путь для сохранения графика
        show_plot: Показывать ли график
        trade_filter: Фильтр сделок ('winning', 'losing', None для всех)
    """
    if not trades:
        log.warning("Нет сделок для визуализации")
        return
    
    # Фильтруем сделки если нужно
    if trade_filter == "winning":
        trades = [t for t in trades if t.net_pnl > 0]
    elif trade_filter == "losing":
        trades = [t for t in trades if t.net_pnl <= 0]
    
    if not trades:
        log.warning("Нет сделок после фильтрации")
        return
    
    # Создаем фигуру
    fig, ax = plt.subplots(figsize=(16, 10))
    
    # Определяем диапазон времени для отображения
    if trades:
        min_time = min(t.entry_time for t in trades)
        max_time = max(t.exit_time for t in trades)
        # Добавляем небольшой запас
        time_range = df[(df.index >= min_time) & (df.index <= max_time)]
    else:
        time_range = df.tail(1000)  # Последние 1000 баров если нет сделок
    
    if time_range.empty:
        log.warning("Нет данных в диапазоне сделок")
        return
    
    # Рисуем свечи (упрощенно - используем close для линии)
    ax.plot(time_range.index, time_range["close"], color="black", linewidth=0.5, alpha=0.7, label="Цена")
    
    # Визуализируем каждую сделку
    for trade in trades:
        # Определяем цвет в зависимости от результата
        if trade.net_pnl > 0:
            color = "green"
            alpha = 0.7
        else:
            color = "red"
            alpha = 0.7
        
        # Точка входа
        entry_marker = "^" if trade.direction == "LONG" else "v"  # Используем стандартные маркеры
        ax.scatter(
            trade.entry_time,
            trade.entry_price,
            color=color,
            marker=entry_marker,
            s=100,
            alpha=alpha,
            zorder=5,
        )
        
        # Точка выхода
        exit_marker = "o" if trade.net_pnl > 0 else "x"  # Используем стандартные маркеры
        ax.scatter(
            trade.exit_time,
            trade.exit_price,
            color=color,
            marker=exit_marker,
            s=100,
            alpha=alpha,
            zorder=5,
        )
        
        # Линия между входом и выходом
        line_width = max(1, abs(trade.net_pnl) / 100)  # Толщина зависит от прибыли
        ax.plot(
            [trade.entry_time, trade.exit_time],
            [trade.entry_price, trade.exit_price],
            color=color,
            linewidth=line_width,
            alpha=alpha * 0.5,
            zorder=3,
        )
        
        # Стоп-лосс (горизонтальная линия)
        if trade.stop_take_history:
            # Рисуем ступенчатую линию для trailing stop
            history = sorted(trade.stop_take_history, key=lambda x: x.timestamp)
            stop_times = [h.timestamp for h in history]
            stop_values = [h.stop_loss for h in history]
            
            # Добавляем точку выхода
            stop_times.append(trade.exit_time)
            stop_values.append(trade.stop_loss)
            
            ax.plot(
                stop_times,
                stop_values,
                color="red",
                linestyle="--",
                linewidth=1.5,
                alpha=0.6,
                label="Стоп-лосс" if trade == trades[0] else "",
                zorder=2,
            )
        else:
            # Простая горизонтальная линия если нет истории
            ax.plot(
                [trade.entry_time, trade.exit_time],
                [trade.stop_loss, trade.stop_loss],
                color="red",
                linestyle="--",
                linewidth=1.5,
                alpha=0.6,
                label="Стоп-лосс" if trade == trades[0] else "",
                zorder=2,
            )
        
        # Тейк-профит (горизонтальная линия)
        ax.plot(
            [trade.entry_time, trade.exit_time],
            [trade.take_profit, trade.take_profit],
            color="green",
            linestyle="--",
            linewidth=1.5,
            alpha=0.6,
            label="Тейк-профит" if trade == trades[0] else "",
            zorder=2,
        )
    
    # Настройки графика
    ax.set_xlabel("Время", fontsize=12)
    ax.set_ylabel("Цена", fontsize=12)
    ax.set_title(f"Визуализация сделок ({len(trades)} сделок)", fontsize=14, fontweight="bold")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    
    # Форматируем оси
    fig.autofmt_xdate()
    
    # Сохраняем график
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        log.info("График сохранен: %s", output_path)
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Визуализация сделок на ценовом графике.")
    parser.add_argument(
        "--strategy",
        required=True,
        help="Название стратегии (например, momentum_breakout).",
    )
    parser.add_argument(
        "--instrument",
        required=True,
        help="Инструмент (например, EURUSD).",
    )
    parser.add_argument(
        "--period",
        default="m15",
        help="Период данных.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Путь для сохранения графика (PNG).",
    )
    parser.add_argument(
        "--filter",
        choices=["winning", "losing"],
        help="Фильтр сделок: winning (только прибыльные), losing (только убыточные).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Не показывать график, только сохранить.",
    )
    parser.add_argument(
        "--trades-file",
        type=Path,
        help="Путь к JSON файлу с результатами бэктеста (альтернатива запуску бэктеста).",
    )
    parser.add_argument(
        "--params-file",
        type=Path,
        help="Путь к JSON файлу с параметрами стратегии (например, из оптимизации).",
    )
    args = parser.parse_args()
    
    # Загружаем параметры если указан файл
    params = None
    if args.params_file:
        with args.params_file.open("r", encoding="utf-8") as f:
            params_data = json.load(f)
            # Поддерживаем разные форматы файлов
            if "best_params" in params_data:
                params = params_data["best_params"]
            elif "params" in params_data:
                params = params_data["params"]
            else:
                params = params_data  # Прямой формат словаря
        log.info("Загружены параметры из файла: %s", args.params_file)
        log.info("Параметры: %s", params)
    
    # Загружаем данные и сделки
    if args.trades_file:
        trades = load_trades_from_file(args.trades_file)
        # Загружаем данные отдельно
        runner = FullBacktestRunner()
        df = runner._load_data(args.instrument, args.period)
    else:
        df, trades = load_trades_from_backtest(args.strategy, args.instrument, args.period, params=params)
    
    if not trades:
        log.error("Не найдено сделок для визуализации")
        return
    
    # Определяем путь для сохранения
    output_path = args.output
    if output_path is None:
        output_path = Path(f"data/v1/reports/trade_visualization/{args.strategy}_{args.instrument}_{args.period}.png")
    
    # Визуализируем
    visualize_trades(
        df=df,
        trades=trades,
        output_path=output_path,
        show_plot=not args.no_show,
        trade_filter=args.filter,
    )


if __name__ == "__main__":
    main()

