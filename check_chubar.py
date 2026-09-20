import pandas as pd
from datetime import datetime
from data_loader import load_all_data, get_payments_data

data = load_all_data()
df = data['df']

payments = get_payments_data(df, ['2026 сентябрь'], 'Чубарь Д.')
print(f"Всего оплат: {len(payments)}")
print(f"Сумма: {payments['payment_amount'].sum():,.0f}")
print()
print("По категориям:")
print(payments.groupby('category')['payment_amount'].sum().to_string())
print()

sept_start = datetime(2026, 9, 1)
sept_end = datetime(2026, 9, 30, 23, 59, 59)

def is_current(d):
    if pd.isna(d):
        return False
    return sept_start <= d <= sept_end

payments = payments.copy()
payments['is_current'] = payments['invoice_date'].apply(is_current)

old = payments[~payments['is_current']]
print(f"Старых оплат: {len(old)}, сумма: {old['payment_amount'].sum():,.0f}")
print()
print("Старые оплаты (invoice_date вне сентября):")
for _, r in old.iterrows():
    inv = r['invoice_date'].strftime('%d.%m.%Y') if pd.notna(r['invoice_date']) else '—'
    pay = r['payment_date'].strftime('%d.%m.%Y') if pd.notna(r['payment_date']) else '—'
    days = (r['payment_date'] - r['invoice_date']).days if pd.notna(r['invoice_date']) and pd.notna(r['payment_date']) else '—'
    print(f"  Счёт: {inv} → Оплата: {pay} | {days} дн. | {r['payment_amount']:>8,.0f} | {r['category']}")