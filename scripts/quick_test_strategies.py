"""Быстрый тест улучшенных стратегий на небольшом датасете."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

# Настройка UTF-8 кодировки для Windows консоли
from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

from src.backtesting.full_backtest import FullBacktestRunner
from src.strategies import CarryMomentumStrategy, MomentumBreakoutStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def quick_test_strategies():
    """Быстрый тест стратегий на последнем месяце данных."""
    runner = FullBacktestRunner()
    
    # Тестируем на последнем месяце данных
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    strategies_to_test = [
        ("momentum_breakout", MomentumBreakoutStrategy()),
        ("carry_momentum", CarryMomentumStrategy()),
    ]
    
    instrument = "EURUSD"
    period = "m15"
    
    log.info("Запуск быстрого теста стратегий на периоде %s - %s", start_date.date(), end_date.date())
    
    for strategy_id, strategy in strategies_to_test:
        try:
            log.info("Тестирование стратегии: %s", strategy_id)
            result = runner.run(strategy, instrument, period, start_date=start_date, end_date=end_date)
            
            log.info("Результаты %s:", strategy_id)
            log.info("  Сделок: %d", result.total_trades)
            log.info("  Прибыльных: %d", result.winning_trades)
            log.info("  Убыточных: %d", result.losing_trades)
            log.info("  Win Rate: %.2f%%", result.win_rate * 100)
            log.info("  Net PnL: %.2f", result.net_pnl)
            log.info("  Profit Factor: %.2f", result.profit_factor)
            log.info("  Recovery Factor: %.2f", result.recovery_factor)
            log.info("  Sharpe Ratio: %.2f", result.sharpe_ratio)
            
            if result.total_trades == 0:
                log.warning("  ВНИМАНИЕ: Стратегия не сгенерировала ни одной сделки!")
            elif result.profit_factor > 1.0:
                log.info("  ✓ Стратегия прибыльна (Profit Factor > 1)")
            else:
                log.warning("  ✗ Стратегия убыточна (Profit Factor < 1)")
                
        except Exception as e:
            log.error("Ошибка при тестировании %s: %s", strategy_id, e, exc_info=True)


if __name__ == "__main__":
    quick_test_strategies()

