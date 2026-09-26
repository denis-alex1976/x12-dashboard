import data_loader as dl
import pandas as pd

data = dl.load_all_data(force_refresh=True)
df = data['df']
pay = df[(df['row_type'] == 'payment') & (df['manager'] == 'Чубарь Д.')].copy()

def norm(x):
    s = str(x).strip().lower() if pd.notna(x) else ''
    return '' if s in ('архив', 'долг', 'нет пп', 'нет пп.', '') else s

pay['_p'] = pay['payment_num'].apply(norm)

print('Всего строк:', len(pay))
print('Уникальных (норм.payment_num, company_code):',
      pay[['_p', 'company_code']].drop_duplicates().shape[0])
print()
print('Разбивка по норм.payment_num (топ-20):')
print(pay['_p'].value_counts().head(20))