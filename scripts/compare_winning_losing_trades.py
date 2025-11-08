from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from scipy import stats

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner
from src.signals import FeatureConfig, compute_features


def _load_market_data(instrument: str, period: str, curated_dir: Path) -> pd.DataFrame:
    """Загружает рыночные данные для анализа."""
    data_path = curated_dir / f"{instrument}_{period}.parquet"
    if not data_path.exists():
        raise FileNotFoundError(f"Данные не найдены: {data_path}")
    
    df = pd.read_parquet(data_path)
    df["utc_time"] = pd.to_datetime(df["utc_time"])
    df = df.set_index("utc_time").sort_index()
    return df


def _calculate_entry_indicators(df: pd.DataFrame, entry_time: pd.Timestamp, lookback_bars: int = 50) -> Dict:
    """Вычисляет индикаторы на момент входа в сделку."""
    try:
        # Находим индекс входа
        entry_idx = df.index.get_indexer([entry_time], method="nearest")[0]
        if entry_idx < lookback_bars:
            return {}
        
        # Берем данные до входа
        window_df = df.iloc[entry_idx - lookback_bars:entry_idx + 1]
        
        # Вычисляем индикаторы
        features = compute_features(
            window_df.tail(100),
            FeatureConfig(
                name="comparison",
                window_short=20,
                window_long=50,
                additional_params={"atr_period": 14, "adx_period": 14, "rsi_period": 14},
            ),
        )
        
        atr = features.get("atr", default=0.0)
        adx = features.get("adx", default=0.0)
        rsi = features.get("rsi", default=50.0)
        ema_short = features.get("ema_short", default=0.0)
        ema_long = features.get("ema_long", default=0.0)
        
        # Вычисляем +DI и -DI (нужно для анализа направления тренда)
        # Используем упрощенный расчет на основе EMA
        price_change = window_df["close"].diff()
        pos_di_signal = (price_change > 0).sum() / len(price_change) * 100 if len(price_change) > 0 else 50.0
        neg_di_signal = (price_change < 0).sum() / len(price_change) * 100 if len(price_change) > 0 else 50.0
        
        # Волатильность
        volatility_pct = (atr / window_df["close"].iloc[-1]) * 100 if window_df["close"].iloc[-1] > 0 else 0.0
        
        # Расстояние от EMA
        current_price = window_df["close"].iloc[-1]
        distance_from_ema_short = abs((current_price - ema_short) / current_price * 100) if ema_short > 0 else 0.0
        distance_from_ema_long = abs((current_price - ema_long) / current_price * 100) if ema_long > 0 else 0.0
        
        # Направление тренда
        trend_direction = "UP" if ema_short > ema_long else "DOWN" if ema_short < ema_long else "FLAT"
        
        return {
            "atr": float(atr),
            "adx": float(adx),
            "rsi": float(rsi),
            "ema_short": float(ema_short),
            "ema_long": float(ema_long),
            "volatility_pct": float(volatility_pct),
            "pos_di_signal": float(pos_di_signal),
            "neg_di_signal": float(neg_di_signal),
            "distance_from_ema_short": float(distance_from_ema_short),
            "distance_from_ema_long": float(distance_from_ema_long),
            "trend_direction": trend_direction,
        }
    except Exception as e:
        logging.debug("Ошибка при вычислении индикаторов: %s", e)
        return {}


