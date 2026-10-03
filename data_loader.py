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
    # Разрешения для админов (открывает/закрывает суперадмин)
    'allow_admins_blacklist': True,
    'allow_admins_golden': True,
    'allow_admins_potential_days': True,
    'allow_admins_trust_limits': True,
    'allow_admins_status_days': True,      # ← НОВОЕ: менять сроки статусов
    'allow_admins_inactive_days': True,    # ← НОВОЕ: менять срок ⏰
    'allow_admins_bonus_settings': True,
    'allow_admins_plans_edit': True,

    # Видимость
    'show_trust_limits': True,

    # Сроки статусов
    'working_days': 60,        # ≤ 60 → Актив
    'passive_days': 120,       # 61–120 → Пассив
    'lost_days': 120,          # > 120 → Потери
    'returned_days': 120,      # разрыв > 120 → Камбэки
    'new_status_days': 30,     # срок «Новое» (для совместимости)

    # Сроки меток
    'inactive_days': 30,       # > 30 → ⏰ Нет заявок
    'potential_warning_days': 90,

    # Дебиторка и предсчёт
    'debtor_days': 90,
    'debtor_threshold': 2,
    'prepayment_active_days': 30,
}

DEFAULT_TRUST_LIMITS = {
    'threshold_1': 5000.0,
    'threshold_2': 7000.0,
    'threshold_3': 10000.0,
}

# === ПЛАНЫ ===

PLAN_CATEGORIES = [
    # (key, label, unit)
    ('sales',          '💰 Продажи',          'BYN'),
    ('payments',       '💵 Оплаты',           'BYN'),
    ('new_companies',  '🆕 Новые предприятия', 'шт.'),
    ('pcr',            '🔬 ПЦР',              'BYN'),
    ('ifa',            '🔬 ИФА',              'BYN'),
    ('biochem',        '🔬 Биохимия',         'BYN'),
    ('microbio',       '🔬 Микробиология',    'BYN'),
    ('pcr_mastitis',   '🔬 ПЦР маститы',      'BYN'),
    ('oak',            '🔬 ОАК',              'BYN'),
    ('urine',          '🔬 Моча',             'BYN'),
    ('avg_check',      '📈 Средний чек',      'BYN'),
    ('companies_count','🏢 Отработано хозяйств', 'шт.'),
]

DEFAULT_PLANS_SETTINGS = {
    'allow_admins_plans_edit': True,
    'enabled_plans': [key for key, _, _ in PLAN_CATEGORIES],
    'plans': {key: 0.0 for key, _, _ in PLAN_CATEGORIES},
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
GSHEETS_REGIONS_WORKSHEET = "Regions"
GSHEETS_PLANS_WORKSHEET = "Plans"

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


def set_company_potential(code, manager_binding, added_by='system'):
    """
    Устанавливает статус «Потенциальный» для предприятия.
    Проверяет, что предприятие НЕ в ЧС.
    """
    flags = load_company_flags() or {}
    code_str = str(code).strip()

    if code_str in flags and flags[code_str].get('blacklist'):
        raise ValueError("Предприятие в ЧС — статус «Потенциальный» недоступен")

    entry = flags.get(code_str, {})
    entry['company_name'] = entry.get('company_name', '')
    entry['blacklist'] = entry.get('blacklist', False)
    entry['golden_fund'] = entry.get('golden_fund', False)
    entry['status'] = 'potential'
    entry['status_date'] = datetime.now().strftime('%Y-%m-%d')
    entry['added_by'] = added_by
    entry['date_added'] = entry.get('date_added') or datetime.now().strftime('%Y-%m-%d')

    flags[code_str] = entry
    return save_company_flags(flags)


def remove_company_potential(code):
    """Снимает статус «Потенциальный» у предприятия."""
    flags = load_company_flags() or {}
    code_str = str(code).strip()

    if code_str not in flags:
        return True

    flags[code_str]['status'] = ''
    flags[code_str]['status_date'] = ''
    return save_company_flags(flags)


def get_potential_days(status_date_str):
    """Возвращает количество дней с даты постановки статуса."""
    if not status_date_str:
        return 0
    try:
        status_date = datetime.strptime(status_date_str, '%Y-%m-%d')
        return (datetime.now() - status_date).days
    except (ValueError, TypeError):
        return 0


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


def load_regions():
    """
    Читает Google Sheets-лист 'Regions'.
    Возвращает dict {company_code: [list of branches]}.

    Каждое предприятие может иметь несколько филиалов (например, ООО ВетКультура).
    """
    try:
        worksheet = _get_worksheet(GSHEETS_REGIONS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return {}

        headers = data[0]
        regions = {}
        for row in data[1:]:
            row = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, row))

            code = rec.get('Код \nхоз-ва', '').strip() or rec.get('Код хоз-ва', '').strip()
            if not code:
                continue

            primary = rec.get('Основной \nМенеджер', '').strip() or rec.get('Основной Менеджер', '').strip()

            # Парсим JSONL из колонки «Адрес»
            address_raw = rec.get('Адрес', '').strip()
            enterprise_json = parse_enterprise_json(address_raw)

            # Извлекаем координаты из JSONL или из колонок
            admin = enterprise_json.get('administration', {}) or {}
            lat = admin.get('latitude') or rec.get('Широта', '').strip() or None
            lon = admin.get('longitude') or rec.get('Долгота', '').strip() or None
            distance_val = admin.get('distance_from_start_km') or rec.get('Расстояние', '').strip() or None

            # Животные
            livestock_summary = enterprise_json.get('livestock_summary', {}) or {}
            animal_type = rec.get('Вид животных', '').strip() or None
            livestock_raw = rec.get('Поголовье', '').strip() or None

            # Площадки
            production_sites = enterprise_json.get('production_sites', []) or []
            production_sites_count = enterprise_json.get('production_sites_count', 0) or 0

            # Контакты
            contacts = enterprise_json.get('contacts', {}) or {}

            # Финансовая стабильность
            stability_raw = rec.get('Статус', '').strip()
            try:
                stability = int(float(stability_raw)) if stability_raw else None
            except (ValueError, TypeError):
                stability = None

            branch = {
                'code': code,
                'name': rec.get('Наименование хозяйства', '').strip(),
                'oblast': rec.get('Область', '').strip(),
                'raion': rec.get('Район', '').strip(),
                'primary_manager': primary,
                'substitute_manager': rec.get('Подмена', '').strip() or None,
                'latitude': lat,
                'longitude': lon,
                'address': address_raw or None,
                'office_coords': rec.get('Координаты офиса', '').strip() or None,
                'distance': distance_val,
                # Животные
                'animal_type': animal_type,
                'livestock_raw': livestock_raw,
                'total_animals': livestock_summary.get('total_animals', 0),
                'milking_cows': livestock_summary.get('milking_cows', 0),
                'pigs_count': livestock_summary.get('pigs_count', 0),
                'poultry': livestock_summary.get('poultry', {}),
                # Площадки
                'production_sites_count': production_sites_count,
                'production_sites': production_sites,
                # Контакты
                'contacts': contacts,
                # Финансы
                'stability': stability,
                # Полный JSONL (для карточки)
                'enterprise_json': enterprise_json,
            }

            regions.setdefault(code, []).append(branch)

        return regions
    except Exception as e:
        print(f"Ошибка чтения Regions: {e}")
        return {}


