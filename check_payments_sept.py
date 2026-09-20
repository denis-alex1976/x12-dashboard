from data_loader import load_all_data, filter_payments

data = load_all_data()
df = data['df']
p = filter_payments(df, ['2026 сентябрь'], 'Все менеджеры')

print("=" * 60)
print(f"Всего оплат: {len(p)}")
print(f"Сумма: {p['payment_amount'].sum():,.0f}")
print("=" * 60)

by_mgr = p.groupby('manager')['payment_amount'].sum().reset_index()
by_mgr.columns = ['manager', 'amount']
by_mgr = by_mgr.sort_values('amount', ascending=False)

for _, r in by_mgr.iterrows():
    print(f"{r['manager']:<20} | {r['amount']:>10,.0f}")