# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
import data_loader

st.set_page_config(
    page_title="X12.1 — Дашборд продаж",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
    .main-header { font-size: 1.5rem; font-weight: bold; color: #1f77b4; margin-bottom: 0.3rem; }
    .metric-box { background: #f0f2f6; padding: 1rem; border-radius: 8px; text-align: center; }
    .metric-box h3 { margin: 0; font-size: 0.9rem; color: #555; }
    .metric-box p { margin: 0.4rem 0 0 0; font-size: 2.2rem; font-weight: bold; color: #1f77b4; }
    .metric-box-sub { font-size: 0.75rem; color: #888; margin-top: 0.3rem; }
    .metric-box-small { background: #fafafa; padding: 0.6rem; border-radius: 8px; text-align: center; }
    .metric-box-small h3 { margin: 0; font-size: 0.8rem; color: #666; }
    .metric-box-small p { margin: 0.2rem 0 0 0; font-size: 1.4rem; font-weight: bold; color: #1f77b4; }

    button[title="Download as CSV"] { display: none !important; }
    [data-testid="stElementToolbar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


MONTHS_RU = {
    1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
    5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
    9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
}

CONTRAST_PALETTE = [
    '#E27D60', '#41B3A3', '#F1B24A', '#C38D9E', '#5DADE2',
    '#A569BD', '#58D68D', '#EC7063', '#F4D03F', '#48C9B0',
    '#EB984E', '#7FB3D5', '#BB8FCE', '#82E0AA', '#F5B041',
]

WARM_PALETTE = [
    '#E8A87C', '#C38D9E', '#85CDCA', '#E27D60', '#D9BF77',
    '#F1B24A', '#D4A5A5', '#C5A880', '#B8A9C9', '#A7C7E7',
    '#E6B89C', '#B5CDA3', '#F5CBA7', '#F2C4A0', '#D6A99A',
]

STATUS_COLORS = {
    '0-30': '#58D68D',
    '31-60': '#F4D03F',
    '61-90': '#F5B041',
    '91-120': '#EC7063',
    '120+': '#C0392B',
}

USER_TABS = [
    ('tab1', "🏢 Предприятия"),
    ('tab2', "📍 Районы"),
    ('tab3', "🗺️ Области"),
    ('tab4', "🔬 Исследования"),
    ('tab5', "💰 Дебиторка"),
    ('tab6', "💵 Оплаты"),
]

ADMIN_TABS = [
    ('tab_access', "🔐 Доступы"),
]

ROLE_LABELS = {
    'super_admin': 'Суперадмин',
    'admin': 'Админ',
    'manager': 'Менеджер',
    'guest': 'Гость',
}

ROLE_OPTIONS = ['super_admin', 'admin', 'manager', 'guest']


def format_int(value):
    try:
        if pd.isna(value):
            return '0'
        return f"{int(round(float(value))):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return '0'


def tab_key_to_name(key):
    for k, v in USER_TABS + ADMIN_TABS:
        if k == key:
            return v
    if key == 'all':
        return 'Все вкладки'
    return key


def tabs_to_display(keys):
    if not keys:
        return '—'
    if 'all' in keys:
        return 'Все вкладки'
    names = [tab_key_to_name(k) for k in keys]
    return ', '.join(names)


def short_ua(ua):
    """Короткое представление User-Agent."""
    if not ua or ua == 'unknown':
        return '—'
    if 'Edg' in ua:
        return 'Edge'
    if 'Chrome' in ua and 'Safari' in ua:
        return 'Chrome'
    if 'Firefox' in ua:
        return 'Firefox'
    if 'Safari' in ua:
        return 'Safari'
    if 'Mobile' in ua:
        return 'Mobile'
    return ua[:40] + ('...' if len(ua) > 40 else '')


@st.cache_data(ttl=600)
def load_data():
    return data_loader.load_all_data()


def check_auth():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.manager_binding = None
        st.session_state.allowed_tabs = []

    if not st.session_state.authenticated:
        st.markdown('<p class="main-header">📊 X12.1 — Вход в систему</p>', unsafe_allow_html=True)
        st.caption("Введите логин и пароль")

        with st.form("login_form"):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти", use_container_width=True)

        if submitted:
            client_info = data_loader.get_client_info()
            ip = client_info.get('ip', 'unknown')
            ua = client_info.get('user_agent', 'unknown')

            user = data_loader.authenticate(username, password)
            if user:
                if user.get('_blocked'):
                    st.error("❌ Пользователь заблокирован")
                    data_loader.log_login(
                        username, ip=ip, user_agent=ua, status='blocked',
                        note='Попытка входа заблокированного пользователя'
                    )
                else:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.role = user['role']
                    st.session_state.manager_binding = user.get('manager_binding')
                    st.session_state.allowed_tabs = user.get('allowed_tabs', [])
                    data_loader.log_login(
                        username, ip=ip, user_agent=ua, status='success'
                    )
                    st.rerun()
            else:
                st.error("❌ Неверный логин или пароль")
                data_loader.log_login(
                    username, ip=ip, user_agent=ua, status='failed',
                    note='Неверный логин или пароль'
                )

        return False

    return True


# ============================================================
# ВКЛАДКА «ДОСТУПЫ»
# ============================================================

def render_access_tab():
    st.subheader("🔐 Управление доступами")

    db = data_loader.load_database()
    users = db.get('users', {})

    total_users = len(users)
    active_users = sum(1 for u in users.values() if not u.get('blocked', False))
    blocked_users = total_users - active_users

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-box"><h3>👥 Всего</h3><p>{total_users}</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-box"><h3>✅ Активных</h3><p>{active_users}</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-box"><h3>🚫 Заблокированных</h3><p>{blocked_users}</p></div>', unsafe_allow_html=True)

    st.divider()

    # === ДОБАВЛЕНИЕ ===
    with st.expander("➕ Добавить пользователя", expanded=False):
        managers_list = data_loader.get_available_managers()
        managers_list = [m for m in managers_list if m != 'Все менеджеры']

        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Логин", key="new_username")
                new_name = st.text_input("Имя (отображаемое)", key="new_name")
                new_role = st.selectbox(
                    "Роль",
                    ROLE_OPTIONS,
                    format_func=lambda r: ROLE_LABELS.get(r, r),
                    key="new_role"
                )
                new_binding = st.selectbox(
                    "Привязка к менеджеру",
                    ['—'] + managers_list,
                    key="new_binding"
                )
            with col2:
                new_tabs = st.multiselect(
                    "Доступные вкладки",
                    options=[k for k, _ in USER_TABS],
                    format_func=tab_key_to_name,
                    key="new_tabs"
                )
                new_password = st.text_input(
                    "Пароль (оставь пустым — сгенерируется)",
                    key="new_password"
                )

            submitted = st.form_submit_button("Создать пользователя", use_container_width=True)

        if submitted:
            if not new_username or not new_name:
                st.error("❌ Логин и имя обязательны")
            elif new_username in users:
                st.error(f"❌ Пользователь {new_username} уже существует")
            else:
                try:
                    binding = None if new_binding == '—' else new_binding
                    pwd = data_loader.create_user(
                        username=new_username,
                        name=new_name,
                        role=new_role,
                        manager_binding=binding,
                        allowed_tabs=new_tabs,
                        password=new_password if new_password else None
                    )
                    st.success(f"✅ Пользователь **{new_username}** создан")
                    st.warning(f"🔑 Пароль (сохрани, показывается один раз): **{pwd}**")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

    st.divider()

    # === ТАБЛИЦА ===
    st.subheader("👥 Пользователи")

    if not users:
        st.info("Нет пользователей")
    else:
        rows = []
        for uname, u in users.items():
            stats = data_loader.get_login_stats(uname)
            last_login = stats.get('last_login') or '—'
            last_ip = stats.get('last_ip') or '—'
            last_status = stats.get('last_status') or '—'
            status_map = {'success': '✅', 'failed': '❌', 'blocked': '🚫'}
            last_status_icon = status_map.get(last_status, '—')

            rows.append({
                'Логин': uname,
                'Имя': u.get('name', ''),
                'Роль': ROLE_LABELS.get(u.get('role', ''), u.get('role', '')),
                'Привязка': u.get('manager_binding') or '—',
                'Вкладки': tabs_to_display(u.get('allowed_tabs', [])),
                'Статус': '🚫 Заблокирован' if u.get('blocked') else '✅ Активен',
                'Последний вход': last_login,
                'IP': last_ip,
                'Вход': last_status_icon,
                'Входов / 30д': stats.get('count_30d', 0),
            })

        df_users = pd.DataFrame(rows)
        st.dataframe(df_users, use_container_width=True, hide_index=True)

    st.divider()

    # === РЕДАКТИРОВАНИЕ ===
    st.subheader("✏️ Редактирование пользователя")

    selected_user = st.selectbox(
        "Выбери пользователя",
        ['—'] + list(users.keys()),
        key="edit_user_select"
    )

    if selected_user != '—':
        u = users[selected_user]
        is_superadmin = (selected_user == 'superadmin')

        col1, col2 = st.columns(2)

        with col1:
            edit_name = st.text_input("Имя", value=u.get('name', ''), key="edit_name")

            if is_superadmin:
                st.text_input("Роль", value='Суперадмин', disabled=True, key="edit_role_display")
                edit_role = 'super_admin'
            else:
                role_idx = ROLE_OPTIONS.index(u.get('role', 'guest')) if u.get('role') in ROLE_OPTIONS else 3
                edit_role = st.selectbox(
                    "Роль",
                    ROLE_OPTIONS,
                    index=role_idx,
                    format_func=lambda r: ROLE_LABELS.get(r, r),
                    key="edit_role"
                )

            managers_list = data_loader.get_available_managers()
            managers_list = [m for m in managers_list if m != 'Все менеджеры']
            binding_options = ['—'] + managers_list
            current_binding = u.get('manager_binding') or '—'
            binding_idx = binding_options.index(current_binding) if current_binding in binding_options else 0

            edit_binding = st.selectbox(
                "Привязка к менеджеру",
                binding_options,
                index=binding_idx,
                key="edit_binding"
            )

        with col2:
            current_tabs = u.get('allowed_tabs', [])
            if 'all' in current_tabs:
                current_tabs = [k for k, _ in USER_TABS]

            edit_tabs = st.multiselect(
                "Доступные вкладки",
                options=[k for k, _ in USER_TABS],
                default=current_tabs,
                format_func=tab_key_to_name,
                key="edit_tabs"
            )

            new_pwd = st.text_input(
                "Новый пароль (оставь пустым — не менять)",
                key="edit_pwd"
            )

        st.markdown("**Действия:**")
        a1, a2, a3 = st.columns([1, 1, 1])

        with a1:
            if st.button("💾 Сохранить", use_container_width=True, key="save_user_btn"):
                try:
                    binding = None if edit_binding == '—' else edit_binding
                    kwargs = {
                        'name': edit_name,
                        'manager_binding': binding,
                        'allowed_tabs': edit_tabs,
                    }
                    if not is_superadmin:
                        kwargs['role'] = edit_role
                    if new_pwd:
                        kwargs['new_password'] = new_pwd

                    data_loader.update_user(selected_user, **kwargs)
                    st.success(f"✅ Пользователь **{selected_user}** обновлён")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

        with a2:
            if is_superadmin:
                st.button("🚫 Блокировать", disabled=True, use_container_width=True, key="block_sa_disabled")
            else:
                is_blocked = u.get('blocked', False)
                btn_label = "✅ Разблокировать" if is_blocked else "🚫 Заблокировать"
                if st.button(btn_label, use_container_width=True, key="toggle_block_btn"):
                    try:
                        data_loader.update_user(selected_user, blocked=not is_blocked)
                        st.success("✅ Статус изменён")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")

        with a3:
            if is_superadmin:
                st.button("🗑 Удалить", disabled=True, use_container_width=True, key="del_sa_disabled")
            else:
                if st.button("🗑 Удалить", use_container_width=True, key="del_user_btn"):
                    st.session_state[f'confirm_delete_{selected_user}'] = True

                if st.session_state.get(f'confirm_delete_{selected_user}'):
                    st.warning(f"Удалить **{selected_user}**? Это необратимо.")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Да, удалить", key="confirm_del_yes", type="primary"):
                            try:
                                data_loader.delete_user(selected_user)
                                st.session_state.pop(f'confirm_delete_{selected_user}', None)
                                st.success(f"✅ Пользователь {selected_user} удалён")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Ошибка: {e}")
                    with cc2:
                        if st.button("Отмена", key="confirm_del_no"):
                            st.session_state.pop(f'confirm_delete_{selected_user}', None)
                            st.rerun()

    st.divider()

    # === СМЕНА ПАРОЛЯ SUPERADMIN ===
    if st.session_state.username == 'superadmin':
        with st.expander("🔑 Сменить пароль суперадмина", expanded=False):
            with st.form("change_sa_pwd_form"):
                pwd1 = st.text_input("Новый пароль", type="password", key="sa_pwd1")
                pwd2 = st.text_input("Повтор пароля", type="password", key="sa_pwd2")
                submitted = st.form_submit_button("Сменить пароль")
            if submitted:
                if not pwd1:
                    st.error("❌ Пароль не может быть пустым")
                elif pwd1 != pwd2:
                    st.error("❌ Пароли не совпадают")
                else:
                    try:
                        data_loader.update_user('superadmin', new_password=pwd1)
                        st.success("✅ Пароль суперадмина изменён")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")

    st.divider()

    # === ЖУРНАЛ ВХОДОВ ===
    st.subheader("📜 Журнал входов (последние 20)")

    try:
        df_hist = data_loader.get_recent_logins(limit=20)
        if not df_hist.empty:
            display = df_hist.copy()
            if 'user_agent' in display.columns:
                display['user_agent'] = display['user_agent'].apply(short_ua)
            cols_order = ['time', 'username', 'status', 'ip', 'user_agent', 'note']
            cols_order = [c for c in cols_order if c in display.columns]
            display = display[cols_order]
            col_names = {
                'time': 'Время', 'username': 'Пользователь', 'status': 'Статус',
                'ip': 'IP', 'user_agent': 'Устройство', 'note': 'Примечание',
            }
            display = display.rename(columns=col_names)
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("Журнал пуст")
    except Exception as e:
        st.error(f"Ошибка чтения журнала: {e}")


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    if not check_auth():
        return

    data = load_data()

    if not data:
        st.error("❌ Не удалось загрузить данные")
        return

    df = data.get('df')
    if df is None or df.empty:
        st.warning("Нет данных для отображения")
        return

    user_role = st.session_state.role
    user_binding = st.session_state.manager_binding
    if user_role in ('manager', 'guest') and user_binding:
        forced_manager = user_binding
    else:
        forced_manager = None

    periods = data_loader.get_period_options(df)
    managers = data_loader.get_available_managers(df)

    # ===== БОКОВАЯ ПАНЕЛЬ =====
    with st.sidebar:
        st.markdown('<p class="main-header">📊 X12.1</p>', unsafe_allow_html=True)

        st.caption(f"👤 {st.session_state.username} ({ROLE_LABELS.get(user_role, user_role)})")

        if user_binding:
            st.caption(f"Привязка: {user_binding}")

        st.divider()

        selected_periods = st.multiselect(
            "📅 Период",
            periods,
            default=['Весь период'],
            key="filter_period"
        )

        if forced_manager is None:
            selected_manager = st.selectbox(
                "👤 Менеджер",
                managers,
                index=0,
                key="filter_manager"
            )
        else:
            selected_manager = forced_manager
            st.info(f"👤 {forced_manager}")

        st.divider()

        if st.button("🔄 Обновить данные", use_container_width=True, key="refresh_btn"):
            st.cache_data.clear()
            st.rerun()

        if st.button("🚪 Выйти", use_container_width=True, key="logout_btn"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.manager_binding = None
            st.session_state.allowed_tabs = []
            st.rerun()

    if not selected_periods:
        selected_periods = ['Весь период']

    period_label = data_loader.get_period_label(selected_periods)

    # ===== ФИЛЬТРАЦИЯ =====
    sales_data = data_loader.filter_sales(df, selected_periods, selected_manager)
    payments_data = data_loader.filter_payments(df, selected_periods, selected_manager)

    # ===== KPI ВЕРХНИЙ РЯД =====
    total_sales = data_loader.get_total_sales(sales_data)
    applications = data_loader.get_applications_count(sales_data)
    companies_count = data_loader.get_companies_count(sales_data)
    avg_check = data_loader.get_avg_check(sales_data)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="metric-box"><h3>💰 ПРОДАЖИ</h3><p>{format_int(total_sales)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-box"><h3>📋 Заявки</h3><p>{format_int(applications)}</p></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-box"><h3>🏢 Хозяйств</h3><p>{format_int(companies_count)}</p></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="metric-box"><h3>📈 Средний чек</h3><p>{format_int(avg_check)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)

    # ===== KPI НИЖНИЙ РЯД =====
    debt_info = data_loader.get_debt_summary(df, selected_periods, selected_manager)
    total_payments = data_loader.get_total_payments(payments_data)
    total_prepayments, prep_count = data_loader.get_total_prepayments(sales_data)

    kk1, kk2, kk3, kk4 = st.columns(4)
    with kk1:
        st.markdown(
            f'<div class="metric-box">'
            f'<h3>💵 ОПЛАТЫ</h3>'
            f'<p>{format_int(total_payments)}</p>'
            f'<h3>BYN</h3>'
            f'<div class="metric-box-sub">'
            f'по текущим: {format_int(debt_info["payments_current"])}<br>'
            f'по старым: {format_int(debt_info["payments_old"])}'
            f'</div></div>',
            unsafe_allow_html=True
        )
    with kk2:
        st.markdown(f'<div class="metric-box"><h3>📊 Дебиторка</h3><p>{format_int(debt_info["debt"])}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
    with kk3:
        st.markdown(f'<div class="metric-box"><h3>📉 % дебиторки</h3><p>{debt_info["percent"]:.2f}%</p></div>', unsafe_allow_html=True)
    with kk4:
        st.markdown(f'<div class="metric-box"><h3>📋 Предсчета</h3><p>{format_int(total_prepayments)}</p><h3>BYN</h3><div class="metric-box-sub">{prep_count} шт.</div></div>', unsafe_allow_html=True)

    st.divider()

    # ===== ДИНАМИКА =====
    st.subheader("📈 Динамика продаж по месяцам")

    df_all = df[(df['row_type'] == 'sale') & (df['order_type'] == 0)].copy()
    df_all = df_all[df_all['invoice_date'].notna()].copy()
    df_all['month'] = df_all['invoice_date'].dt.strftime('%Y-%m')

    total_by_month = df_all.groupby('month')['invoice_amount'].sum().reset_index()
    total_by_month.columns = ['month', 'total_amount']

    if selected_manager != 'Все менеджеры':
        df_mgr = df_all[df_all['manager'] == selected_manager]
        mgr_by_month = df_mgr.groupby('month')['invoice_amount'].sum().reset_index()
        mgr_by_month.columns = ['month', 'mgr_amount']
        merged = pd.merge(total_by_month, mgr_by_month, on='month', how='outer').fillna(0)
    else:
        merged = total_by_month.copy()
        merged['mgr_amount'] = merged['total_amount']

    merged = merged.sort_values('month')
    merged['label'] = merged['month'].apply(
        lambda x: f"{MONTHS_RU[int(x[5:7])]} {x[:4]}" if isinstance(x, str) and len(x) == 7 else ''
    )

    fig = go.Figure()

    if selected_manager != 'Все менеджеры':
        fig.add_trace(go.Scatter(
            x=merged['label'], y=merged['total_amount'],
            mode='lines+markers', name='Все менеджеры',
            line=dict(color='#A7C7E7', width=2), marker=dict(size=6),
            hovertemplate='<b>Все менеджеры</b><br>%{x}<br>%{customdata} BYN<extra></extra>',
            customdata=[format_int(v) for v in merged['total_amount']]
        ))
        fig.add_trace(go.Scatter(
            x=merged['label'], y=merged['mgr_amount'],
            mode='lines+markers', name=selected_manager,
            line=dict(color='#E27D60', width=3), marker=dict(size=8),
            hovertemplate=f'<b>{selected_manager}</b><br>%{{x}}<br>%{{customdata}} BYN<extra></extra>',
            customdata=[format_int(v) for v in merged['mgr_amount']]
        ))
    else:
        fig.add_trace(go.Scatter(
            x=merged['label'], y=merged['total_amount'],
            mode='lines+markers', name='Все менеджеры',
            line=dict(color='#E27D60', width=3), marker=dict(size=8),
            hovertemplate='<b>Все менеджеры</b><br>%{x}<br>%{customdata} BYN<extra></extra>',
            customdata=[format_int(v) for v in merged['total_amount']]
        ))

    fig.update_layout(
        xaxis_title="Месяц",
        yaxis_title="Сумма, BYN",
        yaxis=dict(automargin=True, tickformat=',.0f'),
        margin=dict(l=140, r=20),
        hovermode='x unified',
        plot_bgcolor='#fafafa',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ===== СРАВНЕНИЕ ГОД К ГОДУ =====
    st.subheader("📊 Сравнение год к году")

    monthly = df_all.groupby('month')['invoice_amount'].sum().reset_index()
    monthly.columns = ['month', 'amount']
    monthly['year'] = monthly['month'].str[:4].astype(int)
    monthly['mon'] = monthly['month'].str[5:7].astype(int)
    monthly = monthly[monthly['year'] >= 2025]

    if monthly['year'].nunique() > 1:
        pivot = monthly.pivot_table(index='mon', columns='year', values='amount', aggfunc='sum').reset_index()
        pivot['month_name'] = pivot['mon'].apply(lambda m: MONTHS_RU[m])
        years = sorted([c for c in pivot.columns if isinstance(c, (int,))])
        fig2 = px.bar(
            pivot, x='month_name', y=years, barmode='group',
            labels={'value': 'Сумма, BYN', 'month_name': 'Месяц', 'variable': 'Год'},
            color_discrete_sequence=CONTRAST_PALETTE[:len(years)]
        )
        for i, year in enumerate(years):
            fig2.data[i].customdata = [format_int(v) for v in fig2.data[i].y]
        fig2.update_traces(
            hovertemplate='<b>%{x}</b><br>%{fullData.name}: %{customdata} BYN<extra></extra>'
        )
        fig2.update_layout(
            yaxis=dict(automargin=True, tickformat=',.0f'),
            margin=dict(l=140, r=20)
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Недостаточно данных для сравнения (нужно 2+ года)")

    st.divider()

    # ===== ТОП-3 (всегда по всем менеджерам) =====
    st.subheader("🏆 ТОП-3 менеджера")

    all_sales = data_loader.filter_sales(df, selected_periods, 'Все менеджеры')
    all_payments = data_loader.filter_payments(df, selected_periods, 'Все менеджеры')

    sales_period = all_sales[all_sales['order_type'] == 0]
    by_mgr_sales = sales_period.groupby('manager')['invoice_amount'].sum().reset_index()
    by_mgr_sales.columns = ['manager', 'amount']
    top3_sales = by_mgr_sales.sort_values('amount', ascending=False).head(3)

    by_mgr_payments = all_payments.groupby('manager')['payment_amount'].sum().reset_index()
    by_mgr_payments.columns = ['manager', 'amount']
    top3_payments = by_mgr_payments.sort_values('amount', ascending=False).head(3)

    by_mgr_debt = data_loader.get_debt_by_manager(df, selected_periods)
    top3_debt = by_mgr_debt.sort_values('debt', ascending=False).head(3) if not by_mgr_debt.empty else pd.DataFrame()

    medals = ['🥇', '🥈', '🥉']

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"**Продажи за {period_label}**")
        if not top3_sales.empty:
            for i, (_, row) in enumerate(top3_sales.iterrows()):
                st.markdown(f'<div class="metric-box-small"><h3>{medals[i]} {row["manager"]}</h3><p>{format_int(row["amount"])} BYN</p></div>', unsafe_allow_html=True)
                st.write("")
        else:
            st.info("Нет данных")

    with col2:
        st.markdown(f"**Оплаты за {period_label}**")
        if not top3_payments.empty:
            for i, (_, row) in enumerate(top3_payments.iterrows()):
                st.markdown(f'<div class="metric-box-small"><h3>{medals[i]} {row["manager"]}</h3><p>{format_int(row["amount"])} BYN</p></div>', unsafe_allow_html=True)
                st.write("")
        else:
            st.info("Нет данных")

    with col3:
        st.markdown(f"**Дебиторка за {period_label}**")
        if not top3_debt.empty:
            for i, (_, row) in enumerate(top3_debt.iterrows()):
                st.markdown(f'<div class="metric-box-small"><h3>{medals[i]} {row["manager"]}</h3><p>{format_int(row["debt"])} BYN</p></div>', unsafe_allow_html=True)
                st.write("")
        else:
            st.info("Нет данных")

    st.divider()

    # ===== ТАБЫ =====
    user_tabs = st.session_state.allowed_tabs
    if 'all' in user_tabs:
        visible_user_tabs = USER_TABS
    else:
        visible_user_tabs = [(k, v) for k, v in USER_TABS if k in user_tabs]

    if user_role == 'super_admin':
        visible_tabs = list(visible_user_tabs) + list(ADMIN_TABS)
    else:
        visible_tabs = list(visible_user_tabs)

    if not visible_tabs:
        st.warning("У вас нет доступа ни к одной вкладке. Обратитесь к администратору.")
        return

    tab_objects = st.tabs([v for _, v in visible_tabs])
    tab_map = {k: tab_objects[i] for i, (k, _) in enumerate(visible_tabs)}

    # ===== TAB1: ПРЕДПРИЯТИЯ =====
    if 'tab1' in tab_map:
        with tab_map['tab1']:
            st.subheader("Продажи по предприятиям")
            by_company = data_loader.get_sales_by_company(sales_data)

            if not by_company.empty:
                if selected_manager == 'Все менеджеры':
                    display = by_company[['company', 'raion', 'oblast', 'manager', 'amount']].copy()
                    display.columns = ['Предприятие', 'Район', 'Область', 'Менеджер', 'Сумма, BYN']
                else:
                    display = by_company[['company', 'raion', 'oblast', 'amount']].copy()
                    display.columns = ['Предприятие', 'Район', 'Область', 'Сумма, BYN']

                display['Сумма, BYN'] = display['Сумма, BYN'].apply(format_int)

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(by_company)} предприятий на сумму {format_int(by_company['amount'].sum())} BYN")

                top15 = by_company.head(15).iloc[::-1]
                fig = px.bar(
                    top15, x='amount', y='company', orientation='h',
                    labels={'amount': 'Сумма, BYN', 'company': ''},
                    color='amount', color_continuous_scale='Peach'
                )
                fig.update_traces(
                    hovertemplate='<b>%{y}</b><br>%{customdata} BYN<extra></extra>',
                    customdata=[format_int(v) for v in top15['amount']]
                )
                fig.update_layout(
                    xaxis=dict(automargin=True, tickformat=',.0f'),
                    margin=dict(l=250, r=20),
                    coloraxis_showscale=False,
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет данных")

    # ===== TAB2: РАЙОНЫ =====
    if 'tab2' in tab_map:
        with tab_map['tab2']:
            st.subheader("Продажи по районам")
            by_raion = data_loader.get_sales_by_raion(sales_data)

            if not by_raion.empty:
                color_map = {r: WARM_PALETTE[i % len(WARM_PALETTE)] for i, r in enumerate(by_raion['raion'])}

                display = by_raion.copy()
                display['amount'] = display['amount'].apply(format_int)
                display['share'] = (by_raion['share'] * 100).round(2)
                display = display[['raion', 'amount', 'share']]
                display.columns = ['Район', 'Сумма, BYN', 'Доля, %']

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(by_raion)} районов")

                col1, col2 = st.columns(2)
                with col1:
                    top15 = by_raion.head(15).iloc[::-1].copy()
                    top15['amount_str'] = top15['amount'].apply(format_int)
                    fig = px.bar(
                        top15, x='amount', y='raion', orientation='h',
                        labels={'amount': 'Сумма, BYN', 'raion': ''},
                        color='raion', color_discrete_map=color_map,
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{y}</b><br>%{customdata[0]} BYN<extra></extra>'
                    )
                    fig.update_layout(
                        showlegend=False,
                        xaxis=dict(automargin=True, tickformat=',.0f'),
                        margin=dict(l=200, r=20),
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    pie_data = by_raion.head(10).copy()
                    pie_data['amount_str'] = pie_data['amount'].apply(format_int)
                    fig = px.pie(
                        pie_data, values='amount', names='raion',
                        color='raion', color_discrete_map=color_map,
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{label}</b><br>%{customdata[0]} BYN<br>%{percent}<extra></extra>'
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет данных")

    # ===== TAB3: ОБЛАСТИ =====
    if 'tab3' in tab_map:
        with tab_map['tab3']:
            st.subheader("Продажи по областям")
            by_oblast = data_loader.get_sales_by_oblast(sales_data)

            if not by_oblast.empty:
                color_map = {o: WARM_PALETTE[i % len(WARM_PALETTE)] for i, o in enumerate(by_oblast['oblast'])}

                display = by_oblast.copy()
                display['amount'] = display['amount'].apply(format_int)
                display['share'] = (by_oblast['share'] * 100).round(2)
                display = display[['oblast', 'amount', 'share']]
                display.columns = ['Область', 'Сумма, BYN', 'Доля, %']

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(by_oblast)} областей")

                col1, col2 = st.columns(2)
                with col1:
                    bar_data = by_oblast.copy()
                    bar_data['amount_str'] = bar_data['amount'].apply(format_int)
                    fig = px.bar(
                        bar_data, x='amount', y='oblast', orientation='h',
                        labels={'amount': 'Сумма, BYN', 'oblast': ''},
                        color='oblast', color_discrete_map=color_map,
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{y}</b><br>%{customdata[0]} BYN<extra></extra>'
                    )
                    fig.update_layout(
                        showlegend=False,
                        xaxis=dict(automargin=True, tickformat=',.0f'),
                        margin=dict(l=200, r=20),
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    pie_data = by_oblast.copy()
                    pie_data['amount_str'] = pie_data['amount'].apply(format_int)
                    fig = px.pie(
                        pie_data, values='amount', names='oblast',
                        color='oblast', color_discrete_map=color_map,
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{label}</b><br>%{customdata[0]} BYN<br>%{percent}<extra></extra>'
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет данных")

    # ===== TAB4: ИССЛЕДОВАНИЯ =====
    if 'tab4' in tab_map:
        with tab_map['tab4']:
            st.subheader("Продажи по видам исследований")
            by_research = data_loader.get_sales_by_research(sales_data)

            if not by_research.empty:
                color_map = {r: CONTRAST_PALETTE[i % len(CONTRAST_PALETTE)] for i, r in enumerate(by_research['research_type'])}

                display = by_research.copy()
                display['amount'] = display['amount'].apply(format_int)
                display['share'] = (by_research['share'] * 100).round(2)
                display = display[['research_type', 'amount', 'share']]
                display.columns = ['Вид исследования', 'Сумма, BYN', 'Доля, %']

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(by_research)} видов исследований")

                col1, col2 = st.columns(2)
                with col1:
                    bar_data = by_research.copy()
                    bar_data['amount_str'] = bar_data['amount'].apply(format_int)
                    fig = px.bar(
                        bar_data, x='amount', y='research_type', orientation='h',
                        labels={'amount': 'Сумма, BYN', 'research_type': ''},
                        color='research_type', color_discrete_map=color_map,
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{y}</b><br>%{customdata[0]} BYN<extra></extra>'
                    )
                    fig.update_layout(
                        showlegend=False,
                        xaxis=dict(automargin=True, tickformat=',.0f'),
                        margin=dict(l=280, r=20),
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    pie_data = by_research.copy()
                    pie_data['amount_str'] = pie_data['amount'].apply(format_int)
                    fig = px.pie(
                        pie_data, values='amount', names='research_type',
                        color='research_type', color_discrete_map=color_map,
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{label}</b><br>%{customdata[0]} BYN<br>%{percent}<extra></extra>'
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)

                st.subheader("📈 Динамика исследований по месяцам")
                df_res = df[(df['row_type'] == 'sale') & (df['order_type'] == 0)].copy()
                df_res = df_res[df_res['invoice_date'].notna()]
                df_res['month'] = df_res['invoice_date'].dt.strftime('%Y-%m')
                df_res['label'] = df_res['month'].apply(
                    lambda x: f"{MONTHS_RU[int(x[5:7])]} {x[:4]}" if isinstance(x, str) and len(x) == 7 else ''
                )
                dyn = df_res.groupby(['month', 'label', 'research_type'])['invoice_amount'].sum().reset_index()
                dyn = dyn.sort_values('month')
                fig = px.line(
                    dyn, x='label', y='invoice_amount', color='research_type',
                    labels={'label': 'Месяц', 'invoice_amount': 'Сумма, BYN', 'research_type': 'Исследование'},
                    color_discrete_map=color_map
                )
                fig.update_traces(
                    hovertemplate='<b>%{fullData.name}</b><br>%{x}<br>%{customdata} BYN<extra></extra>',
                    customdata=[format_int(v) for v in dyn['invoice_amount']]
                )
                fig.update_layout(
                    yaxis=dict(automargin=True, tickformat=',.0f'),
                    margin=dict(l=140, r=20)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет данных")

    # ===== TAB5: ДЕБИТОРКА =====
    if 'tab5' in tab_map:
        with tab_map['tab5']:
            st.subheader("💰 Дебиторка")

            debt_info = data_loader.get_debt_summary(df, selected_periods, selected_manager)

            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.markdown(f'<div class="metric-box"><h3>📊 Дебиторка</h3><p>{format_int(debt_info["debt"])}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
            with d2:
                st.markdown(f'<div class="metric-box"><h3>📉 % дебиторки</h3><p>{debt_info["percent"]:.2f}%</p></div>', unsafe_allow_html=True)
            with d3:
                st.markdown(f'<div class="metric-box"><h3>💵 Оплаты</h3><p>{format_int(debt_info["payments"])}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
            with d4:
                st.markdown(f'<div class="metric-box"><h3>🧾 Счета</h3><p>{format_int(debt_info["sales"])}</p><h3>BYN</h3></div>', unsafe_allow_html=True)

            st.divider()

            st.subheader("📊 Структура дебиторки по срокам")
            structure = data_loader.get_debt_structure(df, selected_periods, selected_manager)

            if not structure.empty:
                cat_color_map = {c: STATUS_COLORS.get(c, '#888') for c in structure['category'].astype(str)}

                col1, col2 = st.columns([2, 1])
                with col1:
                    struct_bar = structure.copy()
                    order = ['0-30', '31-60', '61-90', '91-120', '120+']
                    struct_bar['category'] = pd.Categorical(
                        struct_bar['category'], categories=order, ordered=True
                    )
                    struct_bar = struct_bar.sort_values('category')
                    struct_bar['amount_str'] = struct_bar['amount'].apply(format_int)

                    fig = px.bar(
                        struct_bar, x='category', y='amount',
                        labels={'category': 'Срок, дней', 'amount': 'Сумма, BYN'},
                        color='category', color_discrete_map=cat_color_map,
                        category_orders={'category': order},
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{x}</b><br>%{customdata[0]} BYN<extra></extra>'
                    )
                    fig.update_layout(
                        showlegend=False,
                        yaxis=dict(automargin=True, tickformat=',.0f'),
                        margin=dict(l=140, r=20)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    structure_pie = structure.copy()
                    fig = px.pie(
                        structure_pie, values='amount', names='category',
                        color='category', color_discrete_map=cat_color_map,
                        category_orders={'category': ['0-30', '31-60', '61-90', '91-120', '120+']}
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{label}</b><br>%{value:,.0f} BYN<br>%{percent}<extra></extra>',
                        sort=False
                    )
                    st.plotly_chart(fig, use_container_width=True)

                summary_display = structure.copy()
                summary_display['amount'] = summary_display['amount'].apply(format_int)
                summary_display = summary_display[['category', 'amount', 'count']]
                summary_display.columns = ['Категория', 'Сумма, BYN', 'Кол-во счетов']
                st.dataframe(summary_display, use_container_width=True, hide_index=True)
            else:
                st.info("Нет дебиторки за выбранный период")

            st.divider()

            if selected_manager == 'Все менеджеры':
                st.subheader("👥 Дебиторка по менеджерам")
                by_mgr = data_loader.get_debt_by_manager(df, selected_periods)
                if not by_mgr.empty:
                    display = by_mgr.copy()
                    display['sales'] = display['sales'].apply(format_int)
                    display['payments'] = display['payments'].apply(format_int)
                    display['debt'] = display['debt'].apply(format_int)
                    display['percent'] = display['percent'].round(2)
                    display['debt_share'] = display['debt_share'].round(2)
                    display = display[['manager', 'sales', 'payments', 'debt', 'percent', 'debt_share']]
                    display.columns = ['Менеджер', 'Счета, BYN', 'Оплаты, BYN', 'Дебиторка, BYN', '%', 'Доля в общей, %']
                    st.dataframe(display, use_container_width=True, hide_index=True)

                    debt_positive = by_mgr[by_mgr['debt'] > 0]
                    if not debt_positive.empty:
                        fig = px.pie(
                            debt_positive,
                            values='debt', names='manager',
                            color='manager',
                            color_discrete_sequence=CONTRAST_PALETTE
                        )
                        fig.update_traces(
                            hovertemplate='<b>%{label}</b><br>%{customdata} BYN<br>%{percent}<extra></extra>',
                            customdata=[format_int(v) for v in debt_positive['debt']]
                        )
                        st.plotly_chart(fig, use_container_width=True)
                st.divider()

            st.subheader("🏢 Предприятия с дебиторкой")
            companies_debt = data_loader.get_debt_companies(df, selected_periods, selected_manager)

            if not companies_debt.empty:
                display = companies_debt.copy()
                for col in ['0-30', '31-60', '61-90', '91-120', '120+', 'total_debt']:
                    if col in display.columns:
                        display[col] = display[col].apply(format_int)

                cols_order = ['company', 'manager', 'total_debt', '0-30', '31-60', '61-90', '91-120', '120+']
                cols_order = [c for c in cols_order if c in display.columns]
                display = display[cols_order]
                display.columns = ['Предприятие', 'Менеджер', 'Итого, BYN',
                                   '0-30 дн.', '31-60 дн.', '61-90 дн.', '91-120 дн.', '>120 дн.'][:len(cols_order)]

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(companies_debt)} предприятий")

                top15 = companies_debt.head(15).iloc[::-1]
                fig = px.bar(
                    top15, x='total_debt', y='company', orientation='h',
                    labels={'total_debt': 'Сумма, BYN', 'company': ''},
                    color='total_debt', color_continuous_scale='Reds'
                )
                fig.update_traces(
                    hovertemplate='<b>%{y}</b><br>%{customdata} BYN<extra></extra>',
                    customdata=[format_int(v) for v in top15['total_debt']]
                )
                fig.update_layout(
                    xaxis=dict(automargin=True, tickformat=',.0f'),
                    margin=dict(l=250, r=20),
                    coloraxis_showscale=False,
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет предприятий с дебиторкой за выбранный период")

    # ===== TAB6: ОПЛАТЫ =====
    if 'tab6' in tab_map:
        with tab_map['tab6']:
            st.subheader("💵 Оплаты")

            bonus_settings = data_loader.get_bonus_settings()

            payments_structure = data_loader.get_payments_structure(df, selected_periods, selected_manager)
            total_payments = payments_structure['amount'].sum() if not payments_structure.empty else 0

            debt_info_pay = data_loader.get_debt_summary(df, selected_periods, selected_manager)

            p1, p2, p3, p4 = st.columns(4)
            with p1:
                st.markdown(f'<div class="metric-box"><h3>💵 ОПЛАТЫ</h3><p>{format_int(total_payments)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
            with p2:
                st.markdown(f'<div class="metric-box"><h3>📋 По текущим</h3><p>{format_int(debt_info_pay["payments_current"])}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
            with p3:
                st.markdown(f'<div class="metric-box"><h3>📋 По старым</h3><p>{format_int(debt_info_pay["payments_old"])}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
            with p4:
                by_mgr_pay = data_loader.get_payments_by_manager(df, selected_periods, bonus_settings)
                if not by_mgr_pay.empty:
                    if selected_manager == 'Все менеджеры':
                        total_bonus = by_mgr_pay['bonus'].sum()
                    else:
                        mgr_row = by_mgr_pay[by_mgr_pay['manager'] == selected_manager]
                        total_bonus = mgr_row['bonus'].sum() if not mgr_row.empty else 0
                else:
                    total_bonus = 0
                st.markdown(f'<div class="metric-box"><h3>🎁 Бонус</h3><p>{format_int(total_bonus)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)

            st.divider()

            st.subheader("📊 Структура оплат по срокам дебиторки")

            if not payments_structure.empty:
                cat_color_map = {c: STATUS_COLORS.get(c, '#888') for c in payments_structure['category'].astype(str)}
                order = ['0-30', '31-60', '61-90', '91-120', '120+']

                col1, col2 = st.columns([2, 1])
                with col1:
                    struct_bar = payments_structure.copy()
                    struct_bar['category'] = pd.Categorical(struct_bar['category'], categories=order, ordered=True)
                    struct_bar = struct_bar.sort_values('category')
                    struct_bar['amount_str'] = struct_bar['amount'].apply(format_int)

                    fig = px.bar(
                        struct_bar, x='category', y='amount',
                        labels={'category': 'Категория дебиторки', 'amount': 'Сумма, BYN'},
                        color='category', color_discrete_map=cat_color_map,
                        category_orders={'category': order},
                        custom_data=['amount_str']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{x}</b><br>%{customdata[0]} BYN<extra></extra>'
                    )
                    fig.update_layout(
                        showlegend=False,
                        yaxis=dict(automargin=True, tickformat=',.0f'),
                        margin=dict(l=140, r=20)
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    struct_sorted = payments_structure.copy()
                    struct_sorted['category'] = pd.Categorical(struct_sorted['category'], categories=order, ordered=True)
                    struct_sorted = struct_sorted.sort_values('category')

                    labels = struct_sorted['category'].astype(str).tolist()
                    values = struct_sorted['amount'].tolist()
                    hover_texts = [f"{format_int(v)} BYN" for v in values]
                    colors = [cat_color_map.get(c, '#888') for c in labels]

                    fig = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=values,
                        marker=dict(colors=colors),
                        hovertext=hover_texts,
                        hovertemplate='<b>%{label}</b><br>%{hovertext}<br>%{percent}<extra></extra>',
                        sort=False,
                        textinfo='label+percent',
                    )])
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                display = payments_structure.copy()
                display['amount'] = display['amount'].apply(format_int)
                display = display[['category', 'amount', 'count']]
                display.columns = ['Категория дебиторки', 'Оплаты, BYN', 'Кол-во']
                st.dataframe(display, use_container_width=True, hide_index=True)
            else:
                st.info("Нет оплат за выбранный период")

            st.divider()

            st.subheader("👥 Оплаты по менеджерам")

            by_mgr_pay = data_loader.get_payments_by_manager(df, selected_periods, bonus_settings)
            if not by_mgr_pay.empty:
                display = by_mgr_pay.copy()
                display['payments'] = display['payments'].apply(format_int)
                display['bonus'] = display['bonus'].apply(format_int)
                display['share'] = display['share'].round(2)
                display = display[['manager', 'payments', 'share', 'bonus', 'count']]
                display.columns = ['Менеджер', 'Оплаты, BYN', 'Доля, %', 'Бонус, BYN', 'Кол-во оплат']
                st.dataframe(display, use_container_width=True, hide_index=True)

                pie_data = by_mgr_pay[by_mgr_pay['payments'] > 0].copy()
                fig = px.pie(
                    pie_data,
                    values='payments', names='manager',
                    color='manager',
                    color_discrete_sequence=CONTRAST_PALETTE
                )
                fig.update_traces(
                    hovertemplate='<b>%{label}</b><br>%{value:,.0f} BYN<br>%{percent}<extra></extra>'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет данных")

            st.divider()

            if selected_manager == 'Все менеджеры':
                st.subheader("📊 Оплаты по менеджерам и категориям")
                by_mgr_cat = data_loader.get_payments_by_manager_and_category(df, selected_periods)
                if not by_mgr_cat.empty:
                    display = by_mgr_cat.copy()
                    for col in ['0-30', '31-60', '61-90', '91-120', '120+']:
                        if col in display.columns:
                            display[col] = display[col].apply(format_int)
                    display.columns = ['Менеджер', '0-30', '31-60', '61-90', '91-120', '120+']
                    st.dataframe(display, use_container_width=True, hide_index=True)
                st.divider()

            st.subheader("🏢 Предприятия с оплатами")
            companies_pay = data_loader.get_payments_companies(df, selected_periods, selected_manager, bonus_settings)

            if not companies_pay.empty:
                display = companies_pay.copy()
                for col in ['0-30', '31-60', '61-90', '91-120', '120+', 'total_payments', 'total_bonus']:
                    if col in display.columns:
                        display[col] = display[col].apply(format_int)

                cols_order = ['company', 'manager', 'total_payments', '0-30', '31-60', '61-90', '91-120', '120+', 'total_bonus']
                cols_order = [c for c in cols_order if c in display.columns]
                display = display[cols_order]
                display.columns = ['Предприятие', 'Менеджер', 'Итого, BYN',
                                   '0-30', '31-60', '61-90', '91-120', '>120', 'Бонус, BYN'][:len(cols_order)]

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(companies_pay)} предприятий")
            else:
                st.info("Нет оплат за выбранный период")

            st.divider()

            st.subheader("⚙️ Настройки бонусов")

            bonus_settings = data_loader.get_bonus_settings()

            col_chk1, col_chk2 = st.columns(2)
            with col_chk1:
                use_by_category = st.checkbox(
                    "Использовать бонус по категориям дебиторки",
                    value=bonus_settings.get('use_by_category', False),
                    key="use_by_category"
                )
            with col_chk2:
                use_by_threshold = st.checkbox(
                    "Использовать бонус по порогу оплат",
                    value=bonus_settings.get('use_by_threshold', False),
                    key="use_by_threshold"
                )

            if use_by_category:
                st.markdown("**Ставки по категориям дебиторки**")
                rates = bonus_settings.get('rates_by_category', {})
                rc1, rc2, rc3, rc4, rc5 = st.columns(5)
                with rc1:
                    r_0_30 = st.number_input("0-30 дн., %", value=float(rates.get('0-30', 0.0)), step=0.1, format="%.2f", key="r_0_30")
                with rc2:
                    r_31_60 = st.number_input("31-60 дн., %", value=float(rates.get('31-60', 0.0)), step=0.1, format="%.2f", key="r_31_60")
                with rc3:
                    r_61_90 = st.number_input("61-90 дн., %", value=float(rates.get('61-90', 0.0)), step=0.1, format="%.2f", key="r_61_90")
                with rc4:
                    r_91_120 = st.number_input("91-120 дн., %", value=float(rates.get('91-120', 0.0)), step=0.1, format="%.2f", key="r_91_120")
                with rc5:
                    r_120 = st.number_input("120+ дн., %", value=float(rates.get('120+', 0.0)), step=0.1, format="%.2f", key="r_120")
            else:
                r_0_30 = r_31_60 = r_61_90 = r_91_120 = r_120 = 0.0

            if use_by_threshold:
                st.markdown("**Пороги оплат и ставки**")
                thr = bonus_settings.get('thresholds', [
                    {'min_amount': 20000, 'rate': 0.0},
                    {'min_amount': 30000, 'rate': 0.0},
                    {'min_amount': 50000, 'rate': 0.0},
                ])
                while len(thr) < 3:
                    thr.append({'min_amount': 0, 'rate': 0.0})

                tc1, tc2, tc3 = st.columns(3)
                with tc1:
                    t1_amount = st.number_input("Порог 1, BYN", value=float(thr[0].get('min_amount', 0)), step=1000.0, format="%.0f", key="t1_amount")
                    t1_rate = st.number_input("Ставка 1, %", value=float(thr[0].get('rate', 0.0)), step=0.1, format="%.2f", key="t1_rate")
                with tc2:
                    t2_amount = st.number_input("Порог 2, BYN", value=float(thr[1].get('min_amount', 0)), step=1000.0, format="%.0f", key="t2_amount")
                    t2_rate = st.number_input("Ставка 2, %", value=float(thr[1].get('rate', 0.0)), step=0.1, format="%.2f", key="t2_rate")
                with tc3:
                    t3_amount = st.number_input("Порог 3, BYN", value=float(thr[2].get('min_amount', 0)), step=1000.0, format="%.0f", key="t3_amount")
                    t3_rate = st.number_input("Ставка 3, %", value=float(thr[2].get('rate', 0.0)), step=0.1, format="%.2f", key="t3_rate")
            else:
                t1_amount = t2_amount = t3_amount = 0.0
                t1_rate = t2_rate = t3_rate = 0.0

            if st.button("💾 Сохранить настройки бонусов", key="save_bonus_settings_btn"):
                new_settings = {
                    'use_by_category': use_by_category,
                    'use_by_threshold': use_by_threshold,
                    'rates_by_category': {
                        '0-30': r_0_30,
                        '31-60': r_31_60,
                        '61-90': r_61_90,
                        '91-120': r_91_120,
                        '120+': r_120,
                    },
                    'thresholds': [
                        {'min_amount': t1_amount, 'rate': t1_rate},
                        {'min_amount': t2_amount, 'rate': t2_rate},
                        {'min_amount': t3_amount, 'rate': t3_rate},
                    ],
                }
                if data_loader.save_bonus_settings(new_settings):
                    st.success("✅ Настройки бонусов сохранены в Google Sheets")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Не удалось сохранить настройки")

    # ===== TAB_ACCESS =====
    if 'tab_access' in tab_map:
        with tab_map['tab_access']:
            render_access_tab()


if __name__ == "__main__":
    main()