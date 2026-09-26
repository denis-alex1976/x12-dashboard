"""
Проверка расхождения дебиторки: Способ 1 (по счёту) vs Способ 2 (построчно).
Ожидание: разница = sum(court_amount) = 32 790 BYN.
"""
import data_loader as dl

print("=" * 70)
print("ЗАГРУЗКА ДАННЫХ")
print("=" * 70)

data = dl.load_all_data(force_refresh=True)
df = data['df']
print(f"Всего строк: {len(df)}")

admin_settings = dl.get_admin_settings()
trust_limits = dl.load_trust_limits()
summary = dl.get_summary_cached(df, force=True)

print(f"Предприятий в summary: {len(summary)}")

# === СПОСОБ 1: get_debt_summary (по счёту) ===
print()
print("=" * 70)
print("СПОСОБ 1 - get_debt_summary (по счёту, без суда)")
print("=" * 70)

s1 = dl.get_debt_summary(df, None, 'Все менеджеры')
print(f"  Продажи:      {s1['sales']:>15,.2f}")
print(f"  Оплаты:       {s1['payments']:>15,.2f}")
print(f"  Дебиторка:    {s1['debt']:>15,.2f}")
print(f"  % дебиторки:  {s1['percent']:>15.2f}")

# === СПОСОБ 2: через summary (построчно) ===
print()
print("=" * 70)
print("СПОСОБ 2 - через summary (построчно, суд вычтен)")
print("=" * 70)

sales_all = df[(df['row_type'] == 'sale') & (df['order_type'] == 0)]['invoice_amount'].sum()
payments_all = df[df['row_type'] == 'payment']['payment_amount'].sum()

total_debt = sum(m.get('debt_amount', 0.0) for m in summary.values())
total_court = sum(m.get('court_amount', 0.0) for m in summary.values())
total_overpay = sum(m.get('overpay_amount', 0.0) for m in summary.values())

print(f"  Продажи:      {sales_all:>15,.2f}")
print(f"  Оплаты:       {payments_all:>15,.2f}")
print(f"  Дебиторка:    {total_debt:>15,.2f}")
print(f"  Суд:          {total_court:>15,.2f}")
print(f"  Переплата:    {total_overpay:>15,.2f}")

# === РАЗНИЦА ===
print()
print("=" * 70)
print("РАЗНИЦА")
print("=" * 70)

diff_debt = s1['debt'] - total_debt
print(f"  Дебиторка (Способ 1):   {s1['debt']:>15,.2f}")
print(f"  Дебиторка (Способ 2):   {total_debt:>15,.2f}")
print(f"  Разница:                {diff_debt:>15,.2f}")
print(f"  Суд (sum court_amount): {total_court:>15,.2f}")
print()

if abs(diff_debt - total_court) < 1.0:
    print("  [+] СОВПАДАЕТ! Разница = сумма суда.")
    print("  -> Можно смело переписывать get_debt_summary через summary.")
else:
    print(f"  [-] НЕ СОВПАДАЕТ. Разница {diff_debt:,.2f} != суд {total_court:,.2f}")
    print(f"  -> Остаток: {diff_debt - total_court:,.2f}. Ищем баг.")

# === БАЛАНС ===
print()
print("=" * 70)
print("БАЛАНС (проверка модели)")
print("=" * 70)
print(f"  Продажи - Оплаты                = {sales_all - payments_all:>15,.2f}")
print(f"  Дебиторка + Суд - Переплата     = {total_debt + total_court - total_overpay:>15,.2f}")

# === ПО МЕНЕДЖЕРАМ ===
print()
print("=" * 70)
print("ПО МЕНЕДЖЕРАМ (Способ 2)")
print("=" * 70)

by_mgr = dl.get_debt_by_manager(df, summary=summary)
if not by_mgr.empty:
    for _, row in by_mgr.iterrows():
        print(f"  {row['manager']:<20} долг={row['debt']:>12,.2f}  суд={row['court']:>12,.2f}")

print()
print("=" * 70)
print("ГОТОВО")
print("=" * 70)