def parse_enterprise_json(json_str):
    """
    Парсит JSONL-строку из колонки «Адрес».
    Возвращает dict или пустой dict при ошибке.
    """
    if not json_str or not isinstance(json_str, str):
        return {}

    s = json_str.strip()
    if not s or s.lower() in ('nan', 'none', 'null'):
        return {}

    try:
        data = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def load_region_managers():
    """
    Читает Google Sheets-лист 'Regions'.
    Возвращает dict {raion: primary_manager} — закрепление районов за менеджерами.
    Только строки без кода предприятия.
    """
    try:
        worksheet = _get_worksheet(GSHEETS_REGIONS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return {}

        headers = data[0]
        result = {}
        for row in data[1:]:
            row = row + [''] * (len(headers) - len(row))
            rec = dict(zip(headers, row))

            code = rec.get('Код \nхоз-ва', '').strip() or rec.get('Код хоз-ва', '').strip()
            if code:
                continue  # пропускаем строки с кодом

            raion = rec.get('Район', '').strip()
            if not raion:
                continue

            primary = rec.get('Основной \nМенеджер', '').strip() or rec.get('Основной Менеджер', '').strip()
            if not primary:
                continue

            result[raion] = primary

        return result
    except Exception as e:
        print(f"Ошибка чтения RegionManagers: {e}")
        return {}


def get_plans_settings():
    """
    Читает настройки планов из Google Sheets-листа 'Plans'.
    Возвращает dict.
    """
    try:
        worksheet = _get_worksheet(GSHEETS_PLANS_WORKSHEET)
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return dict(DEFAULT_PLANS_SETTINGS)

        for row in data[1:]:
            if len(row) >= 2 and row[0].strip() == 'plans':
                try:
                    settings = json.loads(row[1])
                    result = dict(DEFAULT_PLANS_SETTINGS)
                    result.update(settings)
                    # Мержим plans отдельно
                    if 'plans' in settings:
                        merged_plans = dict(DEFAULT_PLANS_SETTINGS['plans'])
                        merged_plans.update(settings['plans'])
                        result['plans'] = merged_plans
                    return result
                except json.JSONDecodeError:
                    print("Не удалось распарсить plans")
                    return dict(DEFAULT_PLANS_SETTINGS)

        return dict(DEFAULT_PLANS_SETTINGS)
    except Exception as e:
        print(f"Ошибка чтения Plans: {e}")
        return dict(DEFAULT_PLANS_SETTINGS)


def save_plans_settings(settings):
    """
    Сохраняет настройки планов в Google Sheets-лист 'Plans'.
    Создаёт лист, если его нет.
    """
    try:
        # Проверяем наличие листа, создаём если нет
        try:
            worksheet = _get_worksheet(GSHEETS_PLANS_WORKSHEET)
        except Exception:
            sh = _get_spreadsheet()
            worksheet = sh.add_worksheet(
                title=GSHEETS_PLANS_WORKSHEET,
                rows=10,
                cols=2
            )
            worksheet.append_row(['key', 'value'])
            # Сбрасываем кэш
            global _worksheets_cache
            _worksheets_cache[GSHEETS_PLANS_WORKSHEET] = worksheet

        data = worksheet.get_all_values()
        if not data:
            worksheet.append_row(['key', 'value'])

        json_str = json.dumps(settings, ensure_ascii=False)

        found_row = None
        for i, row in enumerate(data):
            if len(row) >= 1 and row[0].strip() == 'plans':
                found_row = i + 1
                break

        if found_row:
            worksheet.update(f'B{found_row}', [[json_str]], value_input_option='RAW')
        else:
            worksheet.append_row(['plans', json_str], value_input_option='RAW')

        return True
    except Exception as e:
        print(f"Ошибка сохранения Plans: {e}")
        return False


def calculate_plan_fact(df, summary, manager_filter=None, month_year=None):
    """
    Считает факт по всем категориям планов за указанный месяц.

    df — полный DataFrame (для продаж, оплат, исследований)
    summary — summary (для новых предприятий)
    manager_filter — менеджер (из сайдбара)
    month_year — (год, месяц). Если None — текущий.

    Возвращает dict: {key: value, ...}
    """
    if df is None or df.empty:
        return {key: 0.0 for key, _, _ in PLAN_CATEGORIES}

    today = datetime.now()
    if month_year:
        year, month = month_year
    else:
        year, month = today.year, today.month

    # Фильтр по месяцу
    df_month = df.copy()
    df_month['_year'] = df_month['invoice_date'].dt.year
    df_month['_month'] = df_month['invoice_date'].dt.month

    # Фильтр по менеджеру (для продаж — по manager заявки)
    def _filter_mgr(data, mgr_col='manager'):
        if manager_filter and manager_filter != 'Все менеджеры':
            return data[data[mgr_col] == manager_filter]
        return data

    # === ПРОДАЖИ ===
    sales = df_month[
        (df_month['row_type'] == 'sale') &
        (df_month['order_type'] == 0) &
        (df_month['_year'] == year) &
        (df_month['_month'] == month)
    ]
    sales = _filter_mgr(sales)
    sales_sum = float(sales['invoice_amount'].sum())

    # === ОПЛАТЫ ===
    payments = df_month[
        (df_month['row_type'] == 'payment') &
        (df_month['payment_date'].dt.year == year) &
        (df_month['payment_date'].dt.month == month)
    ]
    payments = _filter_mgr(payments)
    payments_sum = float(payments['payment_amount'].sum())

    # === НОВЫЕ ПРЕДПРИЯТИЯ ===
    # Первый счёт за всё время — в текущем месяце
    new_companies = 0
    for code, m in summary.items():
        first_date = m.get('first_invoice_date')
        if first_date is None:
            continue
        if hasattr(first_date, 'year'):
            if first_date.year == year and first_date.month == month:
                if manager_filter and manager_filter != 'Все менеджеры':
                    if m.get('manager') != manager_filter:
                        continue
                new_companies += 1

    # === ПО ВИДАМ ИССЛЕДОВАНИЙ ===
    def _research_sum(research_key):
        research_map = {
            'pcr': 'ПЦР',
            'ifa': 'ИФА',
            'biochem': 'Биохимия',
            'microbio': 'Микробиология',
            'pcr_mastitis': 'ПЦР маститы',
            'oak': 'ОАК',
            'urine': 'Моча',
        }
        target = research_map.get(research_key)
        if not target:
            return 0.0
        r = sales[sales['research_type'] == target]
        return float(r['invoice_amount'].sum())

    # === СРЕДНИЙ ЧЕК ===
    unique_invoices = sales[['company', 'invoice_num', 'invoice_date']].drop_duplicates()
    invoices_count = len(unique_invoices)
    avg_check = sales_sum / invoices_count if invoices_count > 0 else 0.0

    # === ОТРАБОТАННЫХ ХОЗЯЙСТВ ===
    companies_count = int(sales['company_code'].nunique()) if not sales.empty else 0

    return {
        'sales': sales_sum,
        'payments': payments_sum,
        'new_companies': new_companies,
        'pcr': _research_sum('pcr'),
        'ifa': _research_sum('ifa'),
        'biochem': _research_sum('biochem'),
        'microbio': _research_sum('microbio'),
        'pcr_mastitis': _research_sum('pcr_mastitis'),
        'oak': _research_sum('oak'),
        'urine': _research_sum('urine'),
        'avg_check': avg_check,
        'companies_count': companies_count,
    }


def get_plan_summary(df, summary, month_year=None):
    """
    Считает факт по всем менеджерам за указанный месяц.

    Возвращает DataFrame:
    Менеджер | sales | payments | new_companies | ... | avg_check | companies_count
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Список активных менеджеров
    active_managers = [m for m in ACTIVE_MANAGERS if m != 'Все менеджеры']

    rows = []
    for mgr in active_managers:
        fact = calculate_plan_fact(df, summary, manager_filter=mgr, month_year=month_year)
        fact['manager'] = mgr
        rows.append(fact)

    # Итоговая строка «Все менеджеры»
    total = calculate_plan_fact(df, summary, manager_filter='Все менеджеры', month_year=month_year)
    total['manager'] = 'Все менеджеры'
    rows.append(total)

    df_res = pd.DataFrame(rows)

    # Переставляем manager в начало
    cols = ['manager'] + [c for c in df_res.columns if c != 'manager']
    df_res = df_res[cols]

    return df_res


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
        'Код хоз-ва': 'company_code',
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
        'ТЕХНО и СУД': 'СУД',
        'Дата передачи юристу': 'court_date',
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

    # === НОВЫЕ КОЛОНКИ: СУД, court_date, row_id ===
    if 'СУД' not in df.columns:
        df['СУД'] = 0
    df['СУД'] = pd.to_numeric(df['СУД'], errors='coerce').fillna(0).astype(int)

    if 'court_date' in df.columns:
        df['court_date'] = pd.to_datetime(df['court_date'], errors='coerce')
    else:
        df['court_date'] = pd.NaT

    # row_id — уникальный идентификатор исходной строки Excel
    df = df.reset_index(drop=True)
    df['row_id'] = df.index

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
                 'payment_amount', 'payment_date', 'payment_num', 'order_type', 'row_type',
                 'row_id', 'СУД', 'court_date']
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


def get_prepayments_data(df, period_selection=None, manager=None):
    """
    Возвращает DataFrame с предсчётами (order_type = 1).

    Колонки: company_code, company, oblast, raion, manager,
             invoice_num, invoice_date, invoice_amount, research_type.
    Фильтр по периоду (invoice_date) и менеджеру.
    Сортировка: по дате (новые сверху).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    work = df[
        (df['row_type'] == 'sale') &
        (df['order_type'] == 1)
    ].copy()

    if work.empty:
        return pd.DataFrame()

    # Фильтр по менеджеру
    if manager and manager != 'Все менеджеры':
        work = work[work['manager'] == manager]

    # Фильтр по периоду
    if period_selection and 'Весь период' not in period_selection:
        years, months_2026 = _parse_period_selection(period_selection)
        mask = pd.Series(False, index=work.index)
        for y in years:
            mask |= (work['invoice_date'].dt.year == y)
        for m in months_2026:
            mask |= ((work['invoice_date'].dt.year == 2026) & (work['invoice_date'].dt.month == m))
        work = work[mask]

    # Сортировка по дате (новые сверху)
    work = work.sort_values('invoice_date', ascending=False)

    return work


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
    """
    Сводка по дебиторке, суду и переплатам — за выбранный период.

    Логика ПОСТРОЧНАЯ (по row_id), как в get_debt_structure.
    Дебиторка, суд, переплата — только по счетам выбранного периода.
    Продажи и оплаты — через filter_sales / filter_payments.
    """
    if df is None or df.empty:
        return {'sales': 0, 'payments': 0, 'debt': 0, 'court': 0, 'overpay': 0,
                'percent': 0, 'payments_current': 0, 'payments_old': 0}

    # Продажи и оплаты — через фильтры
    sales_df = filter_sales(df, period_selection, manager)
    payments_df = filter_payments(df, period_selection, manager)

    sales = float(sales_df[sales_df['order_type'] == 0]['invoice_amount'].sum())
    payments = float(payments_df['payment_amount'].sum())

    # === Построчный расчёт дебиторки/суда/переплаты ЗА ПЕРИОД ===
    # Только счета (order_type == 0)
    sales_only = sales_df[sales_df['order_type'] == 0].copy()

    # Оплаты по row_id — из ВСЕГО df (не только за период), потому что оплата могла прийти позже счёта
    all_payments = df[df['row_type'] == 'payment']
    if not all_payments.empty and 'row_id' in all_payments.columns:
        pay_by_row = all_payments.groupby('row_id')['payment_amount'].sum().to_dict()
    else:
        pay_by_row = {}

    # Готовим СУД
    if 'СУД' not in sales_only.columns:
        sales_only['СУД'] = 0
    sales_only['СУД'] = pd.to_numeric(sales_only['СУД'], errors='coerce').fillna(0).astype(int)

    debt = 0.0
    court = 0.0
    overpay = 0.0

    for _, row in sales_only.iterrows():
        row_id = row.get('row_id')
        inv_amt = float(row.get('invoice_amount') or 0)
        paid = float(pay_by_row.get(row_id, 0.0))

        paid_part = min(paid, inv_amt)
        overpay_part = max(0.0, paid - inv_amt)
        unpaid = inv_amt - paid_part

        overpay += overpay_part

        is_court = int(row.get('СУД', 0)) == 1
        if is_court:
            court += unpaid
        else:
            debt += unpaid

    # % дебиторки — реальный (относительно продаж за период)
    percent = (debt / sales * 100) if sales > 0 else 0.0

    # payments_current / payments_old — по старой логике (через ключ счёта)
    sales_period_keys = sales_only[['company', 'invoice_num', 'invoice_date']].drop_duplicates()

    payments_all_filtered = df[df['row_type'] == 'payment']
    if manager and manager != 'Все менеджеры':
        payments_all_filtered = payments_all_filtered[payments_all_filtered['manager'] == manager]

    merged = payments_all_filtered.merge(
        sales_period_keys,
        on=['company', 'invoice_num', 'invoice_date'],
        how='inner'
    )
    payments_current = float(merged['payment_amount'].sum())
    payments_old = payments - payments_current
    if payments_old < 0:
        payments_old = 0

    return {
        'sales': sales,
        'payments': payments,
        'payments_current': payments_current,
        'payments_old': payments_old,
        'debt': debt,
        'court': court,
        'overpay': overpay,
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
    """
    Структура дебиторки по срокам.
    Построчно, с учётом суда.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['category', 'amount', 'count'])

    sales = df[(df['row_type'] == 'sale') & (df['order_type'] == 0)].copy()
    if sales.empty:
        return pd.DataFrame(columns=['category', 'amount', 'count'])

    payments = df[df['row_type'] == 'payment']
    if not payments.empty:
        pay_by_row = payments.groupby('row_id')['payment_amount'].sum().to_dict()
    else:
        pay_by_row = {}

    if manager and manager != 'Все менеджеры':
        sales = sales[sales['manager'] == manager]

    if 'СУД' not in sales.columns:
        sales['СУД'] = 0
    sales['СУД'] = pd.to_numeric(sales['СУД'], errors='coerce').fillna(0).astype(int)

    now = pd.Timestamp.now()
    rows = []
    for _, row in sales.iterrows():
        if int(row.get('СУД', 0)) == 1:
            continue
        inv_amt = float(row.get('invoice_amount') or 0)
        paid = float(pay_by_row.get(row.get('row_id'), 0.0))
        debt = max(0.0, inv_amt - min(paid, inv_amt))
        if debt <= 0.5:
            continue
        inv_date = row.get('invoice_date')
        days = (now - inv_date).days if pd.notna(inv_date) else 0
        if days <= 30:
            cat = '0-30'
        elif days <= 60:
            cat = '31-60'
        elif days <= 90:
            cat = '61-90'
        elif days <= 120:
            cat = '91-120'
        else:
            cat = '120+'
        rows.append({'category': cat, 'debt': debt})

    if not rows:
        return pd.DataFrame(columns=['category', 'amount', 'count'])

    tmp = pd.DataFrame(rows)
    result = tmp.groupby('category').agg(
        amount=('debt', 'sum'),
        count=('debt', 'count')
    ).reset_index()

    order = ['0-30', '31-60', '61-90', '91-120', '120+']
    result['category'] = pd.Categorical(result['category'], categories=order, ordered=True)
    return result.sort_values('category').reset_index(drop=True)


def get_debt_by_manager(df, period_selection=None, summary=None):
    """
    Дебиторка по менеджерам.
    Каждая строка привязывается к менеджеру, указанному в этой строке.
    Использует debt_by_manager / court_by_manager из summary.
    """
    if summary is None:
        if df is None or df.empty:
            return pd.DataFrame()
        summary = get_summary_cached(df)

    if not summary:
        return pd.DataFrame()

    by_mgr = {}

    for code, m in summary.items():
        # Дебиторка — по менеджеру строки
        dbm = m.get('debt_by_manager', {}) or {}
        for mgr, amount in dbm.items():
            if mgr not in by_mgr:
                by_mgr[mgr] = {'debt': 0.0, 'court': 0.0, 'companies_set': set()}
            by_mgr[mgr]['debt'] += amount
            if amount > 0.5:
                by_mgr[mgr]['companies_set'].add(code)

        # Суд — по менеджеру строки
        cbm = m.get('court_by_manager', {}) or {}
        for mgr, amount in cbm.items():
            if mgr not in by_mgr:
                by_mgr[mgr] = {'debt': 0.0, 'court': 0.0, 'companies_set': set()}
            by_mgr[mgr]['court'] += amount

    rows = []
    for mgr, v in by_mgr.items():
        rows.append({
            'manager': mgr,
            'debt': v['debt'],
            'court': v['court'],
            'companies': len(v['companies_set']),
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    total_debt = result['debt'].sum()
    result['debt_share'] = result['debt'] / total_debt * 100 if total_debt > 0 else 0

    return result.sort_values('debt', ascending=False)


def get_debt_companies(df, period_selection=None, manager=None):
    """
    Предприятия с дебиторкой.
    Берёт debt_amount из summary (суд уже вычтен).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    summary = get_summary_cached(df)
    if not summary:
        return pd.DataFrame()

    rows = []
    for code, m in summary.items():
        if manager and manager != 'Все менеджеры':
            if m.get('manager') != manager:
                continue
        debt = m.get('debt_amount', 0.0)
        if debt <= 0.5:
            continue
        rows.append({
            'company_code': m.get('company_code') or code,
            'company': m.get('company_name') or '',
            'manager': m.get('manager') or '',
            'total_debt': debt,
            'debt_days_max': m.get('debt_days_max', 0),
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result
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

    # Количество оплат — уникальные платёжки по (payment_num, company_code)
    def unique_payment_count(group):
        pairs = group[['payment_num', 'company_code']].drop_duplicates()
        return len(pairs)

    result = payments.groupby('manager').apply(
        lambda g: pd.Series({
            'payments': g['payment_amount'].sum(),
            'bonus_category': g['bonus_category'].sum(),
            'count': unique_payment_count(g),
        })
    ).reset_index()

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

def get_company_metrics(company_code, df_company, flags, admin_settings, trust_limits, primary_map=None, regions_map=None):
    """
    Вычисляет метрики одного предприятия.

    df_company — DataFrame со счетами/оплатами ТОЛЬКО этого предприятия.
    flags — dict с метками из CompanyFlags для этого кода.
    admin_settings — dict.
    trust_limits — dict {'threshold_1': 5000, ...}.

    Возвращает dict с метриками.

    Логика дебиторки и суда — ПОСТРОЧНАЯ (по row_id).
    По каждой строке Excel:
      paid    = сумма оплат по row_id
      unpaid  = max(0, invoice_amount − paid)
      overpay = max(0, paid − invoice_amount)
      если СУД == 1: court_part = unpaid, debt_part = 0
      иначе:         court_part = 0,      debt_part = unpaid
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
        'last_gap': 0,
        'last_invoice': None,
        'debt_amount': 0.0,
        'debt_days_max': 0,
        'court_amount': 0.0,
        'court_days_max': 0,
        'overpay_amount': 0.0,
        'has_court': False,
        'court_rows': [],
        'status': 'working',
        'metki': [],
        'category': 'working',
        'has_prepayment': False,
        'debt_by_manager': {},
        'court_by_manager': {},
        'overpay_by_manager': {},
        'debt_transferred_from': {},
        'court_transferred_from': {},
        'overpay_transferred_from': {},
        'managers_set': set(),
        # Для покрытия
        'stability': None,
        'total_animals': 0,
        'milking_cows': 0,
        'pigs_count': 0,
        'poultry': {},
        'production_sites_count': 0,
        'coverage_group': 'other',
    }

    # Если нет счетов — «Пассивное» (или ручное «Потенциальное»)
    if sales.empty:
        # Заполняем основные поля из любой доступной строки (предсчёта тоже подойдут)
        any_row = df_company[
            df_company['invoice_date'].notna()
        ].sort_values('invoice_date', ascending=False)
        if not any_row.empty:
            last = any_row.iloc[0]
            result['company_name'] = last.get('company')
            result['oblast'] = last.get('oblast')
            result['raion'] = last.get('raion')
            result['manager'] = last.get('manager')
            result['last_activity_date'] = last.get('invoice_date')

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

    # === ДАННЫЕ ИЗ REGIONS (для покрытия) ===
    if regions_map and company_code in regions_map:
        branches = regions_map[company_code]
        # Ищем филиал с совпадающим районом
        target_branch = None
        for br in branches:
            if br.get('raion') == result.get('raion'):
                target_branch = br
                break
        if not target_branch and branches:
            target_branch = branches[0]

        if target_branch:
            result['stability'] = target_branch.get('stability')
            result['total_animals'] = target_branch.get('total_animals', 0) or 0
            result['milking_cows'] = target_branch.get('milking_cows', 0) or 0
            result['pigs_count'] = target_branch.get('pigs_count', 0) or 0
            result['poultry'] = target_branch.get('poultry', {}) or {}
            result['production_sites_count'] = target_branch.get('production_sites_count', 0) or 0

    # === АКТИВНЫЙ МЕНЕДЖЕР (для привязки долгов) ===
    active_only = [m for m in ACTIVE_MANAGERS if m != 'Все менеджеры']
    current_manager = result['manager']
    current_raion = result.get('raion')

    # Приоритет 1: из файла Regions (по совпадению района)
    file_primary = None
    if regions_map and company_code in regions_map:
        branches = regions_map[company_code]
        # Ищем филиал с совпадающим районом
        for br in branches:
            if br.get('raion') == current_raion:
                file_primary = br.get('primary_manager')
                break
        # Если не нашли — берём первый
        if not file_primary and branches:
            file_primary = branches[0].get('primary_manager')

    if file_primary:
        # Основной менеджер — из файла (истина)
        active_mgr = file_primary
    elif current_manager and current_manager in active_only:
        # Текущий менеджер активный — долги идут ему
        active_mgr = current_manager
    elif primary_map:
        # Текущий неактивный — берём основного по району
        active_mgr = primary_map.get(company_code, current_manager)
        # Если основной тоже неактивный — оставляем как есть
        if active_mgr not in active_only:
            active_mgr = current_manager
    else:
        # Нет данных — оставляем текущего
        active_mgr = current_manager

    invoice_dates = sales['invoice_date'].dropna().sort_values()
    if len(invoice_dates) > 0:
        result['first_invoice_date'] = invoice_dates.iloc[0]
        result['last_invoice_date'] = invoice_dates.iloc[-1]
        result['days_since_last'] = (today - invoice_dates.iloc[-1]).days
        result['invoices_count'] = len(invoice_dates)
        # Разрыв между последней и предпоследней заявкой (для Камбэков)
        if len(invoice_dates) >= 2:
            result['last_gap'] = int((invoice_dates.iloc[-1] - invoice_dates.iloc[-2]).days)
        else:
            result['last_gap'] = 0

        # === Последний счёт (для отображения в Камбэках) ===
        last_date = invoice_dates.iloc[-1]
        last_rows = sales[sales['invoice_date'] == last_date]
        result['last_invoice'] = {
            'date': last_date,
            'num': last_rows['invoice_num'].iloc[0] if 'invoice_num' in last_rows.columns and not last_rows.empty else '',
            'amount': float(last_rows['invoice_amount'].sum()),
            'research_type': last_rows['research_type'].iloc[0] if 'research_type' in last_rows.columns and not last_rows.empty else '',
        }
    else:
        result['last_invoice'] = None

    # === ПОСТРОЧНЫЙ РАСЧЁТ ДЕБИТОРКИ, СУДА, ПЕРЕПЛАТ ===
    # Собираем оплаты по row_id
    if not payments.empty and 'row_id' in payments.columns:
        pay_by_row = payments.groupby('row_id')['payment_amount'].sum().to_dict()
    else:
        pay_by_row = {}

    # Готовим колонку СУД
    if 'СУД' not in sales.columns:
        sales['СУД'] = 0
    sales['СУД'] = pd.to_numeric(sales['СУД'], errors='coerce').fillna(0).astype(int)

    if 'court_date' not in sales.columns:
        sales['court_date'] = pd.NaT
    sales['court_date'] = pd.to_datetime(sales['court_date'], errors='coerce')

    debt_rows = []
    court_rows_data = []
    overpay_total = 0.0

    # Разбивка по менеджеру строки
    debt_by_manager = {}
    court_by_manager = {}
    overpay_by_manager = {}
    managers_set = set()

    # Все менеджеры из ВСЕХ строк (счёт + предсчёт)
    all_company_rows = df_company[
        (df_company['row_type'] == 'sale') &
        (df_company['invoice_date'].notna())
    ]
    for _, r in all_company_rows.iterrows():
        row_manager = r.get('manager')
        if row_manager:
            managers_set.add(row_manager)

    # Добавляем менеджеров из файла Regions — только для ЭТОГО филиала
    if regions_map and company_code in regions_map:
        current_raion = result.get('raion')
        for br in regions_map[company_code]:
            # Только филиал с совпадающим районом
            if br.get('raion') == current_raion:
                pm = br.get('primary_manager')
                if pm:
                    managers_set.add(pm)
                sm = br.get('substitute_manager')
                if sm:
                    managers_set.add(sm)

    # Словари для пометок (переходящий долг)
    debt_transferred_from = {}
    court_transferred_from = {}
    overpay_transferred_from = {}

    for _, row in sales.iterrows():
        row_id = row.get('row_id')
        inv_amt = float(row.get('invoice_amount') or 0)
        paid = float(pay_by_row.get(row_id, 0.0))
        row_manager = row.get('manager') or '—'

        # (managers_set заполняется выше из ВСЕХ строк)

        paid_part = min(paid, inv_amt)
        overpay = max(0.0, paid - inv_amt)
        unpaid = inv_amt - paid_part

        overpay_total += overpay

        # Привязка — к АКТИВНОМУ менеджеру предприятия
        target_mgr = active_mgr if active_mgr else row_manager

        # Пометка, если строка от ДРУГОГО менеджера
        is_transferred = (row_manager != target_mgr)

        if overpay > 0.5:
            overpay_by_manager[target_mgr] = overpay_by_manager.get(target_mgr, 0.0) + overpay
            if is_transferred:
                overpay_transferred_from.setdefault(target_mgr, {})
                overpay_transferred_from[target_mgr][row_manager] = \
                    overpay_transferred_from[target_mgr].get(row_manager, 0.0) + overpay

        is_court = int(row.get('СУД', 0)) == 1

        if is_court:
            court_part = unpaid
            debt_part = 0.0
        else:
            court_part = 0.0
            debt_part = unpaid

        inv_date = row.get('invoice_date')

        if debt_part > 0.5:
            days = (today - inv_date).days if pd.notna(inv_date) else 0
            debt_rows.append({'debt': debt_part, 'days': days})
            debt_by_manager[target_mgr] = debt_by_manager.get(target_mgr, 0.0) + debt_part
            if is_transferred:
                debt_transferred_from.setdefault(target_mgr, {})
                debt_transferred_from[target_mgr][row_manager] = \
                    debt_transferred_from[target_mgr].get(row_manager, 0.0) + debt_part

        if court_part > 0.5:
            c_date = row.get('court_date')
            c_days = (today - c_date).days if pd.notna(c_date) else 0
            court_by_manager[target_mgr] = court_by_manager.get(target_mgr, 0.0) + court_part
            if is_transferred:
                court_transferred_from.setdefault(target_mgr, {})
                court_transferred_from[target_mgr][row_manager] = \
                    court_transferred_from[target_mgr].get(row_manager, 0.0) + court_part

            court_rows_data.append({
                'company_code': company_code,
                'company': row.get('company'),
                'manager': target_mgr,           # ← активный
                'transfer_from': row_manager if is_transferred else None,
                'raion': row.get('raion'),
                'oblast': row.get('oblast'),
                'research_type': row.get('research_type'),
                'invoice_num': row.get('invoice_num'),
                'invoice_date': inv_date,
                'invoice_amount': inv_amt,
                'paid_amount': paid_part,
                'court_amount': court_part,
                'court_date': c_date,
                'court_days': c_days,
            })

    # Итоги
    result['debt_amount'] = float(sum(r['debt'] for r in debt_rows))
    result['debt_days_max'] = int(max((r['days'] for r in debt_rows), default=0))
    result['court_amount'] = float(sum(r['court_amount'] for r in court_rows_data))
    result['court_days_max'] = int(max((r['court_days'] for r in court_rows_data), default=0))
    result['overpay_amount'] = float(overpay_total)
    result['has_court'] = result['court_amount'] > 0.5
    result['court_rows'] = court_rows_data

    # Разбивка по менеджерам
    result['debt_by_manager'] = debt_by_manager
    result['court_by_manager'] = court_by_manager
    result['overpay_by_manager'] = overpay_by_manager
    result['managers_set'] = managers_set

    # Пометки переходящих долгов
    result['debt_transferred_from'] = debt_transferred_from
    result['court_transferred_from'] = court_transferred_from
    result['overpay_transferred_from'] = overpay_transferred_from

    # Активный менеджер (для отображения)
    result['active_manager'] = active_mgr

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

    # === ГРУППА ПОКРЫТИЯ ===
    result['coverage_group'] = calculate_coverage_group(result)

    return result


def calculate_company_status(invoice_dates, flags, admin_settings, today):
    """
    Вычисляет статус предприятия.

    Приоритет:
    1. potential (ручной)
    2. new — 1 счёт в текущем календарном месяце
    3. returned (Камбэки) — разрыв > returned_days + последний счёт в текущем календарном месяце
    4. working (Актив) — ≤ working_days дней от последнего счёта
    5. passive (Пассив) — 61–passive_days дней
    6. lost (Потери) — > lost_days дней
    """
    if flags.get('status') == 'potential':
        return 'potential'

    if len(invoice_dates) == 0:
        return 'lost'

    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    first_invoice = invoice_dates.iloc[0]
    last_invoice = invoice_dates.iloc[-1]
    days_since_last = (today - last_invoice).days

    working_days = admin_settings.get('working_days', 60)
    passive_days = admin_settings.get('passive_days', 120)
    lost_days = admin_settings.get('lost_days', 120)
    returned_days = admin_settings.get('returned_days', 120)

    # === НОВОЕ ===
    # Первый счёт в текущем календарном месяце (не важно, сколько всего)
    if first_invoice >= current_month_start:
        return 'new'

    # === КАМБЭКИ ===
    # Последний счёт в текущем календарном месяце + разрыв с предпоследним > returned_days
    if len(invoice_dates) >= 2:
        if last_invoice >= current_month_start:
            last_gap = (invoice_dates.iloc[-1] - invoice_dates.iloc[-2]).days
            if last_gap > returned_days:
                return 'returned'

    # === АКТИВ / ПАССИВ / ПОТЕРИ ===
    if days_since_last <= working_days:
        return 'working'
    elif days_since_last <= lost_days:
        return 'passive'
    else:
        return 'lost'


def calculate_company_metki(result, flags, admin_settings, trust_limits):
    """
    Возвращает список меток для предприятия.
    result — dict с метриками из get_company_metrics.

    Метки могут пересекаться, кроме ЧС (он — исключение).
    ⚖️ Суд ставится автоматически, если есть судная дебиторка (has_court).
    """
    metki = []

    # 1. ЧС — исключение (только 💀)
    if flags.get('blacklist'):
        return ['💀']

    # 2. Суд (автоматически, если есть судная дебиторка)
    if result.get('has_court'):
        metki.append('⚖️')

    # 3. Золотой фонд
    if flags.get('golden_fund'):
        metki.append('🏆')

    # 4. Дебиторка / Должник (только по НЕ-судным строкам)
    debt = result.get('debt_amount', 0.0)
    debt_days = result.get('debt_days_max', 0)
    debtor_threshold_key = f"threshold_{admin_settings.get('debtor_threshold', 2)}"
    debtor_threshold_value = trust_limits.get(debtor_threshold_key, 7000.0)

    if debt > 0.5:
        if debt_days > admin_settings.get('debtor_days', 90) or debt >= debtor_threshold_value:
            metki.append('💸')  # Должник
        else:
            metki.append('💰')  # Дебиторка

    # 5. Нет заявок — только если НЕТ дебиторки И НЕТ других важных меток (⚖️, 💸)
    days_since_last = result.get('days_since_last')

    has_priority_metka = ('⚖️' in metki) or ('💸' in metki)

    if not has_priority_metka and days_since_last is not None:
        if days_since_last > admin_settings.get('inactive_days', 30) and debt < 0.5:
            metki.append('⏰')

    return metki


def calculate_coverage_group(result):
    """
    Определяет группу предприятия для расчёта покрытия.

    Приоритет: Другие → Нерабочие → Рабочие.

    Другие: 💸 Должник, 💀 ЧС, стабильность 3, не КРС
    Нерабочие: 🗑️ Потери, ⏰ Нет заявок, 💰 Дебиторка
    Рабочие: ✅ Актив, 😴 Пассив, 🆕 Новые, 🔄 Камбэки
    """
    metki = result.get('metki', [])
    status = result.get('status', 'working')

    # === ДРУГИЕ (приоритет 1) ===
    # 💀 ЧС
    if '💀' in metki:
        return 'other'

    # 💸 Должник
    if '💸' in metki:
        return 'other'

    # Стабильность 3
    stability = result.get('stability')
    if stability == 3:
        return 'other'

    # Не КРС (свиньи или птица, но не КРС)
    pigs = result.get('pigs_count', 0) or 0
    poultry = result.get('poultry', {}) or {}
    has_poultry = bool(poultry.get('type'))
    total_animals = result.get('total_animals', 0) or 0
    milking_cows = result.get('milking_cows', 0) or 0

    if (pigs > 0 or has_poultry) and total_animals == 0 and milking_cows == 0:
        return 'other'

    # === НЕРАБОЧИЕ (приоритет 2) ===
    if '💰' in metki:
        return 'non_working'

    if '⏰' in metki:
        return 'non_working'

    if status == 'lost':
        return 'non_working'

    # === РАБОЧИЕ (приоритет 3) ===
    if status in ('working', 'passive', 'new', 'returned'):
        return 'working'

    # По умолчанию — другие
    return 'other'


def get_priority_category(result, flags):
    """
    Приоритетная категория для круговой диаграммы.
    Порядок: ЧС → Суд → Золото → Статусы → Метки → working.
    """
    metki = result.get('metki', [])
    status = result.get('status', 'working')

    # Метки-приоритеты (вручную / автоматически)
    if '💀' in metki:
        return 'blacklist'
    if '⚖️' in metki:
        return 'court'
    if '🏆' in metki:
        return 'golden_fund'

    # Статусы (выше автоматических меток)
    if status == 'new':
        return 'new'
    if status == 'returned':
        return 'returned'
    if status == 'potential':
        return 'potential'
    if status == 'lost':
        return 'lost'
    if status == 'passive':
        return 'passive'

    # Автоматические метки — только для «Актив»
    if '💸' in metki:
        return 'debtor'
    if '💰' in metki:
        return 'debitorka'
    if '⏰' in metki:
        return 'inactive'

    return 'working'


def get_all_companies_summary(df, flags=None, admin_settings=None, trust_limits=None):
    """
    Считает метрики для ВСЕХ предприятий.
    Два прохода: первый — базовый summary, второй — с учётом primary_map.
    """
    if flags is None:
        flags = load_company_flags() or {}
    if admin_settings is None:
        admin_settings = get_admin_settings()
    if trust_limits is None:
        trust_limits = load_trust_limits()

    if df is None or df.empty:
        return {}

    # Загружаем файл закреплений
    regions_map = load_regions()

    # Заполняем пропущенные районы
    df = df.copy()
    df['raion_filled'] = df['raion'].fillna('').astype(str).str.strip()

    summary = {}

    # Группируем по (company_code, raion)
    grouped = df.groupby(['company_code', 'raion_filled'])

    # Первый проход: базовый summary (для primary_map)
    for (code, raion), df_group in grouped:
        code_str = str(code).strip()
        if not code_str or code_str == 'nan':
            continue

        # Формируем ключ: code|raion или code (если raion пустой)
        if raion:
            key = f"{code_str}|{raion}"
        else:
            key = code_str

        company_flags = flags.get(code_str, {})

        metrics = get_company_metrics(
            company_code=code_str,
            df_company=df_group,
            flags=company_flags,
            admin_settings=admin_settings,
            trust_limits=trust_limits,
            primary_map=None,
            regions_map=regions_map,
        )
        summary[key] = metrics

    # Считаем primary_map (эвристика по районам)
    primary_map = get_primary_manager_by_raion(summary)

    # Второй проход: пересчёт с учётом primary_map
    for (code, raion), df_group in grouped:
        code_str = str(code).strip()
        if not code_str or code_str == 'nan':
            continue

        if raion:
            key = f"{code_str}|{raion}"
        else:
            key = code_str

        company_flags = flags.get(code_str, {})

        metrics = get_company_metrics(
            company_code=code_str,
            df_company=df_group,
            flags=company_flags,
            admin_settings=admin_settings,
            trust_limits=trust_limits,
            primary_map=primary_map,
            regions_map=regions_map,
        )
        summary[key] = metrics

    return summary


def get_primary_manager_by_raion(summary):
    """
    Определяет основного менеджера для каждого предприятия.

    Логика:
    1. Группируем по районам: {raion: {manager: count}}
    2. Основной — тот, у кого БОЛЬШЕ ВСЕГО предприятий в районе,
       но только из ACTIVE_MANAGERS.
    3. При равенстве — первый по алфавиту.
    4. Если в районе нет активных — берём последнего менеджера предприятия.
    5. Если raion пустой — берём последнего менеджера предприятия.

    Возвращает: {company_code: primary_manager_name}
    """
    active_only = [m for m in ACTIVE_MANAGERS if m != 'Все менеджеры']

    # Группируем: {raion: {manager: count}} — только активные
    raion_counts = {}
    for code, m in summary.items():
        raion = m.get('raion')
        manager = m.get('manager')
        if not raion or pd.isna(raion):
            continue
        if not manager:
            continue
        if manager not in active_only:
            continue  # неактивных не считаем
        if raion not in raion_counts:
            raion_counts[raion] = {}
        raion_counts[raion][manager] = raion_counts[raion].get(manager, 0) + 1

    # Определяем основного для каждого района
    raion_primary = {}
    for raion, counts in raion_counts.items():
        # max по количеству, при равенстве — первый по алфавиту
        primary = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
        raion_primary[raion] = primary

    # Для каждого предприятия
    result = {}
    for code, m in summary.items():
        raion = m.get('raion')
        manager = m.get('manager')

        # 1. Если последний менеджер — активный, он и основной
        if manager and manager in active_only:
            result[code] = manager
            continue

        # 2. Иначе — определяем по району
        if raion and not pd.isna(raion) and raion in raion_primary:
            result[code] = raion_primary[raion]
        else:
            # Нет района / нет активных — берём последнего менеджера
            result[code] = manager or '—'

    return result


def format_managers_display(primary, managers_set):
    """
    Формирует строку для колонки «Менеджер»:
    {primary} / (подмена) {подменный1} / (подмена) {подменный2}

    Подменные — только АКТИВНЫЕ, по алфавиту.
    Если primary неактивный — показываем с пометкой ⚠️.
    """
    active_only = [m for m in ACTIVE_MANAGERS if m != 'Все менеджеры']

    # Формируем отображение основного
    if primary and primary in active_only:
        primary_display = primary
    elif primary:
        primary_display = f"{primary} ⚠️"
    else:
        primary_display = '—'

    if not managers_set:
        return primary_display

    # Подменные — только активные, по алфавиту
    others = sorted([m for m in managers_set if m and m != primary and m in active_only])

    if not others:
        return primary_display

    parts = [primary_display]
    for mgr in others:
        parts.append(f"(подмена) {mgr}")

    return ' / '.join(parts)


def get_all_court_rows(summary, manager_filter=None):
    """
    Собирает все court_rows из всех предприятий в один DataFrame.

    manager_filter — фильтр по ТЕКУЩЕМУ менеджеру предприятия (m['manager']).
    """
    if not summary:
        return pd.DataFrame()

    rows = []
    for code, m in summary.items():
        # Фильтр по текущему менеджеру предприятия
        if manager_filter and manager_filter != 'Все менеджеры':
            if (m.get('active_manager') or m.get('manager')) != manager_filter:
                continue

        court_rows = m.get('court_rows') or []
        for cr in court_rows:
            # Гарантируем наличие transfer_from
            if 'transfer_from' not in cr:
                cr['transfer_from'] = None
            rows.append(cr)

    if not rows:
        return pd.DataFrame()

    df_res = pd.DataFrame(rows)
    df_res = df_res.sort_values('court_amount', ascending=False)
    return df_res


def get_summary_cached(df, force=False, flags=None, admin_settings=None, trust_limits=None):
    """
    Возвращает summary с кэшем (TTL 5 минут).
    Сбрасывается при save_company_flags / save_trust_limits / save_admin_settings.
    """
    global _summary_cache
    now = datetime.now()

    if flags is None:
        flags = load_company_flags() or {}
    if admin_settings is None:
        admin_settings = get_admin_settings()
    if trust_limits is None:
        trust_limits = load_trust_limits()

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
    'court': '⚖️ Суд',
    'golden_fund': '🏆 Золотой фонд',
    'new': '🆕 Новое',
    'returned': '🔄 Камбэки',
    'potential': '🤝 Потенциальное',
    'debtor': '💸 Должник',
    'debitorka': '💰 Дебиторка',
    'inactive': '⏰ Нет заявок',
    'working': '✅ Актив',
    'passive': '😴 Пассив',
    'lost': '🗑️ Потери',
}

CATEGORY_ORDER = [
    'blacklist', 'court', 'golden_fund', 'new', 'returned', 'potential',
    'debtor', 'debitorka', 'inactive', 'working', 'passive', 'lost',
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
            if (metrics.get('active_manager') or metrics.get('manager')) != manager_filter:
                continue

        cat = metrics.get('category', 'working')
        if cat in result:
            result[cat].append(code)
        else:
            result['working'].append(code)

    return result


def get_companies_by_metka(summary, manager_filter=None):
    """
    Группирует предприятия по МЕТКАМ (не по приоритету).

    Метки могут пересекаться — одно предприятие может быть в нескольких категориях.

    Возвращает dict {category: [list of company_codes]}.

    Для статусов (new, returned, potential) — по статусу.
    Для меток (blacklist, golden_fund, court, debtor, debitorka, inactive) — по метке.
    """
    result = {cat: [] for cat in CATEGORY_ORDER}

    for code, m in summary.items():
        # Фильтр по менеджеру
        if manager_filter and manager_filter != 'Все менеджеры':
            if (m.get('active_manager') or m.get('manager')) != manager_filter:
                continue

        metki = m.get('metki', [])
        status = m.get('status', 'working')

        # === СТАТУСЫ (по одному на предприятие) ===
        if status == 'new':
            result['new'].append(code)
        if status == 'returned':
            result['returned'].append(code)
        if status == 'potential':
            result['potential'].append(code)
        # working / passive / lost — не табы, а общий список

        # === МЕТКИ (могут пересекаться) ===
        if '💀' in metki:
            result['blacklist'].append(code)
        if '🏆' in metki:
            result['golden_fund'].append(code)
        if '⚖️' in metki:
            result['court'].append(code)
        if '💸' in metki:
            result['debtor'].append(code)
        if '💰' in metki:
            result['debitorka'].append(code)
        if '⏰' in metki:
            result['inactive'].append(code)

    return result


def get_independent_counts(summary, manager_filter=None):
    """
    Независимый подсчёт предприятий по статусам и меткам.
    Пересечение допустимо: одно предприятие может попасть в несколько счётчиков
    (например, 💀 и ⚖️, или 💸 и ⚖️).

    Возвращает dict:
      {
        # статусы (по одному на предприятие)
        'working': N, 'passive': N, 'new': N, 'returned': N,
        'lost': N, 'potential': N,
        # метки (могут пересекаться)
        'blacklist': N, 'golden_fund': N, 'debtor': N,
        'debitorka': N, 'inactive': N, 'court': N,
      }
    """
    counts = {
        'working': 0, 'passive': 0, 'new': 0, 'returned': 0,
        'lost': 0, 'potential': 0,
        'blacklist': 0, 'golden_fund': 0, 'debtor': 0,
        'debitorka': 0, 'inactive': 0, 'court': 0,
    }

    for code, m in summary.items():
        if manager_filter and manager_filter != 'Все менеджеры':
            if (m.get('active_manager') or m.get('manager')) != manager_filter:
                continue

        # Статус — один на предприятие
        status = m.get('status', 'working')
        if status in counts:
            counts[status] += 1

        # Метки — независимо, могут пересекаться
        metki = m.get('metki', [])
        if '💀' in metki:
            counts['blacklist'] += 1
        if '🏆' in metki:
            counts['golden_fund'] += 1
        if '💸' in metki:
            counts['debtor'] += 1
        if '💰' in metki:
            counts['debitorka'] += 1
        if '⏰' in metki:
            counts['inactive'] += 1
        if '⚖️' in metki:
            counts['court'] += 1

    return counts


def get_companies_with_metki_df(summary, manager_filter=None):
    """
    Возвращает DataFrame со всеми предприятиями и их метками.
    """
    if not summary:
        return pd.DataFrame()

    # Расшифровка меток (единая для всего приложения)
    METKI_LABELS = {
        '💀': '💀 ЧС',
        '⚖️': '⚖️ Суд',
        '🏆': '🏆 Золото',
        '🆕': '🆕 Новое',
        '🔄': '🔄 Камбэки',
        '🤝': '🤝 Потенциальное',
        '💸': '💸 Должник',
        '💰': '💰 Дебиторка',
        '⏰': '⏰ Нет заявок',
    }

    rows = []
    for code, m in summary.items():
        if manager_filter and manager_filter != 'Все менеджеры':
            if (m.get('active_manager') or m.get('manager')) != manager_filter:
                continue

        metki_raw = m.get('metki', [])
        metki_str = ' • '.join(METKI_LABELS.get(emoji, emoji) for emoji in metki_raw)
        rows.append({
            'company_code': m.get('company_code') or code,
            'company_name': m.get('company_name') or '',
            'oblast': m.get('oblast') or '',
            'raion': m.get('raion') or '',
            'manager': m.get('manager') or '',
            'managers_with_debt': ', '.join(sorted(m.get('debt_by_manager', {}).keys())) or '',
            'managers_set': list(m.get('managers_set', set())),
            'debt_amount': m.get('debt_amount', 0.0),
            'debt_days_max': m.get('debt_days_max', 0),
            'court_amount': m.get('court_amount', 0.0),
            'court_days_max': m.get('court_days_max', 0),
            'overpay_amount': m.get('overpay_amount', 0.0),
            'has_court': m.get('has_court', False),
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