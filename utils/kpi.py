def calculate_kpi(manager_name, sales, returns, manager_data):
    """Расчет KPI для менеджера"""
    total_sales = sum(s.get('amount', 0) for s in sales)
    total_returns = sum(r.get('amount', 0) for r in returns)
    
    plan_sales = manager_data.get('plan_sales', 0)
    plan_returns = manager_data.get('plan_returns', 0)
    
    kpi = {}
    
    if plan_sales > 0:
        kpi['plan_sales'] = plan_sales
        kpi['sales_progress'] = (total_sales / plan_sales) * 100
    else:
        kpi['plan_sales'] = 0
        kpi['sales_progress'] = 0
    
    if plan_returns > 0:
        kpi['plan_returns'] = plan_returns
        kpi['returns_progress'] = (total_returns / plan_returns) * 100
    else:
        kpi['plan_returns'] = 0
        kpi['returns_progress'] = 0
    
    return kpi