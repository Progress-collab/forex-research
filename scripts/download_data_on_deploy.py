#!/usr/bin/env python3
"""
Скрипт для автоматической загрузки данных при деплое (если данных нет)
Альтернатива Git LFS - загружает данные через API
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

def check_data_exists():
    """Проверяет наличие данных"""
    curated_dir = Path("data/v1/curated/ctrader")
    if not curated_dir.exists():
        return False
    
    parquet_files = list(curated_dir.glob("*.parquet"))
    return len(parquet_files) > 0

def download_data_via_api():
    """Загружает данные через cTrader API"""
    load_dotenv()
    
    # Проверяем наличие credentials
    required_vars = [
        "CTRADER_CLIENT_ID",
        "CTRADER_CLIENT_SECRET", 
        "CTRADER_ACCESS_TOKEN"
    ]
    
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"⚠️  Отсутствуют переменные окружения: {', '.join(missing)}")
        print("   Данные не могут быть загружены автоматически")
        return False
    
    print("📥 Загрузка данных через cTrader API...")
    
    # Импортируем только если credentials есть
    from src.data_pipeline.ctrader_client import CTraderCredentials, CTraderTrendbarFetcher
    
    creds = CTraderCredentials(
        client_id=os.environ["CTRADER_CLIENT_ID"],
        client_secret=os.environ["CTRADER_CLIENT_SECRET"],
        access_token=os.environ["CTRADER_ACCESS_TOKEN"],
        refresh_token=os.getenv("CTRADER_REFRESH_TOKEN"),
        environment="live"
    )
    
    # Список инструментов для загрузки
    instruments = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    periods = ["m15", "h1"]
    
    curated_dir = Path("data/v1/curated/ctrader")
    curated_dir.mkdir(parents=True, exist_ok=True)
    
    fetcher = CTraderTrendbarFetcher(creds)
    
    try:
        for symbol in instruments:
            for period in periods:
                print(f"  Загрузка {symbol} {period}...")
                try:
                    bars = fetcher.get_trendbars(symbol=symbol, period=period, bars=5000)
                    
                    # Конвертируем в DataFrame и сохраняем
                    import pandas as pd
                    df = pd.DataFrame(bars)
                    if not df.empty:
                        output_path = curated_dir / f"{symbol}_{period}.parquet"
                        df.to_parquet(output_path)
                        print(f"    ✅ Сохранено {len(bars)} баров в {output_path}")
                except Exception as e:
                    print(f"    ⚠️  Ошибка загрузки {symbol} {period}: {e}")
        
        return True
    finally:
        fetcher.close()

def main():
    print("="*60)
    print("🔍 Проверка наличия данных")
    print("="*60)
    
    if check_data_exists():
        print("✅ Данные уже существуют!")
        return 0
    
    print("⚠️  Данные не найдены")
    print("\n📥 Попытка загрузить данные автоматически...")
    
    if download_data_via_api():
        print("\n✅ Данные успешно загружены!")
        return 0
    else:
        print("\n❌ Не удалось загрузить данные автоматически")
        print("\n💡 Альтернативы:")
        print("1. Использовать Git LFS (см. docs/DATA_IN_CLOUD.md)")
        print("2. Скопировать данные вручную")
        print("3. Настроить переменные окружения для API")
        return 1

if __name__ == "__main__":
    sys.exit(main())
