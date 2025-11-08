#!/usr/bin/env python3
"""
Простой тест для проверки что проект работает локально
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Проверка импортов основных модулей"""
    print("🔍 Проверка импортов...")
    try:
        import pandas as pd
        import numpy as np
        print(f"  ✅ pandas {pd.__version__}")
        print(f"  ✅ numpy {np.__version__}")
    except ImportError as e:
        print(f"  ❌ Ошибка импорта: {e}")
        return False
    
    try:
        import src.data_pipeline
        print("  ✅ src.data_pipeline")
    except ImportError as e:
        print(f"  ❌ Ошибка импорта data_pipeline: {e}")
        return False
    
    try:
        import src.strategies
        print("  ✅ src.strategies")
    except ImportError as e:
        print(f"  ❌ Ошибка импорта strategies: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Проверка базовой функциональности"""
    print("\n🔧 Проверка базовой функциональности...")
    try:
        import pandas as pd
        import numpy as np
        
        # Простой тест pandas
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        assert len(df) == 3
        print("  ✅ pandas работает")
        
        # Простой тест numpy
        arr = np.array([1, 2, 3])
        assert arr.sum() == 6
        print("  ✅ numpy работает")
        
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 Локальный тест проекта forex-research")
    print("=" * 60)
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_basic_functionality():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Все тесты прошли успешно!")
        print("\nПроект готов к работе локально.")
        print("\nСледующие шаги:")
        print("  1. python3 scripts/run_ingest.py --list")
        print("  2. python3 scripts/run_full_backtests.py")
        return 0
    else:
        print("❌ Некоторые тесты не прошли")
        print("Проверьте установку зависимостей: pip3 install -e '.[backtesting]'")
        return 1

if __name__ == "__main__":
    sys.exit(main())
