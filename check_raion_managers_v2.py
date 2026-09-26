"""
Проверка v2: распределение менеджеров после правок.
"""
import data_loader as dl

data = dl.load_all_data(force_refresh=True)
df = data['df']
summary = dl.get_summary_cached(df, force=True)
primary_map = dl.get_primary_manager_by_raion(summary)

print("=" * 70)
print("НОВОЕ РАСПРЕДЕЛЕНИЕ")
print("=" * 70)
print(f"Всего предприятий: {len(primary_map)}")
print()

# Сколько предприятий у каждого основного
from collections import Counter
primary_counts = Counter(primary_map.values())

print("Основной менеджер → кол-во предприятий:")
for mgr, cnt in primary_counts.most_common():
    print(f"  {mgr or '—'}: {cnt}")

# Примеры отображения с (подмена)
print()
print("=" * 70)
print("ФОРМАТ «МЕНЕДЖЕР» С (подмена)")
print("=" * 70)
print()

# Смотрим 5 предприятий для примера
examples = ['А/КР-146', 'А/КР-1', 'А/КР-270', 'А/КР-221', 'А/КР-78']

for code in examples:
    m = summary.get(code, {})
    primary = primary_map.get(code, '—')
    managers_set = m.get('managers_set', set())
    
    display = dl.format_managers_display(primary, managers_set)
    
    print(f"{code} — {m.get('company_name', '')}")
    print(f"  Основной: {primary}")
    print(f"  Все менеджеры: {sorted(managers_set)}")
    print(f"  Отображение: {display}")
    print()

# Итог
print("=" * 70)
print("ГОТОВО")
print("=" * 70)