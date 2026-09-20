import pandas as pd
import json
import os
from datetime import datetime, timedelta
import hashlib

from comments_parser import load_comments

EXCEL_PATH = r"C:\ЦЕНТР ИЗЖ\Х\!-Х12.1.xlsm"
SHEET_NAME = "ИСХОДНЫЕ ДАННЫЕ"
DB_PATH = "database.json"
CACHE_DURATION = 600
_last_load = None
_cached_data = None

MANAGERS_LIST = [
    'Все менеджеры',
    'Бабура С.',
    'Крупенькина Е.',
    'Чубарь Д.',
    'Буян В.',
    'Пудакевич И.',
    'Федук П.',
]

# Белый список активных менеджеров для фильтра.
# Остальные из database.json скрываются из селектора,
# но продолжают фигурировать в данных.
ACTIVE_MANAGERS = [
    'Все менеджеры',
    'Бабура С.',
    'Крупенькина Е.',
    'Чубарь Д.',
    'Буян В.',
    'Пудакевич И.',
    'Федук П.',
]

DEFAULT_BONUS_SETTINGS = {
    'use_by_category': False,
    'use_by_threshold': True,
    'rates_by_category': {
        '0-30': 0.0,
        '31-60': 0.0,
        '61-90': 0.0,
        '91-120': 0.0,
        '120+': 0.0,
    },
    'thresholds': [
        {'min_amount': 20000.0, 'rate': 1.0},
        {'min_amount': 35000.0, 'rate': 2.0},
        {'min_amount': 50000.0, 'rate': 3.0},
    ],
}

# === ТРАНСЛИТЕРАЦИЯ И ПАРОЛИ ===

TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
}

# Ручной маппинг для менеджеров (по фамилии → латиница)
MANAGER_LOGIN_MAP = {
    'Бабура С.': 'babura',
    'Крупенькина Е.': 'krupenkina',
    'Чубарь Д.': 'chubar',
    'Буян В.': 'buyan',
    'Пудакевич И.': 'pudakevich',
    'Федук П.': 'feduk',
}


def transliterate(text):
    """Транслитерация русского текста в латиницу"""
    if not text:
        return ''
    result = []
    for ch in text:
        result.append(TRANSLIT_MAP.get(ch, ch))
    return ''.join(result)


def generate_login_from_manager(manager_name):
    """Логин из имени менеджера. Сначала пробуем ручной маппинг."""
    if manager_name in MANAGER_LOGIN_MAP:
        return MANAGER_LOGIN_MAP[manager_name]
    # Иначе — транслитерация фамилии (первое слово)
    first_word = manager_name.split()[0] if manager_name else ''
    return transliterate(first_word).lower()


def generate_password(length=8):
    """Случайный пароль"""
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def find_data_end(df):
    empty_streak = 0
    for i in range(len(df)):
        row = df.iloc[i]
        company_empty = pd.isna(row.get('company')) or str(row.get('company')).strip() == ''
        invoice_empty = pd.isna(row.get('invoice_num')) or str(row.get('invoice_num')).strip() == ''
        date_empty = pd.isna(row.get('invoice_date')) or str(row.get('invoice_date')).strip() == ''
        if company_empty and invoice_empty and date_empty:
            empty_streak += 1
            if empty_streak >= 2:
                return i - 1
        else:
            empty_streak = 0
    return len(df) - 1


