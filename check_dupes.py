import data_loader as dl

w = dl._get_worksheet('Regions')
data = w.get_all_values()
rows = data[1:]

for code in ['А/КР-2', 'А/КР-54', 'А/КР-87', 'А/КР-138', 'А/КР-152', 'А/КР-215', 'А/КР-257']:
    print(f'--- {code} ---')
    for r in rows:
        if r[0].strip() == code:
            print(f'  {r}')