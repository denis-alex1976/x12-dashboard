"""
Проверка распределения менеджеров по районам.
Цель: понять, как ложатся менеджеры, где проблемные районы.
"""
import data_loader as dl
from collections import defaultdict

data = dl.load_all_data(force_refresh=True)
df = data['df']
summary = dl.get_summary_cached(df, force=True)

print("=" * 70)
print("РАСПРЕДЕЛЕНИЕ МЕНЕДЖЕРОВ ПО РАЙОНАМ")
print("=" * 70)

# Собираем: {raion: {manager: count}}
raion_stats = defaultdict(lambda: defaultdict(int))
for code, m in summary.items():
    raion = m.get('raion')
    manager = m.get('manager')
    if raion and manager:
        raion_stats[raion][manager] += 1

# Определяем основного для каждого района
print()
print("Районы (всего", len(raion_stats), "):")
print()

problem_raions = []
for raion in sorted(raion_stats.keys()):
    counts = raion_stats[raion]
    total = sum(counts.values())
    
    # Сортировка: по кол-ву (убыв), потом по алфавиту
    sorted_counts = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    primary = sorted_counts[0][0]
    
    # Формируем строку
    parts = []
    for mgr, cnt in sorted_counts:
        marker = " ← ОСНОВНОЙ" if mgr == primary else ""
        parts.append(f"{mgr}: {cnt}{marker}")
    
    print(f"  {raion} (всего {total}):")
    for p in parts:
        print(f"    {p}")
    
    if len(counts) > 1:
        problem_raions.append(raion)

# Итоги
print()
print("=" * 70)
print("ИТОГИ")
print("=" * 70)
print(f"  Всего районов: {len(raion_stats)}")
print(f"  Районов с одним менеджером: {len(raion_stats) - len(problem_raions)}")
print(f"  Районов с несколькими менеджерами: {len(problem_raions)}")
print()

if problem_raions:
    print("Районы с несколькими менеджерами:")
    for raion in problem_raions:
        counts = raion_stats[raion]
        sorted_counts = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        primary = sorted_counts[0][0]
        others = [m for m, _ in sorted_counts[1:]]
        print(f"  {raion}: {primary} (основной), остальные: {others}")

# Проверка предприятий с пустым районом
print()
print("=" * 70)
print("ПРЕДПРИЯТИЯ С ПУСТЫМ РАЙОНОМ")
print("=" * 70)

empty_raion = []
for code, m in summary.items():
    raion = m.get('raion')
    if not raion or str(raion).strip() in ('', 'nan', 'NaN'):
        empty_raion.append({
            'code': code,
            'name': m.get('company_name', ''),
            'manager': m.get('manager', '—'),
        })

if empty_raion:
    print(f"  Найдено {len(empty_raion)}:")
    for e in empty_raion[:20]:
        print(f"    {e['code']} — {e['name']} (менеджер: {e['manager']})")
    if len(empty_raion) > 20:
        print(f"    ... и ещё {len(empty_raion) - 20}")
else:
    print("  Нет — у всех предприятий есть район")

print()
print("=" * 70)
print("ГОТОВО")
print("=" * 70)