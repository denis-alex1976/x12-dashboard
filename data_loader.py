import pandas as pd
import json
import os
from datetime import datetime, timedelta
import hashlib

try:
    from comments_parser import load_comments, parse_comment
    _COMMENTS_AVAILABLE = True
except Exception:
    _COMMENTS_AVAILABLE = False
    def load_comments():
        return {}
    def parse_comment(text):
        return []

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

ACTIVE_MANAGERS = [
    'Все менеджеры',
    'Бабура С.',
    'Крупенькина Е.',
    'Чубарь Д.',
    'Буян В.',
    'Пудакевич И.',
    'Федук П.',
]

ALL_MANAGERS = [
    'Бабура С.',
    'Крупенькина Е.',
    'Чубарь Д.',
    'Буян В.',
    'Пудакевич И.',
    'Федук П.',
    'Вашкевич А.',
    'Шиянов В.',
    'Пломодьялов Д.',
    'Сагайдак В.',
    'Зварич Д.',
    'Нестер А.',
    'Ребковец Е.',
    'Бабайцев Е.',
]

DEFAULT_BONUS_SETTINGS = {
    'use_by_category': False,
    'use_by_threshold': True,
    'rates_by_category': {
        '0-30': 0.0, '31-60': 0.0, '61-90': 0.0,
        '91-120': 0.0, '120+': 0.0,
    },
    'thresholds': [
        {'min_amount': 20000.0, 'rate': 1.0},
        {'min_amount': 35000.0, 'rate': 2.0},
        {'min_amount': 50000.0, 'rate': 3.0},
    ],
}

DEFAULT_ADMIN_SETTINGS = {
    'allow_admins_blacklist': True,
    'allow_admins_golden': True,
    'allow_admins_potential_days': True,
    'allow_admins_trust_limits': True,
    'show_trust_limits': True,
    'new_status_days': 30,
    'returned_days': 300,
    'passive_days': 300,
    'potential_warning_days': 90,
    'inactive_days': 60,
    'debtor_days': 90,
    'debtor_threshold': 2,
    'debtor_days': 90,
    'debtor_threshold': 2,
    'prepayment_active_days': 30,
}

DEFAULT_TRUST_LIMITS = {
    'threshold_1': 5000.0,
    'threshold_2': 7000.0,
    'threshold_3': 10000.0,
}

# === GOOGLE SHEETS ===
GSHEETS_CREDENTIALS = "service-account.json"
GSHEETS_SPREADSHEET_ID = "1AWSwJECekzgfvbYlBsBk-Ws78hpNp5TC7VSPdvv0Nso"
GSHEETS_WORKSHEET = "Data"
GSHEETS_USERS_WORKSHEET = "Users"
GSHEETS_LOGIN_HISTORY_WORKSHEET = "LoginHistory"
GSHEETS_BONUS_WORKSHEET = "BonusSettings"
GSHEETS_COMPANY_FLAGS_WORKSHEET = "CompanyFlags"
GSHEETS_TRUST_LIMITS_WORKSHEET = "TrustLimits"

GSHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

USER_COLUMNS = ['username', 'password_hash', 'name', 'role',
                'manager_binding', 'blocked', 'allowed_tabs']

LOGIN_HISTORY_COLUMNS = ['time', 'username', 'ip', 'user_agent',
                          'device_id', 'status', 'note']

BONUS_COLUMNS = ['key', 'value']

COMPANY_FLAGS_COLUMNS = ['company_code', 'company_name', 'blacklist',
                          'golden_fund', 'status', 'status_date',
                          'date_added', 'added_by']

TRUST_LIMITS_COLUMNS = ['threshold', 'amount']

USERS_CACHE_TTL = 30


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

MANAGER_LOGIN_MAP = {
    'Бабура С.': 'babura',
    'Крупенькина Е.': 'krupenkina',
    'Чубарь Д.': 'chubar',
    'Буян В.': 'buyan',
    'Пудакевич И.': 'pudakevich',
    'Федук П.': 'feduk',
}


def transliterate(text):
    if not text:
        return ''
    return ''.join(TRANSLIT_MAP.get(ch, ch) for ch in text)


def generate_login_from_manager(manager_name):
    if manager_name in MANAGER_LOGIN_MAP:
        return MANAGER_LOGIN_MAP[manager_name]
    first_word = manager_name.split()[0] if manager_name else ''
    return transliterate(first_word).lower()


def generate_password(length=8):
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# === GOOGLE SHEETS (с кэшированием) ===

_gsheets_client = None
_gsheets_spreadsheet = None
_worksheets_cache = {}
_users_cache = {'data': None, 'time': None}
_summary_cache = {'data': None, 'time': None}
SUMMARY_TTL = 300  # 5 минут


def _get_gsheets_creds():
    from google.oauth2.service_account import Credentials
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(creds_dict, scopes=GSHEETS_SCOPES)
    except Exception:
        pass
    return Credentials.from_service_account_file(GSHEETS_CREDENTIALS, scopes=GSHEETS_SCOPES)


def _get_gsheets_client():
    global _gsheets_client
    if _gsheets_client is None:
        import gspread
        _gsheets_client = gspread.authorize(_get_gsheets_creds())
    return _gsheets_client


