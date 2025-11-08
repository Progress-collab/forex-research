#!/usr/bin/env python3
"""
Проверка наличия данных и запуск бэктеста Momentum Breakout
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.full_backtest import FullBacktestRunner
from src.strategies.momentum_breakout import MomentumBreakoutStrategy

def main():
    print("="*60)
    print("🔍 Проверка данных и запуск бэктеста Momentum Breakout")
    print("="*60)
    
    curated_dir = Path("data/v1/curated/ctrader")
    
    # Проверяем наличие данных
    print(f"\n📁 Проверка данных в {curated_dir}:")
    
    if not curated_dir.exists():
        print(f"   ❌ Директория не существует")
        print(f"   💡 Создана структура папок")
        curated_dir.mkdir(parents=True, exist_ok=True)
    
    # Ищем parquet файлы
    parquet_files = list(curated_dir.glob("*.parquet"))
    
    if parquet_files:
        print(f"   ✅ Найдено {len(parquet_files)} файлов данных:")
        for f in parquet_files[:5]:
            print(f"      - {f.name}")
        
        # Пробуем найти EURUSD m15
        eurusd_m15 = curated_dir / "EURUSD_m15.parquet"
        if eurusd_m15.exists():
            print(f"\n   ✅ Найден EURUSD_m15.parquet - можно запускать бэктест!")
            
            print(f"\n🚀 Запуск бэктеста...")
            strategy = MomentumBreakoutStrategy()
            runner = FullBacktestRunner(curated_dir=curated_dir)
            
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
                    print(f"\n🎉 УСПЕХ! Стратегия генерирует {result.total_trades} сделок!")
                else:
                    print(f"\n⚠️  Стратегия все еще не генерирует сделки")
                
                return 0
            except Exception as e:
                print(f"\n❌ Ошибка при запуске бэктеста: {e}")
                import traceback
                traceback.print_exc()
                return 1
        else:
            print(f"\n   ⚠️  EURUSD_m15.parquet не найден")
            print(f"   Доступные файлы: {[f.name for f in parquet_files[:5]]}")
            print(f"\n   💡 Можно запустить бэктест на других данных:")
            print(f"      python3 scripts/run_full_backtests.py --strategies momentum_breakout")
            return 0
    else:
        print(f"   ⚠️  Файлы данных не найдены")
        print(f"\n   💡 Для сбора данных используйте:")
        print(f"      python3 scripts/run_ingest.py --list")
        print(f"      python3 scripts/fetch_ctrader_trendbars.py --symbol EURUSD --period m15")
        return 1

if __name__ == "__main__":
    sys.exit(main())