def load_excel_data():
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, header=0)
        return process_data(df)
    except Exception as e:
        print(f"Ошибка загрузки Excel: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_data(df):
    column_mapping = {
        'Наименование хозяйства': 'company',
        'Область': 'oblast',
        'Район': 'raion',
        'Менеджер': 'manager',
        'Вид Исследования': 'research_type',
        'Счет, номер': 'invoice_num',
        'Счет, дата': 'invoice_date',
        'Счет, сумма': 'invoice_amount',
        'ПП, сумма': 'payment_amount',
        'ПП, дата': 'payment_date',
        'ПП, номер': 'payment_num',
        'Срок оплаты, дни': 'payment_term',
        'цифра в зав-ти от цвета в  столбце R': 'order_type',
        'Кол-во проб': 'samples_count',
        'Сумма, BYN': 'amount',
        'Номер Протокола': 'protocol_num',
        'Предприятие': 'company_dup',
    }

    rename_map = {}
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns:
            rename_map[old_name] = new_name

    df = df.rename(columns=rename_map)

    required_cols = ['company', 'manager', 'invoice_num', 'invoice_date',
                     'invoice_amount', 'payment_amount', 'order_type']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"⚠️ Отсутствуют критичные колонки: {missing_cols}")
        return None

    df['invoice_date'] = pd.to_datetime(df['invoice_date'], errors='coerce')
    df['payment_date'] = pd.to_datetime(df['payment_date'], errors='coerce')
    df['invoice_amount'] = pd.to_numeric(df['invoice_amount'], errors='coerce').fillna(0)
    df['payment_amount'] = pd.to_numeric(df['payment_amount'], errors='coerce').fillna(0)

    data_end = find_data_end(df)
    print(f"✅ Граница данных: строка {data_end + 2} (Excel)")
    df = df.iloc[:data_end + 1].copy()

    comments = load_comments()

    sales_df = df.copy()
    sales_df['row_type'] = 'sale'

    payment_rows = []
    for idx, row in df.iterrows():
        excel_row = idx + 2
        total_payment = row['payment_amount']
        if total_payment == 0 and pd.isna(row['payment_num']):
            continue

        parts = comments.get(excel_row, [])

        if not parts:
            new_row = row.to_dict()
            new_row['row_type'] = 'payment'
            payment_rows.append(new_row)
        else:
            total_in_comment = sum(p['amount'] for p in parts)
            first_amount = total_payment - total_in_comment

            first_row = row.to_dict()
            first_row['payment_amount'] = first_amount
            first_row['row_type'] = 'payment'
            payment_rows.append(first_row)

            for p in parts:
                new_row = row.to_dict()
                new_row['payment_amount'] = p['amount']
                new_row['payment_date'] = p['date']
                new_row['payment_num'] = p['num']
                new_row['row_type'] = 'payment'
                payment_rows.append(new_row)

    payments_df = pd.DataFrame(payment_rows) if payment_rows else pd.DataFrame(columns=sales_df.columns)

    combined = pd.concat([sales_df, payments_df], ignore_index=True)
    combined['payment_date'] = combined['payment_date'].fillna(combined['invoice_date'])

    keep_cols = ['company', 'oblast', 'raion', 'manager', 'research_type',
                 'invoice_num', 'invoice_date', 'invoice_amount',
                 'payment_amount', 'payment_date', 'order_type', 'row_type']
    combined = combined[keep_cols].copy()

    sales_only = combined[combined['row_type'] == 'sale']
    total_sales = float(sales_only[sales_only['order_type'] == 0]['invoice_amount'].sum())
    total_prepayments = float(sales_only[sales_only['order_type'] == 1]['invoice_amount'].sum())

    payments_only = combined[combined['row_type'] == 'payment']
    total_returns = float(payments_only['payment_amount'].sum())

    db = load_database()

    print(f"✅ Строк 'sale': {len(sales_df)}, 'payment': {len(payments_df)}")

    return {
        'df': combined,
        'database': db,
        'summary': {
            'total_sales': total_sales,
            'total_prepayments': total_prepayments,
            'total_returns': total_returns,
            'total_debt': total_sales - total_returns,
            'debt_percent': (100 - (total_returns / total_sales * 100)) if total_sales > 0 else 0.0,
        }
    }


# === ПЕРИОДЫ ===

def get_period_options(df):
    months_ru = {
        1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
        5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
        9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
    }

    options = ['Весь период']
    if df is None or df.empty:
        return options

    sales = df[(df['row_type'] == 'sale') & (df['order_type'] == 0)]
    if sales.empty:
        return options

    years = sorted(sales['invoice_date'].dt.year.dropna().unique().astype(int).tolist())
    years = [y for y in years if y >= 2025]

    for y in years:
        options.append(str(y))

    if 2026 in years:
        months = sales[sales['invoice_date'].dt.year == 2026]['invoice_date'].dt.month.dropna().unique()
        for m in sorted(months.astype(int).tolist()):
            options.append(f"2026 {months_ru[m]}")

    return options


