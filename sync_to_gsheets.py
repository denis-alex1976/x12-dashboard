"""
Синхронизация Excel → Google Sheets.
Дополнительно переносит примечания к столбцу V (частичные оплаты)
в колонку 'payment_parts'.
Обрезает служебные блоки внизу Excel (итоги, месяцы, пробы и т.п.),
оставляя только строки с валидным менеджером.
"""
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import sys
import openpyxl

# === НАСТРОЙКИ ===
EXCEL_PATH = r"C:\ЦЕНТР ИЗЖ\Х\!-Х12.1.xlsm"
SHEET_NAME = "ИСХОДНЫЕ ДАННЫЕ"
CREDENTIALS_FILE = r"C:\ЦЕНТР ИЗЖ\Х\X12.1\service-account.json"
SPREADSHEET_ID = "1AWSwJECekzgfvbYlBsBk-Ws78hpNp5TC7VSPdvv0Nso"
WORKSHEET_NAME = "Data"

COL_V = 22  # столбец V (ПП, дата) — примечания про частичные оплаты

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Колонки, которые нужны data_loader.py
KEEP_COLUMNS = [
    'Наименование хозяйства',
    'Область',
    'Район',
    'Менеджер',
    'Вид Исследования',
    'Счет, номер',
    'Счет, дата',
    'Счет, сумма',
    'ПП, сумма',
    'ПП, дата',
    'ПП, номер',
    'Срок оплаты, дни',
    'цифра в зав-ти от цвета в  столбце R',
    'Кол-во проб',
    'Сумма, BYN',
    'Номер Протокола',
    'Предприятие',
]

# Все менеджеры, которые могут встречаться в реальных данных
# (используется для валидации — отсеивания служебных блоков внизу Excel)
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

DATE_COLUMNS = ['Счет, дата', 'ПП, дата']

# Колонка, куда пишем текст примечания (для частичных оплат)
EXTRA_COLUMN = 'payment_parts'


def load_comment_texts():
    """
    Читает Excel и возвращает {номер_строки: 'текст примечания'}.
    Номер строки — 1-based как в Excel.
    """
    print("📖 Чтение примечаний из Excel...")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=False, read_only=False)
    ws = wb[SHEET_NAME]

    comments = {}
    for row in range(2, ws.max_row + 1):
        cell = ws.cell(row=row, column=COL_V)
        if cell.comment and cell.comment.text:
            text = cell.comment.text.strip().replace('\n', ' ')
            if text:
                comments[row] = text

    wb.close()
    print(f"   Найдено {len(comments)} примечаний")
    return comments


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Старт синхронизации...")

    # 1. Читаем Excel
    print(f"📖 Чтение Excel: {EXCEL_PATH}")
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, header=0)
    except Exception as e:
        print(f"❌ Ошибка чтения Excel: {e}")
        sys.exit(1)

    print(f"   Загружено {len(df)} строк, {len(df.columns)} колонок")

    # 2. Читаем примечания
    comments = load_comment_texts()

    # 3. Фильтруем колонки
    available = [c for c in KEEP_COLUMNS if c in df.columns]
    missing = [c for c in KEEP_COLUMNS if c not in df.columns]
    if missing:
        print(f"⚠️ Не найдены колонки в Excel: {missing}")
    df = df[available].copy()
    print(f"   Оставлено {len(df.columns)} колонок")

    # 4. Обрезаем служебные блоки внизу Excel:
    #    оставляем только строки, где в колонке 'Менеджер' — валидное имя.
    #    Это отсекает итоги, месяцы, пробы, бонусы и прочие служебные блоки.
    if 'Менеджер' in df.columns:
        mask = df['Менеджер'].isin(ALL_MANAGERS)
        if mask.any():
            last_valid = mask[mask].index[-1]
            before = len(df)
            df = df.loc[:last_valid].copy()
            after = len(df)
            if before != after:
                print(f"   Обрезано служебных строк: {before - after} (до индекса {last_valid})")
        else:
            print("⚠️ Не найдено ни одного валидного менеджера — данные НЕ обрезаны")

    # 5. Добавляем колонку payment_parts
    #    ВАЖНО: используем индекс ДО обрезки, чтобы совпадали номера строк Excel.
    #    Но так как мы обрезали DataFrame — индекс сохранён (pandas сохраняет исходные индексы),
    #    поэтому i + 2 всё ещё корректно.
    df[EXTRA_COLUMN] = [
        comments.get(int(i) + 2, '') if str(i).isdigit() else ''
        for i in df.index
    ]
    filled = (df[EXTRA_COLUMN] != '').sum()
    print(f"   Заполнено {EXTRA_COLUMN}: {filled} строк")

    # 6. Даты → ISO-строки
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            df[col] = df[col].dt.strftime('%Y-%m-%d').fillna('')

    df = df.fillna('')

    # 7. Авторизация
    print("🔑 Авторизация в Google...")
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        sys.exit(1)

    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(WORKSHEET_NAME)
    except Exception as e:
        print(f"❌ Ошибка открытия таблицы: {e}")
        sys.exit(1)

    # 8. Пишем
    print(f"📤 Отправка в Google Sheets (лист '{WORKSHEET_NAME}')...")
    try:
        worksheet.clear()
        data_to_write = [df.columns.tolist()] + df.astype(str).values.tolist()
        worksheet.update(data_to_write, value_input_option='RAW')
    except Exception as e:
        print(f"❌ Ошибка записи: {e}")
        sys.exit(1)

    print(f"✅ Синхронизация завершена! Записано {len(df)} строк, {len(df.columns)} колонок.")
    print(f"   Ссылка: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


if __name__ == "__main__":
    main()