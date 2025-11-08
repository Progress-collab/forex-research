#!/usr/bin/env python3
"""
Проверка структуры данных в указанной папке
"""
import sys
from pathlib import Path

def check_data_structure(data_path: str):
    """Проверяет структуру данных в указанной папке"""
    path = Path(data_path)
    
    print("="*60)
    print(f"🔍 Проверка данных в: {data_path}")
    print("="*60)
    
    if not path.exists():
        print(f"❌ Папка не существует: {data_path}")
        return False
    
    print(f"✅ Папка существует")
    
    # Проверяем структуру
    curated_path = path / "v1" / "curated" / "ctrader"
    
    if curated_path.exists():
        print(f"\n✅ Найдена папка curated: {curated_path}")
        
        # Ищем parquet файлы
        parquet_files = list(curated_path.glob("*.parquet"))
        
        if parquet_files:
            print(f"\n📊 Найдено {len(parquet_files)} файлов данных:")
            for f in sorted(parquet_files)[:10]:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"   - {f.name} ({size_mb:.2f} MB)")
            
            if len(parquet_files) > 10:
                print(f"   ... и еще {len(parquet_files) - 10} файлов")
            
            return True
        else:
            print(f"\n⚠️  Parquet файлы не найдены в {curated_path}")
            return False
    else:
        print(f"\n⚠️  Папка curated не найдена: {curated_path}")
        print(f"\n📁 Содержимое {path}:")
        for item in sorted(path.iterdir())[:10]:
            print(f"   - {item.name}")
        return False

if __name__ == "__main__":
    data_path = "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data"
    
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    
    success = check_data_structure(data_path)
    
    if success:
        print("\n✅ Данные найдены! Можно копировать в /workspace/data")
        print("\nКоманда для копирования:")
        print(f"cp -r '{data_path}/v1' /workspace/data/")
    else:
        print("\n⚠️  Данные не найдены или структура отличается")
    
    sys.exit(0 if success else 1)