def get_period_label(period_selection):
    if isinstance(period_selection, str):
        period_selection = [period_selection]
    if not period_selection or 'Весь период' in period_selection:
        return 'весь период'
    if len(period_selection) == 1:
        return period_selection[0].lower()
    return f"{len(period_selection)} период(ов)"


def _parse_period_selection(period_selection):
    months_ru = {
        'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
        'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
        'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
    }
    years = set()
    months_2026 = set()
    for p in period_selection:
        if p == 'Весь период':
            continue
        if p.isdigit() and len(p) == 4:
            years.add(int(p))
        elif p.startswith('2026 '):
            m = months_ru.get(p.replace('2026 ', '').strip())
            if m:
                months_2026.add(m)
    return years, months_2026


def filter_sales(df, period_selection, manager):
    if df is None or df.empty:
        return df
    work = df[df['row_type'] == 'sale'].copy()
    if manager and manager != 'Все менеджеры':
        work = work[work['manager'] == manager]
    if not period_selection or 'Весь период' in period_selection:
        return work
    years, months_2026 = _parse_period_selection(period_selection)
    mask = pd.Series(False, index=work.index)
    for y in years:
        mask |= (work['invoice_date'].dt.year == y)
    for m in months_2026:
        mask |= ((work['invoice_date'].dt.year == 2026) & (work['invoice_date'].dt.month == m))
    return work[mask].copy()


def filter_payments(df, period_selection, manager):
    if df is None or df.empty:
        return df
    work = df[df['row_type'] == 'payment'].copy()
    if manager and manager != 'Все менеджеры':
        work = work[work['manager'] == manager]
    if not period_selection or 'Весь период' in period_selection:
        return work
    years, months_2026 = _parse_period_selection(period_selection)
    mask = pd.Series(False, index=work.index)
    for y in years:
        mask |= (work['payment_date'].dt.year == y)
    for m in months_2026:
        mask |= ((work['payment_date'].dt.year == 2026) & (work['payment_date'].dt.month == m))
    return work[mask].copy()


# === ПОКАЗАТЕЛИ ===

def get_total_sales(df_sales):
    if df_sales is None or df_sales.empty:
        return 0.0
    sales = df_sales[df_sales['order_type'] == 0]
    return float(sales['invoice_amount'].sum())


def get_total_payments(df_payments):
    if df_payments is None or df_payments.empty:
        return 0.0
    return float(df_payments['payment_amount'].sum())


def get_total_prepayments(df_sales):
    if df_sales is None or df_sales.empty:
        return 0.0, 0
    prep = df_sales[df_sales['order_type'] == 1]
    return float(prep['invoice_amount'].sum()), int(prep['invoice_num'].nunique())


def get_companies_count(df_sales):
    if df_sales is None or df_sales.empty:
        return 0
    sales = df_sales[df_sales['order_type'] == 0]
    return int(sales['company'].nunique())


def get_applications_count(df_sales):
    if df_sales is None or df_sales.empty:
        return 0
    sales = df_sales[df_sales['order_type'] == 0]
    if sales.empty:
        return 0
    return int(sales[['company', 'invoice_num', 'invoice_date']].drop_duplicates().shape[0])


def get_avg_check(df_sales):
    apps = get_applications_count(df_sales)
    if apps == 0:
        return 0.0
    return get_total_sales(df_sales) / apps


# === РАЗБИВКИ ===

def get_sales_by_company(df_sales):
    if df_sales is None or df_sales.empty:
        return pd.DataFrame(columns=['company', 'raion', 'oblast', 'manager', 'amount'])
    sales = df_sales[df_sales['order_type'] == 0]
    if sales.empty:
        return pd.DataFrame(columns=['company', 'raion', 'oblast', 'manager', 'amount'])
    result = sales.groupby(['company', 'raion', 'oblast', 'manager'])['invoice_amount'].sum().reset_index()
    result.columns = ['company', 'raion', 'oblast', 'manager', 'amount']
    return result.sort_values('amount', ascending=False)