def _get_spreadsheet():
    global _gsheets_spreadsheet
    if _gsheets_spreadsheet is None:
        gc = _get_gsheets_client()
        _gsheets_spreadsheet = gc.open_by_key(GSHEETS_SPREADSHEET_ID)
    return _gsheets_spreadsheet


def _get_worksheet(name):
    global _worksheets_cache
    if name not in _worksheets_cache:
        sh = _get_spreadsheet()
        _worksheets_cache[name] = sh.worksheet(name)
    return _worksheets_cache[name]


def _invalidate_users_cache():
    global _users_cache
    _users_cache = {'data': None, 'time': None}


def _invalidate_summary_cache():
    global _summary_cache
    _summary_cache = {'data': None, 'time': None}


# === ДАННЫЕ ИЗ GOOGLE SHEETS ===

def load_from_gsheets():
    try:
        worksheet = _get_worksheet(GSHEETS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            print("Google Sheets пустой")
            return None

        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        df = df.replace('', pd.NA)
        print(f"Загружено из Google Sheets: {len(df)} строк")
        return df
    except Exception as e:
        print(f"Ошибка чтения Google Sheets: {e}")
        return None


# === ПОЛЬЗОВАТЕЛИ ===

def load_users_from_gsheets():
    try:
        worksheet = _get_worksheet(GSHEETS_USERS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return {}

        headers = data[0]
        users = {}
        for row in data[1:]:
            row = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, row))

            username = rec.get('username', '').strip()
            if not username:
                continue

            blocked_raw = rec.get('blocked', '').strip().upper()
            blocked = blocked_raw in ('TRUE', '1', 'YES', 'ДА')

            tabs_raw = rec.get('allowed_tabs', '').strip()
            if tabs_raw == 'all':
                allowed_tabs = ['all']
            elif tabs_raw:
                allowed_tabs = [t.strip() for t in tabs_raw.split(',') if t.strip()]
            else:
                allowed_tabs = []

            users[username] = {
                'password': rec.get('password_hash', '').strip(),
                'name': rec.get('name', '').strip(),
                'role': rec.get('role', '').strip(),
                'manager_binding': rec.get('manager_binding', '').strip() or None,
                'blocked': blocked,
                'allowed_tabs': allowed_tabs,
                'last_login': None,
            }
        return users
    except Exception as e:
        print(f"Не удалось прочитать лист Users: {e}")
        return None


def load_users_cached():
    global _users_cache
    now = datetime.now()
    if (_users_cache['time'] is None or
            (now - _users_cache['time']).total_seconds() > USERS_CACHE_TTL):
        _users_cache['data'] = load_users_from_gsheets()
        _users_cache['time'] = now
    return _users_cache['data']


def save_users_to_gsheets(users):
    try:
        worksheet = _get_worksheet(GSHEETS_USERS_WORKSHEET)

        rows = [USER_COLUMNS]
        for username, u in users.items():
            tabs = u.get('allowed_tabs', [])
            tabs_str = 'all' if 'all' in tabs else ','.join(tabs)

            rows.append([
                username,
                u.get('password', ''),
                u.get('name', ''),
                u.get('role', ''),
                u.get('manager_binding') or '',
                'TRUE' if u.get('blocked') else 'FALSE',
                tabs_str,
            ])

        worksheet.clear()
        worksheet.update(rows, value_input_option='RAW')
        _invalidate_users_cache()
        return True
    except Exception as e:
        print(f"Ошибка записи листа Users: {e}")
        return False


# === ИСТОРИЯ ВХОДОВ ===

def log_login(username, ip=None, user_agent=None, device_id=None,
              status='success', note=''):
    try:
        worksheet = _get_worksheet(GSHEETS_LOGIN_HISTORY_WORKSHEET)

        all_data = worksheet.get_all_values()
        if not all_data:
            worksheet.append_row(LOGIN_HISTORY_COLUMNS)

        entry = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            username or '',
            ip or 'unknown',
            user_agent or 'unknown',
            device_id or '',
            status,
            note,
        ]
        worksheet.append_row(entry, value_input_option='RAW')
        return True
    except Exception as e:
        print(f"Ошибка записи в LoginHistory: {e}")
        return False


def get_login_stats(username):
    try:
        worksheet = _get_worksheet(GSHEETS_LOGIN_HISTORY_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return {'last_login': None, 'count_30d': 0, 'last_ip': None,
                    'last_device': None, 'last_status': None}

        headers = data[0]
        rows = data[1:]

        user_rows = []
        for row in rows:
            row = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, row))
            if rec.get('username', '').strip() == username:
                user_rows.append(rec)

        if not user_rows:
            return {'last_login': None, 'count_30d': 0, 'last_ip': None,
                    'last_device': None, 'last_status': None}

        user_rows.sort(key=lambda r: r.get('time', ''), reverse=True)
        last = user_rows[0]

        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        count_30d = sum(1 for r in user_rows if r.get('time', '') >= cutoff)

        return {
            'last_login': last.get('time'),
            'count_30d': count_30d,
            'last_ip': last.get('ip'),
            'last_device': last.get('user_agent'),
            'last_status': last.get('status'),
        }
    except Exception as e:
        print(f"Ошибка чтения LoginHistory: {e}")
        return {'last_login': None, 'count_30d': 0, 'last_ip': None,
                'last_device': None, 'last_status': None}


