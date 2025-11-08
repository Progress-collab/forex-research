from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner, FullBacktestResult
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


def _calculate_market_conditions(df: pd.DataFrame, entry_time: pd.Timestamp, lookback_bars: int = 50) -> Dict:
    """Вычисляет рыночные условия на момент входа в сделку."""
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
                name="analysis",
                window_short=20,
                window_long=50,
                additional_params={"atr_period": 14, "adx_period": 14},
            ),
        )
        
        atr = features.get("atr", default=0.0)
        adx = features.get("adx", default=0.0)
        rsi = features.get("rsi", default=50.0)
        ema_short = features.get("ema_short", default=0.0)
        ema_long = features.get("ema_long", default=0.0)
        
        # Определяем тренд/флэт
        price_change = (window_df["close"].iloc[-1] - window_df["close"].iloc[0]) / window_df["close"].iloc[0]
        trend_strength = abs(price_change)
        
        # Волатильность (ATR относительно цены)
        volatility_pct = (atr / window_df["close"].iloc[-1]) * 100 if window_df["close"].iloc[-1] > 0 else 0.0
        
        # Историческая волатильность (стандартное отклонение returns)
        returns = window_df["close"].pct_change().dropna()
        hist_volatility = returns.std() * np.sqrt(252 * 24 * 4) * 100 if len(returns) > 1 else 0.0  # Годовая волатильность
        
        # Направление тренда
        trend_direction = "UP" if ema_short > ema_long else "DOWN" if ema_short < ema_long else "FLAT"
        
        # Определяем режим рынка
        if adx < 20:
            market_regime = "FLAT"
        elif adx >= 25:
            market_regime = "TREND"
        else:
            market_regime = "WEAK_TREND"
        
        return {
            "atr": float(atr),
            "adx": float(adx),
            "rsi": float(rsi),
            "volatility_pct": float(volatility_pct),
            "hist_volatility_pct": float(hist_volatility),
            "trend_strength": float(trend_strength),
            "trend_direction": trend_direction,
            "market_regime": market_regime,
            "ema_short": float(ema_short),
            "ema_long": float(ema_long),
        }
    except Exception as e:
        logging.debug("Ошибка при вычислении условий рынка: %s", e)
        return {}


def _analyze_false_breakout(df: pd.DataFrame, trade: Dict, strategy_id: str) -> Dict:
    """Анализирует ложные пробития для Momentum Breakout."""
    if strategy_id != "momentum_breakout":
        return {}
    
    try:
        entry_time = trade["entry_time"]
        direction = trade["direction"]
        entry_price = trade["entry_price"]
        
        # Находим индекс входа
        entry_idx = df.index.get_indexer([entry_time], method="nearest")[0]
        
        # Проверяем движение после входа (следующие 10-20 баров)
        future_bars = min(20, len(df) - entry_idx - 1)
        if future_bars < 5:
            return {}
        
        future_df = df.iloc[entry_idx + 1:entry_idx + 1 + future_bars]
        
        if direction == "LONG":
            # Проверяем, вернулась ли цена ниже уровня входа
            min_price_after = future_df["low"].min()
            max_price_after = future_df["high"].max()
            
            # Ложное пробитие: цена вернулась ниже уровня входа
            false_breakout = min_price_after < entry_price * 0.999  # Небольшой допуск
            max_move_up = (max_price_after - entry_price) / entry_price * 100
            max_move_down = (entry_price - min_price_after) / entry_price * 100
            
        else:  # SHORT
            # Проверяем, вернулась ли цена выше уровня входа
            min_price_after = future_df["low"].min()
            max_price_after = future_df["high"].max()
            
            # Ложное пробитие: цена вернулась выше уровня входа
            false_breakout = max_price_after > entry_price * 1.001  # Небольшой допуск
            max_move_up = (max_price_after - entry_price) / entry_price * 100
            max_move_down = (entry_price - min_price_after) / entry_price * 100
        
        return {
            "false_breakout": bool(false_breakout),
            "max_move_up_pct": float(max_move_up),
            "max_move_down_pct": float(max_move_down),
        }
    except Exception as e:
        logging.debug("Ошибка при анализе ложного пробития: %s", e)
        return {}