def get_sales_by_raion(df_sales):
    if df_sales is None or df_sales.empty:
        return pd.DataFrame(columns=['raion', 'amount', 'share'])
    sales = df_sales[df_sales['order_type'] == 0]
    if sales.empty:
        return pd.DataFrame(columns=['raion', 'amount', 'share'])
    total = sales['invoice_amount'].sum()
    result = sales.groupby('raion')['invoice_amount'].sum().reset_index()
    result.columns = ['raion', 'amount']
    result['share'] = result['amount'] / total if total > 0 else 0
    return result.sort_values('amount', ascending=False)


def get_sales_by_oblast(df_sales):
    if df_sales is None or df_sales.empty:
        return pd.DataFrame(columns=['oblast', 'amount', 'share'])
    sales = df_sales[df_sales['order_type'] == 0]
    if sales.empty:
        return pd.DataFrame(columns=['oblast', 'amount', 'share'])
    total = sales['invoice_amount'].sum()
    result = sales.groupby('oblast')['invoice_amount'].sum().reset_index()
    result.columns = ['oblast', 'amount']
    result['share'] = result['amount'] / total if total > 0 else 0
    return result.sort_values('amount', ascending=False)


def get_sales_by_research(df_sales):
    if df_sales is None or df_sales.empty:
        return pd.DataFrame(columns=['research_type', 'amount', 'share'])
    sales = df_sales[df_sales['order_type'] == 0]
    if sales.empty:
        return pd.DataFrame(columns=['research_type', 'amount', 'share'])
    total = sales['invoice_amount'].sum()
    result = sales.groupby('research_type')['invoice_amount'].sum().reset_index()
    result.columns = ['research_type', 'amount']
    result['share'] = result['amount'] / total if total > 0 else 0
    return result.sort_values('amount', ascending=False)


# === ДЕБИТОРКА ===

def get_debt_summary(df, period_selection=None, manager=None):
    if df is None or df.empty:
        return {'sales': 0, 'payments': 0, 'debt': 0, 'percent': 0,
                'payments_current': 0, 'payments_old': 0}

    sales_df = filter_sales(df, period_selection, manager)
    payments_df = filter_payments(df, period_selection, manager)

    sales = float(sales_df[sales_df['order_type'] == 0]['invoice_amount'].sum())
    payments = float(payments_df['payment_amount'].sum())

    sales_period = filter_sales(df, period_selection, manager)
    sales_period_keys = sales_period[['company', 'invoice_num', 'invoice_date']].drop_duplicates()

    payments_all = df[df['row_type'] == 'payment']
    if manager and manager != 'Все менеджеры':
        payments_all = payments_all[payments_all['manager'] == manager]

    merged = payments_all.merge(
        sales_period_keys,
        on=['company', 'invoice_num', 'invoice_date'],
        how='inner'
    )
    payments_current = float(merged['payment_amount'].sum())
    payments_old = payments - payments_current
    if payments_old < 0:
        payments_old = 0

    debt = sales - payments if sales > payments else 0
    percent = (100 - (payments / sales * 100)) if sales > 0 else 0

    return {
        'sales': sales,
        'payments': payments,
        'payments_current': payments_current,
        'payments_old': payments_old,
        'debt': debt,
        'percent': percent,
    }