def get_recent_logins(limit=50):
    try:
        worksheet = _get_worksheet(GSHEETS_LOGIN_HISTORY_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame(columns=LOGIN_HISTORY_COLUMNS)

        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        if 'time' in df.columns:
            df = df.sort_values('time', ascending=False).head(limit)
        return df
    except Exception as e:
        print(f"Ошибка чтения LoginHistory: {e}")
        return pd.DataFrame(columns=LOGIN_HISTORY_COLUMNS)


# === НАСТРОЙКИ БОНУСОВ И ADMIN_SETTINGS ===

def get_bonus_settings():
    try:
        worksheet = _get_worksheet(GSHEETS_BONUS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return dict(DEFAULT_BONUS_SETTINGS)

        for row in data[1:]:
            if len(row) >= 2 and row[0].strip() == 'settings':
                try:
                    settings = json.loads(row[1])
                    result = dict(DEFAULT_BONUS_SETTINGS)
                    result.update(settings)
                    return result
                except json.JSONDecodeError:
                    print("Не удалось распарсить JSON настроек бонусов")
                    return dict(DEFAULT_BONUS_SETTINGS)

        return dict(DEFAULT_BONUS_SETTINGS)
    except Exception as e:
        print(f"Ошибка чтения BonusSettings: {e}")
        return dict(DEFAULT_BONUS_SETTINGS)


def save_bonus_settings(settings):
    try:
        worksheet = _get_worksheet(GSHEETS_BONUS_WORKSHEET)
        data = worksheet.get_all_values()

        if not data:
            worksheet.append_row(BONUS_COLUMNS)

        json_str = json.dumps(settings, ensure_ascii=False)

        found_row = None
        for i, row in enumerate(data):
            if len(row) >= 1 and row[0].strip() == 'settings':
                found_row = i + 1
                break

        if found_row:
            worksheet.update(f'B{found_row}', [[json_str]], value_input_option='RAW')
        else:
            worksheet.append_row(['settings', json_str], value_input_option='RAW')

        return True
    except Exception as e:
        print(f"Ошибка сохранения BonusSettings: {e}")
        return False


def get_admin_settings():
    """Читает admin_settings из BonusSettings (строка 'admin_settings')."""
    try:
        worksheet = _get_worksheet(GSHEETS_BONUS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return dict(DEFAULT_ADMIN_SETTINGS)

        for row in data[1:]:
            if len(row) >= 2 and row[0].strip() == 'admin_settings':
                try:
                    settings = json.loads(row[1])
                    result = dict(DEFAULT_ADMIN_SETTINGS)
                    result.update(settings)
                    return result
                except json.JSONDecodeError:
                    print("Не удалось распарсить admin_settings")
                    return dict(DEFAULT_ADMIN_SETTINGS)

        return dict(DEFAULT_ADMIN_SETTINGS)
    except Exception as e:
        print(f"Ошибка чтения admin_settings: {e}")
        return dict(DEFAULT_ADMIN_SETTINGS)


def save_admin_settings(settings):
    """Сохраняет admin_settings в BonusSettings (строка 'admin_settings')."""
    try:
        worksheet = _get_worksheet(GSHEETS_BONUS_WORKSHEET)
        data = worksheet.get_all_values()

        if not data:
            worksheet.append_row(BONUS_COLUMNS)

        json_str = json.dumps(settings, ensure_ascii=False)

        found_row = None
        for i, row in enumerate(data):
            if len(row) >= 1 and row[0].strip() == 'admin_settings':
                found_row = i + 1
                break

        if found_row:
            worksheet.update(f'B{found_row}', [[json_str]], value_input_option='RAW')
        else:
            worksheet.append_row(['admin_settings', json_str], value_input_option='RAW')

        _invalidate_summary_cache()
        return True
    except Exception as e:
        print(f"Ошибка сохранения admin_settings: {e}")
        return False


# === COMPANY FLAGS ===

def load_company_flags():
    """
    Читает лист CompanyFlags.
    Возвращает dict {company_code: {...}}.
    """
    try:
        worksheet = _get_worksheet(GSHEETS_COMPANY_FLAGS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return {}

        headers = data[0]
        flags = {}
        for row in data[1:]:
            row = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, row))

            code = rec.get('company_code', '').strip()
            if not code:
                continue

            blacklist = rec.get('blacklist', '').strip().upper() in ('TRUE', '1', 'YES', 'ДА')
            golden_fund = rec.get('golden_fund', '').strip().upper() in ('TRUE', '1', 'YES', 'ДА')

            flags[code] = {
                'company_name': rec.get('company_name', '').strip(),
                'blacklist': blacklist,
                'golden_fund': golden_fund,
                'status': rec.get('status', '').strip(),
                'status_date': rec.get('status_date', '').strip(),
                'date_added': rec.get('date_added', '').strip(),
                'added_by': rec.get('added_by', '').strip(),
            }
        return flags
    except Exception as e:
        print(f"Ошибка чтения CompanyFlags: {e}")
        return {}


def save_company_flags(flags):
    """Перезаписывает лист CompanyFlags."""
    try:
        worksheet = _get_worksheet(GSHEETS_COMPANY_FLAGS_WORKSHEET)

        rows = [COMPANY_FLAGS_COLUMNS]
        for code, f in flags.items():
            rows.append([
                code,
                f.get('company_name', ''),
                'TRUE' if f.get('blacklist') else 'FALSE',
                'TRUE' if f.get('golden_fund') else 'FALSE',
                f.get('status', ''),
                f.get('status_date', ''),
                f.get('date_added', ''),
                f.get('added_by', ''),
            ])

        worksheet.clear()
        worksheet.update(rows, value_input_option='RAW')
        _invalidate_summary_cache()
        return True
    except Exception as e:
        print(f"Ошибка записи CompanyFlags: {e}")
        return False


# === TRUST LIMITS ===

def load_trust_limits():
    """
    Читает лист TrustLimits.
    Возвращает dict {'threshold_1': 5000, 'threshold_2': 7000, 'threshold_3': 10000}.
    """
    try:
        worksheet = _get_worksheet(GSHEETS_TRUST_LIMITS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return dict(DEFAULT_TRUST_LIMITS)

        headers = data[0]
        limits = dict(DEFAULT_TRUST_LIMITS)
        for row in data[1:]:
            row = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, row))

            key = rec.get('threshold', '').strip()
            if not key:
                continue

            try:
                amount = float(str(rec.get('amount', '0')).replace(',', '.').replace(' ', ''))
                limits[key] = amount
            except (ValueError, TypeError):
                pass

        return limits
    except Exception as e:
        print(f"Ошибка чтения TrustLimits: {e}")
        return dict(DEFAULT_TRUST_LIMITS)


def save_trust_limits(limits):
    """Перезаписывает лист TrustLimits."""
    try:
        worksheet = _get_worksheet(GSHEETS_TRUST_LIMITS_WORKSHEET)

        rows = [TRUST_LIMITS_COLUMNS]
        for key in ['threshold_1', 'threshold_2', 'threshold_3']:
            rows.append([key, limits.get(key, 0.0)])

        worksheet.clear()
        worksheet.update(rows, value_input_option='RAW')
        _invalidate_summary_cache()
        return True
    except Exception as e:
        print(f"Ошибка записи TrustLimits: {e}")
        return False


# === ОБРАБОТКА ДАННЫХ ===

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
    df = load_from_gsheets()
    from_gsheets = df is not None

    if not from_gsheets:
        print("Google Sheets недоступен — пробую локальный Excel...")
        try:
            df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, header=0)
            print(f"Загружено из Excel: {len(df)} строк")
        except Exception as e:
            print(f"Ошибка загрузки Excel: {e}")
            return None

    return process_data(df, from_gsheets=from_gsheets)


