import data_loader as dl

# 1. Читаем текущие настройки
s = dl.get_admin_settings()
print("До:", s.get('working_days'), s.get('inactive_days'))

# 2. Меняем одно поле
s['working_days'] = 61
ok = dl.save_admin_settings(s)
print("Сохранено:", ok)

# 3. Читаем заново
s2 = dl.get_admin_settings()
print("После:", s2.get('working_days'))

# 4. Возвращаем как было
s2['working_days'] = 60
dl.save_admin_settings(s2)
s3 = dl.get_admin_settings()
print("Восстановлено:", s3.get('working_days'))