def get_debt_data(df, period_selection=None, manager=None):
    if df is None or df.empty:
        return pd.DataFrame()

    sales_period = filter_sales(df, period_selection, manager)
    sales = sales_period[sales_period['order_type'] == 0].copy()
    if sales.empty:
        return pd.DataFrame()

    payments_all = df[df['row_type'] == 'payment'].copy()
    if manager and manager != 'Все менеджеры':
        payments_all = payments_all[payments_all['manager'] == manager]

    payments_grouped = payments_all.groupby(['company', 'invoice_num', 'invoice_date'])['payment_amount'].sum().reset_index()
    payments_grouped.columns = ['company', 'invoice_num', 'invoice_date', 'paid_amount']

    sales_grouped = sales.groupby(['company', 'manager', 'raion', 'oblast',
                                   'invoice_num', 'invoice_date']).agg({
        'invoice_amount': 'sum'
    }).reset_index()

    merged = sales_grouped.merge(
        payments_grouped,
        on=['company', 'invoice_num', 'invoice_date'],
        how='left'
    ).fillna({'paid_amount': 0})

    merged['debt_amount'] = merged['invoice_amount'] - merged['paid_amount']
    merged = merged[merged['debt_amount'] > 0].copy()

    now = datetime.now()
    merged['days'] = merged['invoice_date'].apply(
        lambda d: (now - d).days if pd.notna(d) else 0
    )

    def cat(days):
        if days <= 30:
            return '0-30'
        elif days <= 60:
            return '31-60'
        elif days <= 90:
            return '61-90'
        elif days <= 120:
            return '91-120'
        return '120+'

    merged['category'] = merged['days'].apply(cat)
    return merged


def get_debt_structure(df, period_selection=None, manager=None):
    debt_df = get_debt_data(df, period_selection, manager)
    if debt_df.empty:
        return pd.DataFrame(columns=['category', 'amount', 'count'])

    result = debt_df.groupby('category').agg({
        'debt_amount': 'sum',
        'company': 'count'
    }).reset_index()
    result.columns = ['category', 'amount', 'count']

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    result['category'] = pd.Categorical(result['category'], categories=order, ordered=True)
    return result.sort_values('category').reset_index(drop=True)


def get_debt_by_manager(df, period_selection=None):
    if df is None or df.empty:
        return pd.DataFrame()

    sales_period = filter_sales(df, period_selection, 'Все менеджеры')
    sales = sales_period[sales_period['order_type'] == 0]

    sales_by_mgr = sales.groupby('manager')['invoice_amount'].sum().reset_index()
    sales_by_mgr.columns = ['manager', 'sales']

    payments_all = df[df['row_type'] == 'payment']
    if period_selection and 'Весь период' not in period_selection:
        payments_all = filter_payments(df, period_selection, 'Все менеджеры')

    payments_by_mgr = payments_all.groupby('manager')['payment_amount'].sum().reset_index()
    payments_by_mgr.columns = ['manager', 'payments']

    merged = pd.merge(sales_by_mgr, payments_by_mgr, on='manager', how='outer').fillna(0)
    merged['debt'] = (merged['sales'] - merged['payments']).clip(lower=0)
    merged['percent'] = merged.apply(
        lambda r: (100 - (r['payments'] / r['sales'] * 100)) if r['sales'] > 0 else 0, axis=1
    )

    total_debt = merged['debt'].sum()
    merged['debt_share'] = merged['debt'] / total_debt * 100 if total_debt > 0 else 0

    return merged.sort_values('debt', ascending=False)


