def get_notifications(data):
    """Генерация уведомлений"""
    notifications = []
    db = data.get('database', {})
    settings = db.get('settings', {})
    debt = data.get('debt', [])
    
    legal_days = settings.get('debt_legal_days', 120)
    warning_days = settings.get('debt_warning_days', 100)
    
    for d in debt:
        if d.get('days', 0) >= legal_days:
            notifications.append({
                'type': 'danger',
                'message': f"🔴 {d['company']}: дебиторка {d['days']} дней - передать юристу!"
            })
        elif d.get('days', 0) >= warning_days:
            notifications.append({
                'type': 'warning',
                'message': f"⚠️ {d['company']}: дебиторка {d['days']} дней - скоро передача юристу"
            })
    
    return notifications[:10]