def analyze_losing_trades(
    strategy_id: str,
    instrument: str,
    period: str = "m15",
    curated_dir: Path = Path("data/v1/curated/ctrader"),
    output_path: Path = Path("data/v1/reports/trade_analysis"),
) -> Dict:
    """
    Анализирует паттерны убыточных сделок с расширенным анализом:
    - Распределение по времени дня и дням недели
    - Рыночные условия при входе
    - Волатильность при входе
    - Ложные пробития (для Momentum Breakout)
    - Расстояние до стоп-лосса vs фактический убыток
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

    # Анализируем сделки с расширенной информацией
    trades_data = []
    for t in result.trades:
        trade_dict = {
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.net_pnl,
            "pnl_pct": t.pnl_pct,
            "duration_hours": (t.exit_time - t.entry_time).total_seconds() / 3600,
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
        }
        
        # Добавляем анализ рыночных условий
        market_conditions = _calculate_market_conditions(market_df, t.entry_time)
        trade_dict.update(market_conditions)
        
        # Добавляем анализ ложных пробитий
        false_breakout_info = _analyze_false_breakout(market_df, trade_dict, strategy_id)
        trade_dict.update(false_breakout_info)
        
        # Вычисляем расстояние до стоп-лосса
        if t.direction == "LONG":
            stop_distance_pct = abs((t.entry_price - t.stop_loss) / t.entry_price) * 100
            actual_loss_pct = abs((t.entry_price - t.exit_price) / t.entry_price) * 100
        else:  # SHORT
            stop_distance_pct = abs((t.stop_loss - t.entry_price) / t.entry_price) * 100
            actual_loss_pct = abs((t.exit_price - t.entry_price) / t.entry_price) * 100
        
        trade_dict["stop_distance_pct"] = stop_distance_pct
        trade_dict["actual_loss_pct"] = actual_loss_pct
        trade_dict["stop_to_loss_ratio"] = stop_distance_pct / actual_loss_pct if actual_loss_pct > 0 else 0.0
        
        # Время дня и день недели
        entry_ts = pd.Timestamp(t.entry_time)
        trade_dict["hour"] = entry_ts.hour
        trade_dict["day_of_week"] = entry_ts.dayofweek  # 0=Monday, 6=Sunday
        trade_dict["day_name"] = entry_ts.strftime("%A")
        
        trades_data.append(trade_dict)
    
    trades_df = pd.DataFrame(trades_data)

    # Разделяем на прибыльные и убыточные
    winning_trades = trades_df[trades_df["pnl"] > 0]
    losing_trades = trades_df[trades_df["pnl"] < 0]

    analysis = {
        "strategy": strategy_id,
        "instrument": instrument,
        "period": period,
        "total_trades": len(trades_df),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": len(winning_trades) / len(trades_df) if len(trades_df) > 0 else 0.0,
        "patterns": {},
    }

    if len(losing_trades) > 0:
        # Базовый анализ убыточных сделок
        analysis["patterns"]["losing_trades"] = {
            "avg_duration_hours": float(losing_trades["duration_hours"].mean()),
            "avg_loss": float(losing_trades["pnl"].mean()),
            "avg_loss_pct": float(losing_trades["pnl_pct"].mean()),
            "max_loss": float(losing_trades["pnl"].min()),
            "long_vs_short": {
                "long": int((losing_trades["direction"] == "LONG").sum()),
                "short": int((losing_trades["direction"] == "SHORT").sum()),
            },
        }

        # Проверяем, сколько сделок закрылись по стоп-лоссу
        stop_loss_hits = 0
        take_profit_hits = 0
        for _, trade in losing_trades.iterrows():
            if trade["direction"] == "LONG":
                if abs(trade["exit_price"] - trade["stop_loss"]) < abs(trade["exit_price"] - trade["take_profit"]):
                    stop_loss_hits += 1
            else:  # SHORT
                if abs(trade["exit_price"] - trade["stop_loss"]) < abs(trade["exit_price"] - trade["take_profit"]):
                    stop_loss_hits += 1

        analysis["patterns"]["losing_trades"]["stop_loss_hits"] = stop_loss_hits
        analysis["patterns"]["losing_trades"]["take_profit_hits"] = take_profit_hits
        
        # Анализ по времени дня
        if "hour" in losing_trades.columns:
            hour_distribution = losing_trades["hour"].value_counts().sort_index().to_dict()
            analysis["patterns"]["losing_trades"]["hour_distribution"] = {int(k): int(v) for k, v in hour_distribution.items()}
            
            # Находим худшие часы
            worst_hours = losing_trades.groupby("hour")["pnl"].mean().sort_values().head(5)
            analysis["patterns"]["losing_trades"]["worst_hours"] = {
                int(hour): float(avg_loss) for hour, avg_loss in worst_hours.items()
            }
        
        # Анализ по дням недели
        if "day_of_week" in losing_trades.columns:
            day_distribution = losing_trades["day_of_week"].value_counts().sort_index().to_dict()
            analysis["patterns"]["losing_trades"]["day_distribution"] = {int(k): int(v) for k, v in day_distribution.items()}
            
            # Средний убыток по дням недели
            day_avg_loss = losing_trades.groupby("day_of_week")["pnl"].mean().to_dict()
            analysis["patterns"]["losing_trades"]["day_avg_loss"] = {int(k): float(v) for k, v in day_avg_loss.items()}
        
        # Анализ рыночных условий
        if "market_regime" in losing_trades.columns:
            regime_distribution = losing_trades["market_regime"].value_counts().to_dict()
            analysis["patterns"]["losing_trades"]["market_regime_distribution"] = regime_distribution
            
            regime_avg_loss = losing_trades.groupby("market_regime")["pnl"].mean().to_dict()
            analysis["patterns"]["losing_trades"]["market_regime_avg_loss"] = {k: float(v) for k, v in regime_avg_loss.items()}
        
        # Анализ волатильности
        if "volatility_pct" in losing_trades.columns:
            volatility_stats = losing_trades["volatility_pct"].describe().to_dict()
            analysis["patterns"]["losing_trades"]["volatility_stats"] = {k: float(v) for k, v in volatility_stats.items()}
            
            # Разделяем на низкую/среднюю/высокую волатильность
            vol_median = losing_trades["volatility_pct"].median()
            low_vol = losing_trades[losing_trades["volatility_pct"] < vol_median * 0.7]
            high_vol = losing_trades[losing_trades["volatility_pct"] > vol_median * 1.3]
            
            analysis["patterns"]["losing_trades"]["volatility_groups"] = {
                "low_volatility": {
                    "count": int(len(low_vol)),
                    "avg_loss": float(low_vol["pnl"].mean()) if len(low_vol) > 0 else 0.0,
                },
                "high_volatility": {
                    "count": int(len(high_vol)),
                    "avg_loss": float(high_vol["pnl"].mean()) if len(high_vol) > 0 else 0.0,
                },
            }
        
        # Анализ расстояния до стоп-лосса vs фактический убыток
        if "stop_distance_pct" in losing_trades.columns and "actual_loss_pct" in losing_trades.columns:
            analysis["patterns"]["losing_trades"]["stop_analysis"] = {
                "avg_stop_distance_pct": float(losing_trades["stop_distance_pct"].mean()),
                "avg_actual_loss_pct": float(losing_trades["actual_loss_pct"].mean()),
                "avg_stop_to_loss_ratio": float(losing_trades["stop_to_loss_ratio"].mean()),
                "trades_exceeding_stop": int((losing_trades["actual_loss_pct"] > losing_trades["stop_distance_pct"]).sum()),
            }
        
        # Анализ ложных пробитий (для Momentum Breakout)
        if strategy_id == "momentum_breakout" and "false_breakout" in losing_trades.columns:
            false_breakouts = losing_trades[losing_trades["false_breakout"] == True]
            analysis["patterns"]["losing_trades"]["false_breakouts"] = {
                "count": int(len(false_breakouts)),
                "percentage": float(len(false_breakouts) / len(losing_trades) * 100) if len(losing_trades) > 0 else 0.0,
                "avg_loss": float(false_breakouts["pnl"].mean()) if len(false_breakouts) > 0 else 0.0,
            }
        
        # Анализ направления тренда vs направление сделки
        if "trend_direction" in losing_trades.columns:
            trend_analysis = {}
            for direction in ["LONG", "SHORT"]:
                direction_trades = losing_trades[losing_trades["direction"] == direction]
                if len(direction_trades) > 0:
                    trend_match = direction_trades[
                        (direction == "LONG" and direction_trades["trend_direction"] == "UP") |
                        (direction == "SHORT" and direction_trades["trend_direction"] == "DOWN")
                    ]
                    trend_analysis[direction] = {
                        "total": int(len(direction_trades)),
                        "trend_match": int(len(trend_match)),
                        "trend_match_pct": float(len(trend_match) / len(direction_trades) * 100) if len(direction_trades) > 0 else 0.0,
                        "avg_loss_match": float(trend_match["pnl"].mean()) if len(trend_match) > 0 else 0.0,
                        "avg_loss_no_match": float(direction_trades[~direction_trades.index.isin(trend_match.index)]["pnl"].mean()) if len(direction_trades) > len(trend_match) else 0.0,
                    }
            analysis["patterns"]["losing_trades"]["trend_direction_analysis"] = trend_analysis

    if len(winning_trades) > 0:
        # Анализ прибыльных сделок для сравнения
        analysis["patterns"]["winning_trades"] = {
            "avg_duration_hours": float(winning_trades["duration_hours"].mean()),
            "avg_win": float(winning_trades["pnl"].mean()),
            "avg_win_pct": float(winning_trades["pnl_pct"].mean()),
            "max_win": float(winning_trades["pnl"].max()),
        }

    # Рекомендации
    recommendations = []
    if len(losing_trades) > len(winning_trades) * 2:
        recommendations.append("Слишком много убыточных сделок. Рассмотреть более строгие фильтры входа.")
    if len(losing_trades) > 0 and analysis["patterns"]["losing_trades"]["avg_loss"] < -100:
        recommendations.append("Средний убыток слишком большой. Рассмотреть уменьшение размера позиции или улучшение стоп-лоссов.")
    if len(losing_trades) > 0 and analysis["patterns"]["losing_trades"]["stop_loss_hits"] > len(losing_trades) * 0.7:
        recommendations.append("Большинство убыточных сделок закрываются по стоп-лоссу. Рассмотреть увеличение расстояния стоп-лосса или улучшение фильтров входа.")

    analysis["recommendations"] = recommendations

    # Сохраняем анализ
    output_path.mkdir(parents=True, exist_ok=True)
    report_file = output_path / f"{strategy_id}_{instrument}_{period}_analysis.json"
    with report_file.open("w", encoding="utf-8") as fp:
        json.dump(analysis, fp, ensure_ascii=False, indent=2, default=str)

    logging.info("Анализ сохранен в %s", report_file)
    return analysis


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Анализ паттернов убыточных сделок.")
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

    analyze_losing_trades(
        strategy_id=args.strategy,
        instrument=args.instrument,
        period=args.period,
    )


if __name__ == "__main__":
    main()

