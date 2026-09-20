"""
Диагностика строки Excel по номеру.
Использование: python lookup.py 1410
"""
import sys
import pandas as pd
from data_loader import EXCEL_PATH, SHEET_NAME


def lookup(excel_row):
    """excel_row — номер строки в Excel (как в шапке, 1-based, с шапкой)"""
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, header=0)

    # В Excel строка 1 = шапка. Данные начинаются с Excel строки 2.
    # pandas индекс 0 = Excel строка 2.
    pandas_idx = excel_row - 2

    if pandas_idx < 0 or pandas_idx >= len(df):
        print(f"❌ Строка {excel_row} вне диапазона (всего {len(df)} строк, максимум Excel = {len(df) + 1})")
        return

    row = df.iloc[pandas_idx]

    print("=" * 70)
    print(f"Excel row: {excel_row}")
    print(f"Pandas row: {pandas_idx}")
    print("=" * 70)

    print("\n--- Ключевые поля ---")
    key_fields = {
        'C — Наименование хозяйства': 'Наименование хозяйства',
        'G — Менеджер': 'Менеджер',
        'E — Область': 'Область',
        'F — Район': 'Район',
        'Q — Счет, номер': 'Счет, номер',
        'R — Счет, дата': 'Счет, дата',
        'S — Счет, сумма': 'Счет, сумма',
        'U — ПП, сумма': 'ПП, сумма',
        'V — ПП, дата': 'ПП, дата',
        'W — ПП, номер': 'ПП, номер',
        'T — ОБЩАЯ сумма за месяц': 'ОБЩАЯ сумма за месяц',
        'AI — цифра в зав-ти от цвета': 'цифра в зав-ти от цвета в  столбце R',
    }

    for label, col_name in key_fields.items():
        val = row.get(col_name, '— КОЛОНКА НЕ НАЙДЕНА —')
        print(f"  {label}: {val}")

    print("\n--- Все заполненные поля ---")
    for col in df.columns:
        val = row[col]
        if pd.notna(val) and str(val).strip() != '':
            print(f"  {col}: {val}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python lookup.py <номер строки Excel>")
        print("Пример: python lookup.py 1410")
        sys.exit(1)

    try:
        excel_row = int(sys.argv[1])
    except ValueError:
        print("❌ Номер строки должен быть числом")
        sys.exit(1)

    lookup(excel_row)