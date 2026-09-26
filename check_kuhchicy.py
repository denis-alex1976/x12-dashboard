import data_loader as dl

data = dl.load_all_data(force_refresh=True)
df = data['df']

# Ищем Кухчиц по кириллице
code = None
for c in df['company_code'].dropna().unique():
    if '146' in str(c):
        code = c
        break

print(f"Код Кухчиц: {code!r}")
print()

if code:
    kuh = df[df['company_code'] == code]
    kuh_sale = kuh[kuh['row_type'] == 'sale'].sort_values('invoice_date')

    print("Все sale-строки Кухчиц:")
    for _, r in kuh_sale.iterrows():
        print(f"  {r['invoice_date']}  order_type={r['order_type']}  research={r.get('research_type')}")

    # Уникальные даты продаж (order_type=0)
    sales_only = kuh[(kuh['row_type'] == 'sale') & (kuh['order_type'] == 0)]
    dates = sales_only['invoice_date'].dropna().sort_values()
    print()
    print(f"Уникальные даты продаж ({len(dates)}):")
    for d in dates:
        print(f"  {d}")

    if len(dates) >= 2:
        gap = (dates.iloc[-1] - dates.iloc[-2]).days
        print()
        print(f"Предпоследняя дата: {dates.iloc[-2]}")
        print(f"Последняя дата:     {dates.iloc[-1]}")
        print(f"last_gap = {gap} дней")