def process_data(df, from_gsheets=False):
    column_mapping = {
        'Код хоз-ва': 'company_code',      # ← НОВОЕ
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

    required_cols = ['company_code', 'company', 'manager', 'invoice_num', 'invoice_date',
                     'invoice_amount', 'payment_amount', 'order_type']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Отсутствуют критичные колонки: {missing_cols}")
        return None

    df['invoice_date'] = pd.to_datetime(df['invoice_date'], errors='coerce')
    df['payment_date'] = pd.to_datetime(df['payment_date'], errors='coerce')
    df['invoice_amount'] = pd.to_numeric(df['invoice_amount'], errors='coerce').fillna(0)
    df['payment_amount'] = pd.to_numeric(df['payment_amount'], errors='coerce').fillna(0)
    df['order_type'] = pd.to_numeric(df['order_type'], errors='coerce').fillna(-1).astype(int)

    before = len(df)
    df = df[df['manager'].isin(ALL_MANAGERS)].copy()
    after = len(df)
    if before != after:
        print(f"Отсеяно служебных строк: {before - after}")

    data_end = find_data_end(df)
    print(f"Граница данных: строка {data_end + 2}")
    df = df.iloc[:data_end + 1].copy()

    comments_by_index = {}

    if from_gsheets and 'payment_parts' in df.columns:
        for idx, row in df.iterrows():
            text = row.get('payment_parts', '')
            if pd.notna(text) and str(text).strip():
                parts = parse_comment(str(text))
                if parts:
                    comments_by_index[idx] = parts
        print(f"Примечаний из Google Sheets: {len(comments_by_index)}")
    elif _COMMENTS_AVAILABLE:
        try:
            raw = load_comments()
            comments_by_index = {int(k) - 2: v for k, v in raw.items()}
            print(f"Примечаний из Excel: {len(comments_by_index)}")
        except Exception as e:
            print(f"Не удалось прочитать примечания: {e}")

    if 'payment_parts' in df.columns:
        df = df.drop(columns=['payment_parts'])

    sales_df = df.copy()
    sales_df['row_type'] = 'sale'

    payment_rows = []
    for idx, row in df.iterrows():
        total_payment = row['payment_amount']
        if total_payment == 0 and pd.isna(row['payment_num']):
            continue

        parts = comments_by_index.get(idx, [])

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

    # company_code — первым
    keep_cols = ['company_code', 'company', 'oblast', 'raion', 'manager', 'research_type',
                 'invoice_num', 'invoice_date', 'invoice_amount',
                 'payment_amount', 'payment_date', 'order_type', 'row_type']
    combined = combined[keep_cols].copy()

    sales_only = combined[combined['row_type'] == 'sale']
    total_sales = float(sales_only[sales_only['order_type'] == 0]['invoice_amount'].sum())
    total_prepayments = float(sales_only[sales_only['order_type'] == 1]['invoice_amount'].sum())

    payments_only = combined[combined['row_type'] == 'payment']
    total_returns = float(payments_only['payment_amount'].sum())

    print(f"Строк 'sale': {len(sales_df)}, 'payment': {len(payments_df)}")

    return {
        'df': combined,
        'database': load_database(),
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
    return float(df_sales[df_sales['order_type'] == 0]['invoice_amount'].sum())


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
    return int(df_sales[df_sales['order_type'] == 0]['company'].nunique())


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
        return pd.DataFrame(columns=['company_code', 'company', 'raion', 'oblast', 'manager', 'amount'])
    sales = df_sales[df_sales['order_type'] == 0]
    if sales.empty:
        return pd.DataFrame(columns=['company_code', 'company', 'raion', 'oblast', 'manager', 'amount'])
    result = sales.groupby(['company_code', 'company', 'raion', 'oblast', 'manager'])['invoice_amount'].sum().reset_index()
    result.columns = ['company_code', 'company', 'raion', 'oblast', 'manager', 'amount']
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

    sales_grouped = sales.groupby(['company_code', 'company', 'manager', 'raion', 'oblast',
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

    result = debt_df.groupby(['company_code', 'company', 'manager']).agg({
        'debt_amount': 'sum'
    }).reset_index()
    result.columns = ['company_code', 'company', 'manager', 'total_debt']

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


def calc_threshold_bonus(total_amount, thresholds):
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

    if use_cat:
        payments['bonus_category'] = payments.apply(
            lambda r: r['payment_amount'] * rates_cat.get(r.get('category', ''), 0.0) / 100.0,
            axis=1
        )
    else:
        payments['bonus_category'] = 0.0

    result = payments.groupby('manager').agg({
        'payment_amount': 'sum',
        'bonus_category': 'sum',
        'company': 'count'
    }).reset_index()
    result.columns = ['manager', 'payments', 'bonus_category', 'count']

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
        index='manager', columns='category', values='amount', aggfunc='sum', fill_value=0
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

    result = payments.groupby(['company_code', 'company', 'manager', 'category']).agg({
        'payment_amount': 'sum',
        'bonus': 'sum'
    }).reset_index()

    pivot_amount = result.pivot_table(
        index=['company_code', 'company', 'manager'], columns='category', values='payment_amount',
        aggfunc='sum', fill_value=0
    ).reset_index()
    pivot_bonus = result.pivot_table(
        index=['company_code', 'company', 'manager'], columns='category', values='bonus',
        aggfunc='sum', fill_value=0
    ).reset_index()

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    for cat in order:
        if cat not in pivot_amount.columns:
            pivot_amount[cat] = 0
        if cat not in pivot_bonus.columns:
            pivot_bonus[cat] = 0

    pivot_amount['total_payments'] = pivot_amount[order].sum(axis=1)
    pivot_bonus['total_bonus'] = pivot_bonus[order].sum(axis=1)

    merged = pivot_amount[['company_code', 'company', 'manager', 'total_payments'] + order].merge(
        pivot_bonus[['company_code', 'company', 'manager', 'total_bonus']],
        on=['company_code', 'company', 'manager'], how='left'
    )
    return merged.sort_values('total_payments', ascending=False)


# === СОВМЕСТИМОСТЬ ===

def get_available_months(df):
    return get_period_options(df)


def get_available_managers(df=None):
    return ACTIVE_MANAGERS


def filter_by_period(df, period_selection, manager):
    return filter_sales(df, period_selection, manager)


def get_bonus_rates():
    return get_bonus_settings().get('rates_by_category', {})


def save_bonus_rates(rates):
    settings = get_bonus_settings()
    settings['rates_by_category'] = rates
    save_bonus_settings(settings)


# === БАЗА ===

def load_database():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                db = json.load(f)
        except Exception:
            db = create_default_database()
    else:
        db = create_default_database()

    users = load_users_cached()
    if users is not None:
        db['users'] = users
    elif 'users' not in db:
        db['users'] = {}

    return db


def create_default_database():
    db = {
        "managers": {},
        "companies": {},
        "districts": {},
        "users": {},
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
    db_to_save = {k: v for k, v in db.items() if k != 'users'}
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db_to_save, f, ensure_ascii=False, indent=2)


# === АВТОРИЗАЦИЯ ===

def authenticate(username, password):
    db = load_database()
    users = db.get('users', {})
    if username not in users:
        return None
    user = users[username]
    if user.get('blocked', False):
        return {'username': username, **user, '_blocked': True}
    if verify_password(password, user.get('password', '')):
        return {'username': username, **user}
    return None


def create_user(username, name, role, manager_binding, allowed_tabs, password=None):
    users = load_users_from_gsheets() or {}
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
    if not save_users_to_gsheets(users):
        raise RuntimeError("Не удалось сохранить пользователя в Google Sheets")
    return password


def update_user(username, **kwargs):
    users = load_users_from_gsheets() or {}
    if username not in users:
        raise ValueError(f"Пользователь {username} не найден")

    user = users[username]

    if 'new_password' in kwargs:
        pwd = kwargs.pop('new_password')
        if pwd:
            user['password'] = hash_password(pwd)

    if 'blocked' in kwargs:
        if username == 'superadmin' and kwargs['blocked']:
            raise ValueError("Нельзя заблокировать суперадмина")
        user['blocked'] = kwargs.pop('blocked')

    if 'role' in kwargs:
        if username == 'superadmin' and kwargs['role'] != 'super_admin':
            raise ValueError("Нельзя изменить роль суперадмина")
        user['role'] = kwargs.pop('role')

    for key, value in kwargs.items():
        user[key] = value

    users[username] = user
    if not save_users_to_gsheets(users):
        raise RuntimeError("Не удалось сохранить изменения в Google Sheets")


def delete_user(username):
    if username == 'superadmin':
        raise ValueError("Нельзя удалить суперадмина")

    users = load_users_from_gsheets() or {}
    if username in users:
        del users[username]
        if not save_users_to_gsheets(users):
            raise RuntimeError("Не удалось удалить пользователя из Google Sheets")


# === УТИЛИТА: IP + User-Agent из Streamlit ===

def get_client_info():
    info = {'ip': 'unknown', 'user_agent': 'unknown'}
    try:
        import streamlit as st

        ctx = getattr(st, 'context', None)
        if ctx is None:
            return info

        try:
            ip = getattr(ctx, 'ip_address', None)
            if ip:
                info['ip'] = ip
        except Exception:
            pass

        if info['ip'] == 'unknown':
            try:
                headers = getattr(ctx, 'headers', None) or {}
                forwarded = headers.get("X-Forwarded-For", "")
                if forwarded:
                    info['ip'] = forwarded.split(",")[0].strip()
            except Exception:
                pass

        try:
            headers = getattr(ctx, 'headers', None) or {}
            ua = headers.get("User-Agent", "")
            if ua:
                info['user_agent'] = ua
        except Exception:
            pass
    except Exception:
        pass

    return info


# === РАСЧЁТ СТАТУСОВ И МЕТОК ПРЕДПРИЯТИЙ ===

def get_company_metrics(company_code, df_company, flags, admin_settings, trust_limits):
    """
    Вычисляет метрики одного предприятия.

    df_company — DataFrame со счетами/оплатами ТОЛЬКО этого предприятия.
    flags — dict с метками из CompanyFlags для этого кода.
    admin_settings — dict.
    trust_limits — dict {'threshold_1': 5000, ...}.

    Возвращает dict с метриками.
    """
    today = pd.Timestamp.now()

    # Только счета (order_type == 0)
    sales = df_company[
        (df_company['row_type'] == 'sale') &
        (df_company['order_type'] == 0)
    ].copy()

    # Оплаты
    payments = df_company[df_company['row_type'] == 'payment'].copy()

    result = {
        'company_code': company_code,
        'company_name': None,
        'manager': None,
        'oblast': None,
        'raion': None,
        'invoices_count': 0,
        'first_invoice_date': None,
        'last_invoice_date': None,
        'last_activity_date': None,
        'days_since_last': None,
        'debt_amount': 0.0,
        'debt_days_max': 0,
        'status': 'working',
        'metki': [],
        'category': 'working',
        'has_prepayment': False,
    }

    # Если нет счетов — «Пассивное» (или ручное «Потенциальное»)
    if sales.empty:
        if flags.get('status') == 'potential':
            result['status'] = 'potential'
            result['category'] = 'potential'
        else:
            result['status'] = 'passive'
            result['category'] = 'passive'
        return result

    # Основные поля
    # Компания — из первой строки
    first_row = sales.iloc[0]
    result['company_name'] = first_row.get('company')
    result['oblast'] = first_row.get('oblast')
    result['raion'] = first_row.get('raion')

    # Менеджер — из ПОСЛЕДНЕЙ записи (счёт ИЛИ предсчёт)
    all_entries = df_company[
        (df_company['row_type'] == 'sale') &
        (df_company['invoice_date'].notna())
    ].copy()
    if not all_entries.empty:
        all_entries_sorted = all_entries.sort_values('invoice_date', ascending=False)
        last_entry = all_entries_sorted.iloc[0]
        result['manager'] = last_entry.get('manager')
        result['last_activity_date'] = last_entry.get('invoice_date')
    else:
        result['manager'] = first_row.get('manager')
        result['last_activity_date'] = None

    invoice_dates = sales['invoice_date'].dropna().sort_values()
    if len(invoice_dates) > 0:
        result['first_invoice_date'] = invoice_dates.iloc[0]
        result['last_invoice_date'] = invoice_dates.iloc[-1]
        result['days_since_last'] = (today - invoice_dates.iloc[-1]).days
        result['invoices_count'] = len(invoice_dates)

    # === РАСЧЁТ ДЕБИТОРКИ ===
    # Группируем счета по invoice_num
    sales_grouped = sales.groupby('invoice_num').agg({
        'invoice_amount': 'sum',
        'invoice_date': 'max',
    }).reset_index()

    # Группируем оплаты по invoice_num
    if not payments.empty:
        pay_grouped = payments.groupby('invoice_num')['payment_amount'].sum().reset_index()
        pay_grouped.columns = ['invoice_num', 'paid_amount']
        merged = sales_grouped.merge(pay_grouped, on='invoice_num', how='left').fillna({'paid_amount': 0})
    else:
        merged = sales_grouped.copy()
        merged['paid_amount'] = 0.0

    merged['debt'] = merged['invoice_amount'] - merged['paid_amount']
    unpaid = merged[merged['debt'] > 0.5].copy()

    if not unpaid.empty:
        result['debt_amount'] = float(unpaid['debt'].sum())
        unpaid['days'] = unpaid['invoice_date'].apply(
            lambda d: (today - d).days if pd.notna(d) else 0
        )
        result['debt_days_max'] = int(unpaid['days'].max())

    # === ПРЕДСЧЁТ ===
    prepayments = df_company[
        (df_company['row_type'] == 'sale') &
        (df_company['order_type'] == 1) &
        (df_company['invoice_date'].notna())
    ]
    if not prepayments.empty:
        last_prepayment_date = prepayments['invoice_date'].max()
        days_since_prepayment = (today - last_prepayment_date).days
        active_days = admin_settings.get('prepayment_active_days', 30)
        if days_since_prepayment <= active_days:
            result['has_prepayment'] = True

    # === СТАТУС ===
    result['status'] = calculate_company_status(
        invoice_dates=invoice_dates,
        flags=flags,
        admin_settings=admin_settings,
        today=today,
    )

    # === МЕТКИ ===
    result['metki'] = calculate_company_metki(
        result=result,
        flags=flags,
        admin_settings=admin_settings,
        trust_limits=trust_limits,
    )

    # === КАТЕГОРИЯ (для круговой) ===
    result['category'] = get_priority_category(result, flags)

    return result


def calculate_company_status(invoice_dates, flags, admin_settings, today):
    """
    Вычисляет статус предприятия.

    Приоритет:
    1. potential (ручной)
    2. new — 1 счёт И первый счёт в текущем календарном месяце
    3. returned — есть счёт в текущем месяце + перерыв >= returned_days
    4. passive — нет счетов > passive_days
    5. working — всё остальное
    """
    if flags.get('status') == 'potential':
        return 'potential'

    if len(invoice_dates) == 0:
        return 'passive'

    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    first_invoice = invoice_dates.iloc[0]
    last_invoice = invoice_dates.iloc[-1]
    days_since_last = (today - last_invoice).days

    # === НОВОЕ ===
    if len(invoice_dates) == 1:
        if first_invoice >= current_month_start:
            return 'new'
        if days_since_last > admin_settings.get('passive_days', 300):
            return 'passive'
        return 'working'

    # === ВЕРНУВШЕЕСЯ ===
    has_invoice_current_month = any(d >= current_month_start for d in invoice_dates)
    if has_invoice_current_month:
        gaps = invoice_dates.diff().dt.days.dropna()
        if len(gaps) > 0 and gaps.max() >= admin_settings.get('returned_days', 300):
            return 'returned'

    # === ПАССИВНОЕ ===
    if days_since_last > admin_settings.get('passive_days', 300):
        return 'passive'

    return 'working'


def calculate_company_metki(result, flags, admin_settings, trust_limits):
    """
    Возвращает список меток для предприятия.
    result — dict с метриками из get_company_metrics.
    """
    metki = []

    # 1. ЧС — исключение
    if flags.get('blacklist'):
        return ['💀']

    # 2. Золотой фонд
    if flags.get('golden_fund'):
        metki.append('🏆')

    # 3. Дебиторка / Должник
    debt = result.get('debt_amount', 0.0)
    debt_days = result.get('debt_days_max', 0)
    debtor_threshold_key = f"threshold_{admin_settings.get('debtor_threshold', 2)}"
    debtor_threshold_value = trust_limits.get(debtor_threshold_key, 7000.0)

    if debt > 0.5:
        if debt_days > admin_settings.get('debtor_days', 90) or debt >= debtor_threshold_value:
            metki.append('💸')  # Должник
        else:
            metki.append('💰')  # Дебиторка

    # 4. Нет заявок — только если НЕТ дебиторки вообще
    days_since_last = result.get('days_since_last')

    if days_since_last is not None:
        # ⏰ ставим только если дебиторка = 0 (нет долга)
        if days_since_last > admin_settings.get('inactive_days', 60) and debt < 0.5:
            metki.append('⏰')

    return metki


def get_priority_category(result, flags):
    """
    Приоритетная категория для круговой диаграммы.
    """
    metki = result.get('metki', [])
    status = result.get('status', 'working')

    if '💀' in metki:
        return 'blacklist'
    if '🏆' in metki:
        return 'golden_fund'
    if status == 'new':
        return 'new'
    if status == 'returned':
        return 'returned'
    if status == 'potential':
        return 'potential'
    if '💸' in metki:
        return 'debtor'
    if '💰' in metki:
        return 'debitorka'
    if '⏰' in metki:
        return 'inactive'
    if status == 'passive':
        return 'passive'
    return 'working'


def get_all_companies_summary(df, flags=None, admin_settings=None, trust_limits=None):
    """
    Считает метрики для ВСЕХ предприятий.
    Возвращает dict {company_code: metrics_dict}.
    """
    if flags is None:
        flags = load_company_flags()
    if admin_settings is None:
        admin_settings = get_admin_settings()
    if trust_limits is None:
        trust_limits = load_trust_limits()

    if df is None or df.empty:
        return {}

    summary = {}

    # Группируем по company_code
    grouped = df.groupby('company_code')

    for code, df_company in grouped:
        code_str = str(code).strip()
        if not code_str or code_str == 'nan':
            continue

        company_flags = flags.get(code_str, {})

        metrics = get_company_metrics(
            company_code=code_str,
            df_company=df_company,
            flags=company_flags,
            admin_settings=admin_settings,
            trust_limits=trust_limits,
        )
        summary[code_str] = metrics

    return summary


def get_summary_cached(df, force=False, flags=None, admin_settings=None, trust_limits=None):
    """
    Возвращает summary с кэшем (TTL 5 минут).
    Сбрасывается при save_company_flags / save_trust_limits / save_admin_settings.
    """
    global _summary_cache
    now = datetime.now()
    
    if (force or 
            _summary_cache['data'] is None or 
            _summary_cache['time'] is None or
            (now - _summary_cache['time']).total_seconds() > SUMMARY_TTL):
        _summary_cache['data'] = get_all_companies_summary(
            df, flags, admin_settings, trust_limits
        )
        _summary_cache['time'] = now
    
    return _summary_cache['data']


CATEGORY_LABELS = {
    'blacklist': '💀 Чёрный список',
    'golden_fund': '🏆 Золотой фонд',
    'new': '🆕 Новое',
    'returned': '🔄 Вернувшееся',
    'potential': '🤝 Потенциальное',
    'debtor': '💸 Должник',
    'debitorka': '💰 Дебиторка',
    'inactive': '⏰ Нет заявок',
    'working': '✅ Рабочее',
    'passive': '😴 Пассивное',
}

CATEGORY_ORDER = [
    'blacklist', 'golden_fund', 'new', 'returned', 'potential',
    'debtor', 'debitorka', 'inactive', 'working', 'passive',
]


def get_companies_by_category(summary, manager_filter=None):
    """
    Группирует предприятия по приоритетной категории.
    Возвращает dict {category: [list of company_codes]}.
    """
    result = {cat: [] for cat in CATEGORY_ORDER}

    for code, metrics in summary.items():
        # Фильтр по менеджеру
        if manager_filter and manager_filter != 'Все менеджеры':
            if metrics.get('manager') != manager_filter:
                continue

        cat = metrics.get('category', 'working')
        if cat in result:
            result[cat].append(code)
        else:
            result['working'].append(code)

    return result


def get_companies_with_metki_df(summary, manager_filter=None):
    """
    Возвращает DataFrame со всеми предприятиями и их метками.
    """
    if not summary:
        return pd.DataFrame()

    rows = []
    for code, m in summary.items():
        if manager_filter and manager_filter != 'Все менеджеры':
            if m.get('manager') != manager_filter:
                continue

        # Расшифровка меток
        METKI_LABELS = {
            '💀': '💀 ЧС',
            '🏆': '🏆 Золото',
            '🆕': '🆕 Новое',
            '🔄': '🔄 Вернувшееся',
            '🤝': '🤝 Потенциальное',
            '💸': '💸 Должник',
            '💰': '💰 Дебиторка',
            '⏰': '⏰ Нет заявок',
        }
        metki_raw = m.get('metki', [])
        metki_str = ' • '.join(METKI_LABELS.get(emoji, emoji) for emoji in metki_raw)
        rows.append({
            'company_code': code,
            'company_name': m.get('company_name') or '',
            'oblast': m.get('oblast') or '',
            'raion': m.get('raion') or '',
            'manager': m.get('manager') or '',
            'debt_amount': m.get('debt_amount', 0.0),
            'debt_days_max': m.get('debt_days_max', 0),
            'status': m.get('status', ''),
            'category': m.get('category', ''),
            'metki': metki_str,
            'last_invoice_date': m.get('last_invoice_date'),
            'days_since_last': m.get('days_since_last'),
        })

    df_res = pd.DataFrame(rows)
    if not df_res.empty:
        df_res = df_res.sort_values('debt_amount', ascending=False)
    return df_res


# === ЗАГРУЗКА ВСЕГО ===


# === ЗАГРУЗКА ВСЕГО ===

def load_all_data(force_refresh=False):
    global _last_load, _cached_data

    if force_refresh or _cached_data is None or (datetime.now() - _last_load).seconds > CACHE_DURATION:
        excel_data = load_excel_data()
        if excel_data:
            excel_data['database'] = load_database()
            _cached_data = excel_data
            _last_load = datetime.now()

    return _cached_data