def get_debt_companies(df, period_selection=None, manager=None):
    debt_df = get_debt_data(df, period_selection, manager)
    if debt_df.empty:
        return pd.DataFrame()

    result = debt_df.groupby(['company', 'manager']).agg({
        'debt_amount': 'sum'
    }).reset_index()
    result.columns = ['company', 'manager', 'total_debt']

    pivot = debt_df.pivot_table(
        index='company',
        columns='category',
        values='debt_amount',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    for cat in order:
        if cat not in pivot.columns:
            pivot[cat] = 0

    pivot = pivot[['company'] + order]

    result = pd.merge(result, pivot, on='company', how='left')
    return result.sort_values('total_debt', ascending=False)


# === ОПЛАТЫ ===

def get_payment_category(invoice_date, payment_date):
    if pd.isna(invoice_date) or pd.isna(payment_date):
        return '0-30'
    days = (payment_date - invoice_date).days
    if days <= 30:
        return '0-30'
    elif days <= 60:
        return '31-60'
    elif days <= 90:
        return '61-90'
    elif days <= 120:
        return '91-120'
    else:
        return '120+'


def get_payments_data(df, period_selection=None, manager=None):
    if df is None or df.empty:
        return pd.DataFrame()

    payments = filter_payments(df, period_selection, manager)
    payments = payments[payments['payment_amount'] > 0].copy()

    if payments.empty:
        return pd.DataFrame()

    payments['invoice_date_eff'] = payments['invoice_date'].fillna(payments['payment_date'])
    payments['category'] = payments.apply(
        lambda r: get_payment_category(r['invoice_date_eff'], r['payment_date']),
        axis=1
    )

    return payments


def get_payments_structure(df, period_selection=None, manager=None):
    payments = get_payments_data(df, period_selection, manager)
    if payments.empty:
        return pd.DataFrame(columns=['category', 'amount', 'count'])

    result = payments.groupby('category').agg({
        'payment_amount': 'sum',
        'company': 'count'
    }).reset_index()
    result.columns = ['category', 'amount', 'count']

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    result['category'] = pd.Categorical(result['category'], categories=order, ordered=True)
    return result.sort_values('category').reset_index(drop=True)


def calc_bonus_for_payments(payments_df, bonus_settings):
    """
    Считает бонус для DataFrame оплат.
    Возвращает DataFrame с колонками: payment_amount, bonus, bonus_category, bonus_threshold
    """
    if payments_df is None or payments_df.empty:
        return payments_df

    df = payments_df.copy()

    use_cat = bonus_settings.get('use_by_category', False)
    use_thr = bonus_settings.get('use_by_threshold', False)
    rates_cat = bonus_settings.get('rates_by_category', {})
    thresholds = bonus_settings.get('thresholds', [])

    # Бонус по категориям
    if use_cat:
        df['bonus_category'] = df.apply(
            lambda r: r['payment_amount'] * rates_cat.get(r.get('category', ''), 0.0) / 100.0,
            axis=1
        )
    else:
        df['bonus_category'] = 0.0

    # Бонус по порогам — считается по общей сумме оплат менеджера за период
    # Здесь возвращаем только флаг — расчёт на уровне менеджера в get_payments_by_manager
    df['bonus_threshold'] = 0.0

    return df


def calc_threshold_bonus(total_amount, thresholds):
    """
    Считает бонус по порогу для общей суммы.
    thresholds: [{'min_amount': X, 'rate': Y}, ...]
    """
    if not thresholds or total_amount <= 0:
        return 0.0

    sorted_thr = sorted(thresholds, key=lambda x: x['min_amount'], reverse=True)
    for t in sorted_thr:
        if total_amount >= t['min_amount']:
            return total_amount * t['rate'] / 100.0
    return 0.0


def get_payments_by_manager(df, period_selection=None, bonus_settings=None):
    if df is None or df.empty:
        return pd.DataFrame()

    if bonus_settings is None:
        bonus_settings = DEFAULT_BONUS_SETTINGS

    payments = get_payments_data(df, period_selection, 'Все менеджеры')
    if payments.empty:
        return pd.DataFrame()

    use_cat = bonus_settings.get('use_by_category', False)
    use_thr = bonus_settings.get('use_by_threshold', False)
    rates_cat = bonus_settings.get('rates_by_category', {})
    thresholds = bonus_settings.get('thresholds', [])

    # Бонус по категориям — для каждой оплаты
    if use_cat:
        payments['bonus_category'] = payments.apply(
            lambda r: r['payment_amount'] * rates_cat.get(r.get('category', ''), 0.0) / 100.0,
            axis=1
        )
    else:
        payments['bonus_category'] = 0.0

    # Группируем по менеджерам
    result = payments.groupby('manager').agg({
        'payment_amount': 'sum',
        'bonus_category': 'sum',
        'company': 'count'
    }).reset_index()
    result.columns = ['manager', 'payments', 'bonus_category', 'count']

    # Бонус по порогам — от общей суммы оплат менеджера
    if use_thr:
        result['bonus_threshold'] = result['payments'].apply(
            lambda total: calc_threshold_bonus(total, thresholds)
        )
    else:
        result['bonus_threshold'] = 0.0

    result['bonus'] = result['bonus_category'] + result['bonus_threshold']

    total_payments = result['payments'].sum()
    result['share'] = result['payments'] / total_payments * 100 if total_payments > 0 else 0

    return result.sort_values('payments', ascending=False)


def get_payments_by_manager_and_category(df, period_selection=None):
    if df is None or df.empty:
        return pd.DataFrame()

    payments = get_payments_data(df, period_selection, 'Все менеджеры')
    if payments.empty:
        return pd.DataFrame()

    result = payments.groupby(['manager', 'category'])['payment_amount'].sum().reset_index()
    result.columns = ['manager', 'category', 'amount']

    pivot = result.pivot_table(
        index='manager',
        columns='category',
        values='amount',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    for cat in order:
        if cat not in pivot.columns:
            pivot[cat] = 0

    pivot = pivot[['manager'] + order]
    return pivot


def get_payments_companies(df, period_selection=None, manager=None, bonus_settings=None):
    payments = get_payments_data(df, period_selection, manager)
    if payments.empty:
        return pd.DataFrame()

    if bonus_settings is None:
        bonus_settings = DEFAULT_BONUS_SETTINGS

    use_cat = bonus_settings.get('use_by_category', False)
    rates_cat = bonus_settings.get('rates_by_category', {})

    if use_cat:
        payments['bonus'] = payments.apply(
            lambda r: r['payment_amount'] * rates_cat.get(r.get('category', ''), 0.0) / 100.0,
            axis=1
        )
    else:
        payments['bonus'] = 0.0

    result = payments.groupby(['company', 'manager', 'category']).agg({
        'payment_amount': 'sum',
        'bonus': 'sum'
    }).reset_index()

    pivot_amount = result.pivot_table(
        index=['company', 'manager'],
        columns='category',
        values='payment_amount',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    pivot_bonus = result.pivot_table(
        index=['company', 'manager'],
        columns='category',
        values='bonus',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    for cat in order:
        if cat not in pivot_amount.columns:
            pivot_amount[cat] = 0
        if cat not in pivot_bonus.columns:
            pivot_bonus[cat] = 0

    pivot_amount['total_payments'] = pivot_amount[order].sum(axis=1)
    pivot_bonus['total_bonus'] = pivot_bonus[order].sum(axis=1)

    merged = pivot_amount[['company', 'manager', 'total_payments'] + order].merge(
        pivot_bonus[['company', 'manager', 'total_bonus']],
        on=['company', 'manager'],
        how='left'
    )

    return merged.sort_values('total_payments', ascending=False)


# === НАСТРОЙКИ БОНУСОВ ===

def get_bonus_settings():
    db = load_database()
    settings = db.get('bonus_settings')
    if not settings:
        # Совместимость со старой структурой
        old_rates = db.get('bonus_rates', {})
        settings = dict(DEFAULT_BONUS_SETTINGS)
        settings['rates_by_category'] = {
            '0-30': old_rates.get('0-30', 0.0),
            '31-60': old_rates.get('31-60', 0.0),
            '61-90': old_rates.get('61-90', 0.0),
            '91-120': old_rates.get('91-120', 0.0),
            '120+': old_rates.get('120+', 0.0),
        }
    return settings


def save_bonus_settings(settings):
    db = load_database()
    db['bonus_settings'] = settings
    save_database(db)


def get_bonus_rates():
    """Совместимость"""
    return get_bonus_settings().get('rates_by_category', {})


def save_bonus_rates(rates):
    """Совместимость"""
    settings = get_bonus_settings()
    settings['rates_by_category'] = rates
    save_bonus_settings(settings)


# === СОВМЕСТИМОСТЬ ===

def get_available_months(df):
    return get_period_options(df)


def get_available_managers(df=None):
    """
    Возвращает список менеджеров для фильтра — только те,
    кто в белом списке ACTIVE_MANAGERS.
    Остальные (архивные) скрываются из UI, но остаются в данных.
    """
    return ACTIVE_MANAGERS


def filter_by_period(df, period_selection, manager):
    return filter_sales(df, period_selection, manager)


# === БАЗА ===

# === АВТОРИЗАЦИЯ ===

def authenticate(username, password):
    """Проверка логина/пароля. Возвращает dict пользователя или None."""
    db = load_database()
    users = db.get('users', {})
    if username not in users:
        return None
    user = users[username]
    if user.get('blocked', False):
        return None
    if verify_password(password, user.get('password', '')):
        return {'username': username, **user}
    return None


def create_user(username, name, role, manager_binding, allowed_tabs, password=None):
    """
    Создаёт пользователя. Возвращает сгенерированный пароль.
    """
    db = load_database()
    users = db.get('users', {})

    if username in users:
        raise ValueError(f"Пользователь {username} уже существует")

    if not password:
        password = generate_password()

    users[username] = {
        'password': hash_password(password),
        'name': name,
        'role': role,
        'manager_binding': manager_binding,
        'blocked': False,
        'allowed_tabs': allowed_tabs,
        'last_login': None,
    }
    db['users'] = users
    save_database(db)
    return password


def update_user(username, **kwargs):
    """Обновление пользователя"""
    db = load_database()
    users = db.get('users', {})
    if username not in users:
        raise ValueError(f"Пользователь {username} не найден")

    user = users[username]

    if 'new_password' in kwargs:
        pwd = kwargs.pop('new_password')
        if pwd:
            user['password'] = hash_password(pwd)

    if 'blocked' in kwargs:
        # Защита: суперадмин не может заблокировать себя
        if username == 'superadmin' and kwargs['blocked']:
            raise ValueError("Нельзя заблокировать суперадмина")
        user['blocked'] = kwargs.pop('blocked')

    if 'role' in kwargs:
        if username == 'superadmin' and kwargs['role'] != 'super_admin':
            raise ValueError("Нельзя изменить роль суперадмина")
        user['role'] = kwargs.pop('role')

    for key, value in kwargs.items():
        user[key] = value

    db['users'] = users
    save_database(db)


def delete_user(username):
    """Удаление пользователя"""
    if username == 'superadmin':
        raise ValueError("Нельзя удалить суперадмина")

    db = load_database()
    users = db.get('users', {})
    if username in users:
        del users[username]
        db['users'] = users
        save_database(db)


def log_login(username):
    """Запись входа в login_history.json"""
    import json
    history_path = 'login_history.json'

    entry = {
        'username': username,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []

    # Обрезаем: только за последний месяц
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    history = [h for h in history if h.get('time', '') >= cutoff]
    history.append(entry)

    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_login_stats(username):
    """Возвращает: последний вход, кол-во входов за месяц"""
    import json
    history_path = 'login_history.json'

    if not os.path.exists(history_path):
        return {'last_login': None, 'count_30d': 0}

    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except:
        return {'last_login': None, 'count_30d': 0}

    user_history = [h for h in history if h.get('username') == username]
    if not user_history:
        return {'last_login': None, 'count_30d': 0}

    last = max(user_history, key=lambda x: x.get('time', ''))
    return {
        'last_login': last.get('time'),
        'count_30d': len(user_history),
    }

def load_database():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return create_default_database()


def create_default_database():
    db = {
        "managers": {},
        "companies": {},
        "districts": {},
        "users": {
            "superadmin": {
                "password": hash_password("15041976"),
                "name": "СуперАдминистратор",
                "role": "super_admin",
                "manager_binding": None,
                "blocked": False,
                "allowed_tabs": ["all"],
                "last_login": None,
            }
        },
        "settings": {
            "default_credit_limit": 5000,
            "debt_warning_days": 100,
            "debt_legal_days": 120,
            "refresh_interval_minutes": 10
        },
        "bonus_settings": DEFAULT_BONUS_SETTINGS,
    }
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    return db


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hash_value):
    return hash_password(password) == hash_value


def save_database(db):
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def load_all_data(force_refresh=False):
    global _last_load, _cached_data

    if force_refresh or _cached_data is None or (datetime.now() - _last_load).seconds > CACHE_DURATION:
        excel_data = load_excel_data()
        if excel_data:
            db = load_database()
            excel_data['database'] = db
            _cached_data = excel_data
            _last_load = datetime.now()

    return _cached_data