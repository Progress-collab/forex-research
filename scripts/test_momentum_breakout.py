#!/usr/bin/env python3
"""
Быстрый тест исправленной стратегии Momentum Breakout
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.momentum_breakout import MomentumBreakoutStrategy
from src.backtesting.full_backtest import FullBacktestRunner

def main():
    print("="*60)
    print("🧪 Тестирование исправленной Momentum Breakout стратегии")
    print("="*60)
    
    # Создаем стратегию
    strategy = MomentumBreakoutStrategy()
    print(f"\n📊 Параметры стратегии:")
    print(f"   - Lookback hours: {strategy.lookback_hours}")
    print(f"   - ADX threshold: {strategy.adx_threshold}")
    print(f"   - Min ATR: {strategy.min_atr}")
    
    # Проверяем наличие данных
    curated_dir = Path("data/v1/curated/ctrader")
    if not curated_dir.exists():
        print(f"\n⚠️  Директория с данными не найдена: {curated_dir}")
        print("   Нужно сначала собрать данные: python3 scripts/run_ingest.py")
        return 1
    
    # Запускаем бэктест
    print(f"\n🚀 Запуск бэктеста...")
    runner = FullBacktestRunner(curated_dir=curated_dir)
    
    # Тестируем на EURUSD m15 (самый популярный инструмент)
    try:
        result = runner.run(strategy, "EURUSD", "m15")
        
        print(f"\n✅ Результаты бэктеста:")
        print(f"   - Сделок: {result.total_trades}")
        print(f"   - Win rate: {result.win_rate:.2%}")
        print(f"   - Net PnL: {result.net_pnl:.2f}")
        print(f"   - Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"   - Max Drawdown: {result.max_drawdown:.2%}")
        print(f"   - Recovery Factor: {result.recovery_factor:.2f}")
        
        if result.total_trades > 0:
            print(f"\n✅ УСПЕХ! Стратегия генерирует сделки!")
            if result.sharpe_ratio > 0:
                print(f"   🎉 Sharpe положительный - стратегия прибыльная!")
            else:
                print(f"   ⚠️  Sharpe отрицательный - нужна дальнейшая оптимизация")
        else:
            print(f"\n⚠️  Стратегия все еще не генерирует сделки")
            print(f"   Возможно нужны дополнительные исправления")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Ошибка при запуске бэктеста: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