def compare_winning_losing_trades(
    strategy_id: str,
    instrument: str,
    period: str = "m15",
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    output_path: Path = Path("data/v1/reports/trade_analysis"),
) -> Dict:
    """
    Сравнивает прибыльные и убыточные сделки по индикаторам и условиям входа.
    Выполняет статистический анализ различий.
    """
    from src.strategies import (
        CarryMomentumStrategy,
        MeanReversionStrategy,
        MomentumBreakoutStrategy,
    )

    # Создаем стратегию
    strategy_map = {
        "mean_reversion": MeanReversionStrategy,
        "carry_momentum": CarryMomentumStrategy,
        "momentum_breakout": MomentumBreakoutStrategy,
    }

    if strategy_id not in strategy_map:
        raise ValueError(f"Неизвестная стратегия: {strategy_id}")

    strategy = strategy_map[strategy_id]()

    # Загружаем рыночные данные
    market_df = _load_market_data(instrument, period, curated_dir)

    # Запускаем бэктест
    runner = FullBacktestRunner(curated_dir=curated_dir)
    result = runner.run(strategy, instrument, period)

    if result.total_trades == 0:
        logging.warning("Нет сделок для анализа")
        return {"error": "No trades"}

    # Собираем данные о сделках с индикаторами
    trades_data = []
    for t in result.trades:
        trade_dict = {
            "entry_time": t.entry_time,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "pnl": t.net_pnl,
            "pnl_pct": t.pnl_pct,
            "is_winning": t.net_pnl > 0,
        }
        
        # Добавляем индикаторы на момент входа
        indicators = _calculate_entry_indicators(market_df, t.entry_time)
        trade_dict.update(indicators)
        
        trades_data.append(trade_dict)
    
    trades_df = pd.DataFrame(trades_data)

    # Разделяем на прибыльные и убыточные
    winning_trades = trades_df[trades_df["is_winning"] == True]
    losing_trades = trades_df[trades_df["is_winning"] == False]

    if len(winning_trades) == 0 or len(losing_trades) == 0:
        logging.warning("Недостаточно данных для сравнения (нет прибыльных или убыточных сделок)")
        return {"error": "Insufficient data"}

    # Индикаторы для сравнения
    indicators_to_compare = [
        "atr", "adx", "rsi", "volatility_pct",
        "pos_di_signal", "neg_di_signal",
        "distance_from_ema_short", "distance_from_ema_long",
    ]

    comparison = {
        "strategy": strategy_id,
        "instrument": instrument,
        "period": period,
        "total_trades": len(trades_df),
        "winning_trades": int(len(winning_trades)),
        "losing_trades": int(len(losing_trades)),
        "win_rate": float(len(winning_trades) / len(trades_df)) if len(trades_df) > 0 else 0.0,
        "indicator_comparison": {},
        "statistical_tests": {},
        "recommendations": [],
    }

    # Сравнение по каждому индикатору
    for indicator in indicators_to_compare:
        if indicator not in winning_trades.columns or indicator not in losing_trades.columns:
            continue
        
        # Удаляем NaN значения
        winning_values = winning_trades[indicator].dropna()
        losing_values = losing_trades[indicator].dropna()
        
        if len(winning_values) == 0 or len(losing_values) == 0:
            continue
        
        # Описательная статистика
        comparison["indicator_comparison"][indicator] = {
            "winning": {
                "mean": float(winning_values.mean()),
                "median": float(winning_values.median()),
                "std": float(winning_values.std()),
                "min": float(winning_values.min()),
                "max": float(winning_values.max()),
            },
            "losing": {
                "mean": float(losing_values.mean()),
                "median": float(losing_values.median()),
                "std": float(losing_values.std()),
                "min": float(losing_values.min()),
                "max": float(losing_values.max()),
            },
            "difference": {
                "mean_diff": float(winning_values.mean() - losing_values.mean()),
                "mean_diff_pct": float((winning_values.mean() - losing_values.mean()) / losing_values.mean() * 100) if losing_values.mean() != 0 else 0.0,
            },
        }
        
        # Статистический тест (t-test)
        try:
            t_stat, p_value = stats.ttest_ind(winning_values, losing_values)
            comparison["statistical_tests"][indicator] = {
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "significant": p_value < 0.05,
            }
        except Exception as e:
            logging.debug("Ошибка при статистическом тесте для %s: %s", indicator, e)

    # Анализ направления тренда
    if "trend_direction" in trades_df.columns:
        trend_comparison = {}
        for direction in ["UP", "DOWN", "FLAT"]:
            winning_with_trend = winning_trades[winning_trades["trend_direction"] == direction]
            losing_with_trend = losing_trades[losing_trades["trend_direction"] == direction]
            
            if len(winning_with_trend) > 0 or len(losing_with_trend) > 0:
                trend_comparison[direction] = {
                    "winning_count": int(len(winning_with_trend)),
                    "losing_count": int(len(losing_with_trend)),
                    "win_rate": float(len(winning_with_trend) / (len(winning_with_trend) + len(losing_with_trend)) * 100) if (len(winning_with_trend) + len(losing_with_trend)) > 0 else 0.0,
                }
        
        comparison["trend_direction_comparison"] = trend_comparison

    # Анализ по направлению сделки
    if "direction" in trades_df.columns:
        direction_comparison = {}
        for trade_dir in ["LONG", "SHORT"]:
            winning_dir = winning_trades[winning_trades["direction"] == trade_dir]
            losing_dir = losing_trades[losing_trades["direction"] == trade_dir]
            
            if len(winning_dir) > 0 or len(losing_dir) > 0:
                direction_comparison[trade_dir] = {
                    "winning_count": int(len(winning_dir)),
                    "losing_count": int(len(losing_dir)),
                    "win_rate": float(len(winning_dir) / (len(winning_dir) + len(losing_dir)) * 100) if (len(winning_dir) + len(losing_dir)) > 0 else 0.0,
                }
        
        comparison["trade_direction_comparison"] = direction_comparison

    # Генерируем рекомендации на основе сравнения
    recommendations = []
    
    # Проверяем значимые различия в индикаторах
    for indicator, test_result in comparison.get("statistical_tests", {}).items():
        if test_result.get("significant", False):
            indicator_comp = comparison["indicator_comparison"].get(indicator, {})
            mean_diff = indicator_comp.get("difference", {}).get("mean_diff", 0.0)
            
            if indicator == "adx":
                if mean_diff > 0:
                    recommendations.append(f"Прибыльные сделки имеют более высокий ADX ({mean_diff:.2f}). Рассмотреть увеличение минимального порога ADX.")
                else:
                    recommendations.append(f"Убыточные сделки имеют более высокий ADX ({abs(mean_diff):.2f}). Рассмотреть увеличение минимального порога ADX.")
            
            elif indicator == "rsi":
                if mean_diff > 0:
                    recommendations.append(f"Прибыльные сделки имеют более высокий RSI ({mean_diff:.2f}). Рассмотреть фильтр по RSI для входа.")
                else:
                    recommendations.append(f"Убыточные сделки имеют более высокий RSI ({abs(mean_diff):.2f}). Рассмотреть фильтр по RSI для избежания перекупленности/перепроданности.")
            
            elif indicator == "volatility_pct":
                if mean_diff > 0:
                    recommendations.append(f"Прибыльные сделки происходят при более высокой волатильности ({mean_diff:.2f}%). Рассмотреть фильтр по минимальной волатильности.")
                else:
                    recommendations.append(f"Убыточные сделки происходят при более высокой волатильности ({abs(mean_diff):.2f}%). Рассмотреть фильтр по максимальной волатильности.")
    
    # Рекомендации по направлению тренда
    if "trend_direction_comparison" in comparison:
        trend_comp = comparison["trend_direction_comparison"]
        best_trend = max(trend_comp.items(), key=lambda x: x[1].get("win_rate", 0.0), default=None)
        worst_trend = min(trend_comp.items(), key=lambda x: x[1].get("win_rate", 0.0), default=None)
        
        if best_trend and best_trend[1].get("win_rate", 0.0) > 60:
            recommendations.append(f"Лучшие результаты при тренде {best_trend[0]} (Win Rate {best_trend[1]['win_rate']:.1f}%). Рассмотреть фильтр по направлению тренда.")
        
        if worst_trend and worst_trend[1].get("win_rate", 0.0) < 30:
            recommendations.append(f"Худшие результаты при тренде {worst_trend[0]} (Win Rate {worst_trend[1]['win_rate']:.1f}%). Рассмотреть избегание входов в таких условиях.")

    comparison["recommendations"] = recommendations

    # Сохраняем сравнение
    output_path.mkdir(parents=True, exist_ok=True)
    report_file = output_path / f"{strategy_id}_{instrument}_{period}_comparison.json"
    with report_file.open("w", encoding="utf-8") as fp:
        json.dump(comparison, fp, ensure_ascii=False, indent=2, default=str)

    logging.info("Сравнение сохранено в %s", report_file)
    return comparison


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Сравнение прибыльных и убыточных сделок.")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["mean_reversion", "carry_momentum", "momentum_breakout"],
        help="Стратегия для анализа.",
    )
    parser.add_argument(
        "--instrument",
        default="EURUSD",
        help="Инструмент для анализа.",
    )
    parser.add_argument(
        "--period",
        default="m15",
        help="Период данных.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    compare_winning_losing_trades(
        strategy_id=args.strategy,
        instrument=args.instrument,
        period=args.period,
    )


if __name__ == "__main__":
    main()

