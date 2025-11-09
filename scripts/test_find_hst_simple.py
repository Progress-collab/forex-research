"""Простой тест для проверки логики find_hst"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.encoding import setup_utf8_encoding
setup_utf8_encoding()

import pandas as pd
from src.patterns.chart import find_hst, check_nearness

# Создаем тестовые данные
data = {
    'high': [100.0, 105.0, 100.0],  # Левое плечо, Голова, Правое плечо
    'low': [95.0, 100.0, 95.0]
}
df = pd.DataFrame(data)

ls_idx = 0
head_idx = 1
rs_idx = 2

ls_price = df.iloc[ls_idx]['high']
head_price = df.iloc[head_idx]['high']
rs_price = df.iloc[rs_idx]['high']

print(f"Тестовые данные:")
print(f"  Левое плечо: {ls_price}")
print(f"  Голова: {head_price}")
print(f"  Правое плечо: {rs_price}")
print(f"  Преимущество головы: {(head_price - (ls_price + rs_price)/2) / ((ls_price + rs_price)/2) * 100:.2f}%")

# Проверяем check_nearness для плеч
shoulder_near = check_nearness(ls_price, rs_price, percent=0.5, price_vary=0.4, strict_patterns=False)
print(f"\nПлечи близки (check_nearness): {shoulder_near}")

# Проверяем find_hst с разными процентами
for pct in [0.15, 0.10, 0.05, 0.02]:
    result = find_hst(df, ls_idx, rs_idx, head_idx, pct, False)
    head_to_rs = (head_price - rs_price) / rs_price
    head_to_ls = (head_price - ls_price) / ls_price
    print(f"\nhead_shoulder_pct={pct*100:.1f}%:")
    print(f"  head_to_rs_diff: {head_to_rs*100:.2f}%")
    print(f"  head_to_ls_diff: {head_to_ls*100:.2f}%")
    print(f"  find_hst результат: {result} (True=невалиден, False=валиден)")
    print(f"  Ожидается: {'валиден' if min(head_to_rs, head_to_ls) >= pct else 'невалиден'}")

