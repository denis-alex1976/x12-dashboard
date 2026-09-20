from data_loader import load_all_data, filter_sales

data = load_all_data()
df = data['df']
f = filter_sales(df, ['2026 сентябрь'], 'Все менеджеры')
s = f[f['order_type'] == 0]

s2 = s.groupby(['company', 'invoice_num', 'invoice_date']).agg({
    'invoice_amount': 'sum'
}).reset_index().sort_values('invoice_amount', ascending=False)

print("=" * 80)
for _, r in s2.iterrows():
    print(f"{r['company'][:45]:<45} | {r['invoice_num']:>5} | {r['invoice_date'].strftime('%d.%m.%Y')} | {r['invoice_amount']:>10,.0f}")
print("=" * 80)
print(f"Всего счетов: {len(s2)}")
print(f"Сумма: {s2['invoice_amount'].sum():,.0f}")