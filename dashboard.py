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

# Запрет Google Переводчик переводить страницу
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

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

    /* Скрываем кнопки экспорта и toolbar у таблиц */
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
    ('tab0', "📋 План"),
    ('tab1', "🏢 Предприятия"),
    ('tab2', "📍 Районы"),
    ('tab3', "🗺️ Области"),
    ('tab4', "🔬 Исследования"),
    ('tab5', "💰 Дебиторка"),
    ('tab6', "💵 Оплаты"),
    ('tab7', "📋 Предсчета"),
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


    # === НАСТРОЙКА ПЛАНОВ (админ + суперадмин) ===
    admin_settings_plans = data_loader.get_admin_settings()
    can_edit_plans = (
        st.session_state.role == 'super_admin' or
        (st.session_state.role == 'admin' and admin_settings_plans.get('allow_admins_plans_edit', True))
    )

    if can_edit_plans:
        st.divider()

        with st.expander("📋 Настройка планов", expanded=False):
            st.caption("Установите планы продаж. Пустое или 0 — план не задан.")

            plans_settings = data_loader.get_plans_settings()
            plans = plans_settings.get('plans', {})
            enabled_plans = plans_settings.get('enabled_plans', [])

            new_plans = {}
            new_enabled = []

            for key, label, unit in data_loader.PLAN_CATEGORIES:
                col_chk, col_val = st.columns([1, 3])
                with col_chk:
                    enabled = st.checkbox(
                        label,
                        value=(key in enabled_plans),
                        key=f"access_plan_chk_{key}"
                    )
                with col_val:
                    val = st.number_input(
                        f"{unit}",
                        value=float(plans.get(key, 0.0)),
                        min_value=0.0,
                        step=1000.0 if unit == 'BYN' else 1.0,
                        format="%.2f" if unit == 'BYN' else "%.0f",
                        key=f"access_plan_val_{key}",
                        label_visibility="collapsed"
                    )
                if enabled:
                    new_enabled.append(key)
                    new_plans[key] = val

            if st.button("💾 Сохранить планы", key="access_save_plans_btn", type="primary"):
                new_settings = dict(plans_settings)
                new_settings['plans'] = new_plans
                new_settings['enabled_plans'] = new_enabled

                if data_loader.save_plans_settings(new_settings):
                    st.success("✅ Планы сохранены")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Не удалось сохранить планы")


    # === РАЗРЕШЕНИЯ ДЛЯ АДМИНОВ (только суперадмин) ===
    if st.session_state.role == 'super_admin':
        st.divider()

        with st.expander("🔐 Разрешения для админов", expanded=False):
            st.caption("Управление правами администраторов. "
                       "Если опция выключена — соответствующий блок скрыт от админов.")

            admin_settings = data_loader.get_admin_settings()

            # Права на метки
            st.markdown("**🏷️ Метки предприятий**")
            c1, c2 = st.columns(2)
            with c1:
                new_allow_blacklist = st.checkbox(
                    "💀 ЧС — админы могут ставить/снимать",
                    value=admin_settings.get('allow_admins_blacklist', True),
                    key="res_allow_blacklist"
                )
            with c2:
                new_allow_golden = st.checkbox(
                    "🏆 Золото — админы могут ставить/снимать",
                    value=admin_settings.get('allow_admins_golden', True),
                    key="res_allow_golden"
                )

            st.divider()

            # Права на сроки и пороги
            st.markdown("**⚙️ Настройки**")
            c3, c4 = st.columns(2)
            with c3:
                new_allow_trust = st.checkbox(
                    "💰 Пороги TrustLimits + Дебиторка",
                    value=admin_settings.get('allow_admins_trust_limits', True),
                    key="res_allow_trust"
                )
                new_allow_status = st.checkbox(
                    "🔄 Сроки статусов + Предсчёт",
                    value=admin_settings.get('allow_admins_status_days', True),
                    key="res_allow_status"
                )
            with c4:
                new_allow_inactive = st.checkbox(
                    "⏰ Срок метки «Нет заявок»",
                    value=admin_settings.get('allow_admins_inactive_days', True),
                    key="res_allow_inactive"
                )
                new_allow_potential = st.checkbox(
                    "🤝 Срок метки «Потенциальное»",
                    value=admin_settings.get('allow_admins_potential_days', True),
                    key="res_allow_potential"
                )

            st.divider()


            # Прочие настройки
            st.markdown("**⚙️ Прочие настройки**")
            new_allow_bonus = st.checkbox(
                "💰 Настройки бонусов — админы могут менять",
                value=admin_settings.get('allow_admins_bonus_settings', True),
                key="res_allow_bonus"
            )
            new_allow_plans = st.checkbox(
                "📋 Настройка планов — админы могут менять",
                value=admin_settings.get('allow_admins_plans_edit', True),
                key="res_allow_plans"
            )

            # Видимость
            st.markdown("**👁️ Видимость**")
            new_show_trust = st.checkbox(
                "⚠️ Показывать «Превышение лимита доверия» всем",
                value=admin_settings.get('show_trust_limits', True),
                key="res_show_trust"
            )

            if st.button("💾 Сохранить разрешения", key="save_resolutions", type="primary"):
                new_settings = dict(admin_settings)
                new_settings['allow_admins_blacklist'] = new_allow_blacklist
                new_settings['allow_admins_golden'] = new_allow_golden
                new_settings['allow_admins_trust_limits'] = new_allow_trust
                new_settings['allow_admins_status_days'] = new_allow_status
                new_settings['allow_admins_inactive_days'] = new_allow_inactive
                new_settings['allow_admins_potential_days'] = new_allow_potential
                new_settings['allow_admins_bonus_settings'] = new_allow_bonus
                new_settings['allow_admins_plans_edit'] = new_allow_plans
                new_settings['show_trust_limits'] = new_show_trust

                if data_loader.save_admin_settings(new_settings):
                    st.success("✅ Разрешения сохранены")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Не удалось сохранить")


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

@st.fragment
def render_potential_manager(summary, admin_settings, selected_manager):
    """Expander управления статусом «Потенциальный» через data_editor."""
    with st.expander("🎯 Управление статусом «Потенциальный»", expanded=False):
        st.caption("Статус «Потенциальный» — для предприятий, с которыми ведём переговоры. "
                   "Доступен менеджерам для своих предприятий, админам — для всех.")

        current_user = st.session_state.username
        current_role = st.session_state.role
        user_binding = st.session_state.manager_binding

        can_manage = current_role in ('super_admin', 'admin') or (current_role == 'manager' and user_binding)

        if not can_manage:
            st.info("Управление статусом доступно менеджерам (для своих предприятий) и админам.")
            return

        if current_role in ('admin', 'super_admin'):
            selected_filter_manager = selected_manager
        else:
            selected_filter_manager = user_binding

        flags = data_loader.load_company_flags() or {}

        rows = []
        for code, m in summary.items():
            if selected_filter_manager != 'Все менеджеры':
                if m.get('manager') != selected_filter_manager:
                    continue

            flag = flags.get(code, {})
            if flag.get('blacklist'):
                continue

            is_potential = flag.get('status') == 'potential'
            status_date = flag.get('status_date', '')
            days_in_status = data_loader.get_potential_days(status_date) if is_potential else 0

            rows.append({
                'code': code,
                'name': m.get('company_name', ''),
                'manager': m.get('manager', ''),
                'is_potential': is_potential,
                'days': days_in_status,
            })

        if not rows:
            st.info("Нет предприятий для управления.")
            return

        df = pd.DataFrame(rows)
        df = df.sort_values('code')

        warning_days = admin_settings.get('potential_warning_days', 90)

        # Формируем отображаемый DataFrame
        display = pd.DataFrame({
            'Код': df['code'],
            'Название': df['name'],
            'Менеджер': df['manager'],
            'Статус': df.apply(
                lambda r: f"🤝 {r['days']} дн." + (" ⚠️" if r['days'] > warning_days else "")
                if r['is_potential'] else "⬜ —",
                axis=1
            ),
            'Потенциальный': df['is_potential'],
        })

        st.caption(f"Всего: {len(display)} предприятий. "
                   f"Отметьте 🤝 напротив нужных и нажмите «Применить».")

        edited = st.data_editor(
            display,
            use_container_width=True,
            hide_index=True,
            disabled=['Код', 'Название', 'Менеджер', 'Статус'],
            column_config={
                'Потенциальный': st.column_config.CheckboxColumn(
                    "Поставить 🤝",
                    help="Отметьте, чтобы поставить статус «Потенциальный»",
                    default=False,
                ),
            },
            key="potential_editor",
        )

        if st.button("💾 Применить изменения", key="apply_potential_changes", type="primary"):
            changed = 0
            errors = []

            for i, row in edited.iterrows():
                original = display.iloc[i]['Потенциальный']
                new_val = row['Потенциальный']

                if original == new_val:
                    continue

                code = row['Код']

                try:
                    if new_val:
                        data_loader.set_company_potential(
                            code,
                            manager_binding=selected_filter_manager,
                            added_by=current_user
                        )
                        changed += 1
                    else:
                        data_loader.remove_company_potential(code)
                        changed += 1
                except Exception as e:
                    errors.append(f"{code}: {e}")

            st.cache_data.clear()

            if changed:
                st.session_state['pot_msg'] = f"✅ Изменено: {changed}"
            if errors:
                st.session_state['pot_err'] = f"❌ Ошибки: {'; '.join(errors)}"

            st.rerun()


@st.fragment
def render_metki_editor(summary, selected_manager, can_edit_blacklist, can_edit_golden):
    """Блок редактирования меток предприятий (💀, 🏆) через selectbox + radio."""
    st.markdown("**🏷️ Метки предприятий**")

    primary_map = data_loader.get_primary_manager_by_raion(summary)
    flags = data_loader.load_company_flags() or {}

    # Поиск
    query = st.text_input(
        "🔍 Поиск по коду или названию",
        key="admin_settings_search",
        placeholder="Например: Кухчицы или 146"
    )

    # Формируем список предприятий (с фильтрами)
    filtered = []
    for code, m in summary.items():
        primary = primary_map.get(code, '—')
        managers_set = m.get('managers_set', set())

        # Фильтр по менеджеру (из сайдбара)
        if selected_manager != 'Все менеджеры':
            if selected_manager != primary and selected_manager not in managers_set:
                continue

        # Фильтр по поиску
        if query:
            q = query.lower()
            name = (m.get('company_name') or '').lower()
            if q not in code.lower() and q not in name:
                continue

        mgr_display = data_loader.format_managers_display(primary, managers_set)

        filtered.append({
            'code': code,
            'name': m.get('company_name') or '',
            'raion': m.get('raion') or '',
            'manager': mgr_display,
        })

    if not filtered:
        st.info("Нет предприятий для отображения (проверь фильтры)")
        return

    st.caption(f"Всего: {len(filtered)} предприятий")

    # Selectbox с предприятием
    options = [f"{r['code']} — {r['name']}" for r in filtered]
    selected_display = st.selectbox(
        "Выбери предприятие",
        options,
        key="admin_settings_company"
    )

    # Извлекаем код
    selected_code = selected_display.split(' — ')[0].strip()

    # Находим запись
    selected = next((r for r in filtered if r['code'] == selected_code), None)
    if not selected:
        return

    # Информация о предприятии
    st.markdown(f"**Район:** {selected['raion']}")
    st.markdown(f"**Менеджер:** {selected['manager']}")

    # Текущие метки
    flag = flags.get(selected_code, {})
    current_blacklist = flag.get('blacklist', False)
    current_golden = flag.get('golden_fund', False)

    # Радио: взаимоисключение
    if current_blacklist:
        default_idx = 1  # ЧС
    elif current_golden:
        default_idx = 2  # Золото
    else:
        default_idx = 0  # Нет

    metka = st.radio(
        "Метка",
        options=['—', '💀 ЧС', '🏆 Золото'],
        index=default_idx,
        key=f"admin_settings_metka_{selected_code}",
        horizontal=True,
    )

    st.caption("Выбери метку и нажми «💾 Сохранить метку».")

    if st.button("💾 Сохранить метку", key=f"save_metka_{selected_code}", type="primary"):
        flags_to_save = data_loader.load_company_flags() or {}
        if selected_code not in flags_to_save:
            flags_to_save[selected_code] = {
                'company_name': selected['name'],
                'date_added': datetime.now().strftime('%Y-%m-%d'),
                'added_by': st.session_state.username,
            }

        if metka == '💀 ЧС':
            flags_to_save[selected_code]['blacklist'] = True
            flags_to_save[selected_code]['golden_fund'] = False
        elif metka == '🏆 Золото':
            flags_to_save[selected_code]['blacklist'] = False
            flags_to_save[selected_code]['golden_fund'] = True
        else:
            flags_to_save[selected_code]['blacklist'] = False
            flags_to_save[selected_code]['golden_fund'] = False

        if data_loader.save_company_flags(flags_to_save):
            st.success(f"✅ Метка сохранена: {selected_code} — {metka}")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("❌ Не удалось сохранить метку")


def render_plan_tab(df, summary, selected_periods, selected_manager, user_role):
    """Вкладка «📋 План»."""

    # === ОПРЕДЕЛЯЕМ МЕСЯЦ ===
    MONTHS_RU_REVERSE = {
        'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
        'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
        'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12,
    }

    month_year = None
    if selected_periods and 'Весь период' not in selected_periods:
        # Ищем месяц (например, '2026 сентябрь')
        for p in selected_periods:
            if ' ' in p and p.startswith('2026 '):
                month_ru = p.replace('2026 ', '').strip()
                m = MONTHS_RU_REVERSE.get(month_ru)
                if m:
                    month_year = (2026, m)
                    break

        # Если выбран только год ('2026') — берём последний месяц с данными
        if month_year is None:
            only_year = any(p.isdigit() and len(p) == 4 for p in selected_periods)
            if only_year:
                sales_all = df[(df['row_type'] == 'sale') & (df['order_type'] == 0)]
                if not sales_all.empty:
                    last_date = sales_all['invoice_date'].max()
                    if last_date is not None and hasattr(last_date, 'year'):
                        month_year = (last_date.year, last_date.month)

    # Если период не выбран / «Весь период» → текущий месяц
    if month_year is None:
        now = datetime.now()
        month_year = (now.year, now.month)

    year, month = month_year
    month_label = f"{MONTHS_RU[month]} {year}"

    st.subheader("📋 План продаж")
    st.caption(f"Период: **{month_label}**")

    # === НАСТРОЙКИ ПЛАНОВ ===
    plans_settings = data_loader.get_plans_settings()
    plans = plans_settings.get('plans', {})
    enabled_plans = plans_settings.get('enabled_plans', [])

    # === ФАКТ ===
    plan_summary = data_loader.get_plan_summary(df, summary, month_year=month_year)

    if plan_summary.empty:
        st.info("Нет данных за выбранный период")
        return

    # Фильтр по менеджеру
    if selected_manager != 'Все менеджеры':
        plan_summary = plan_summary[plan_summary['manager'] == selected_manager]
        if plan_summary.empty:
            st.info(f"Нет данных для менеджера {selected_manager}")
            return

    # === KPI ПО ПРОДАЖАМ ===
    # Если выбран конкретный — берём его. Иначе — строку «Все менеджеры».
    if selected_manager == 'Все менеджеры':
        total_row = plan_summary[plan_summary['manager'] == 'Все менеджеры']
    else:
        total_row = plan_summary  # только одна строка

    # Количество менеджеров для общего плана
    if selected_manager == 'Все менеджеры':
        n_managers = len([m for m in data_loader.ACTIVE_MANAGERS if m != 'Все менеджеры'])
    else:
        n_managers = 1

    # === ПЛАН / ФАКТ ПО ПРОДАЖАМ ===
    plan_sales = plans.get('sales', 0.0) * n_managers
    fact_sales = float(total_row['sales'].iloc[0]) if not total_row.empty else 0.0

    if plan_sales > 0:
        percent_sales = fact_sales / plan_sales * 100
        remainder_sales = plan_sales - fact_sales
    else:
        percent_sales = None
        remainder_sales = 0.0

    # === ПЛАН / ФАКТ ПО ОПЛАТАМ ===
    plan_payments = plans.get('payments', 0.0) * n_managers
    fact_payments = float(total_row['payments'].iloc[0]) if not total_row.empty else 0.0

    if plan_payments > 0:
        percent_payments = fact_payments / plan_payments * 100
        remainder_payments = plan_payments - fact_payments
    else:
        percent_payments = None
        remainder_payments = 0.0

    # === KPI ПРОДАЖИ ===
    st.markdown("**💰 Продажи**")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="metric-box"><h3>💰 План</h3><p>{format_int(plan_sales)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-box"><h3>💵 Факт</h3><p>{format_int(fact_sales)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
    with k3:
        if percent_sales is None:
            st.markdown(f'<div class="metric-box"><h3>📊 Выполнение</h3><p>—</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-box"><h3>📊 Выполнение</h3><p>{percent_sales:.1f}%</p></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="metric-box"><h3>📉 Остаток</h3><p>{format_int(max(0, remainder_sales))}</p><h3>BYN</h3></div>', unsafe_allow_html=True)

    # === KPI ОПЛАТЫ ===
    st.markdown("**💵 Оплаты**")
    kk1, kk2, kk3, kk4 = st.columns(4)
    with kk1:
        st.markdown(f'<div class="metric-box"><h3>💰 План</h3><p>{format_int(plan_payments)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
    with kk2:
        st.markdown(f'<div class="metric-box"><h3>💵 Факт</h3><p>{format_int(fact_payments)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
    with kk3:
        if percent_payments is None:
            st.markdown(f'<div class="metric-box"><h3>📊 Выполнение</h3><p>—</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-box"><h3>📊 Выполнение</h3><p>{percent_payments:.1f}%</p></div>', unsafe_allow_html=True)
    with kk4:
        st.markdown(f'<div class="metric-box"><h3>📉 Остаток</h3><p>{format_int(max(0, remainder_payments))}</p><h3>BYN</h3></div>', unsafe_allow_html=True)

    st.divider()

    # === ТРИ ТАБЛИЦЫ: ФАКТ / ПЛАН / % ===
    st.subheader("📋 План по менеджерам")

    # Собираем данные: {manager: {key: fact}}
    managers_list = plan_summary['manager'].tolist()

    # Категории (только включённые)
    active_cats = [(k, l, u) for k, l, u in data_loader.PLAN_CATEGORIES if k in enabled_plans]

    # ФАКТ
    fact_data = {'Категория': [label for _, label, _ in active_cats]}
    for mgr in managers_list:
        mgr_row = plan_summary[plan_summary['manager'] == mgr]
        if mgr_row.empty:
            continue
        r = mgr_row.iloc[0]
        fact_data[mgr] = [format_int(r.get(key, 0)) for key, _, _ in active_cats]
    df_fact = pd.DataFrame(fact_data)

    # ПЛАН
    plan_data = {'Категория': [label for _, label, _ in active_cats]}
    for mgr in managers_list:
        plan_data[mgr] = [format_int(plans.get(key, 0)) for key, _, _ in active_cats]
    df_plan = pd.DataFrame(plan_data)

    # %
    pct_data = {'Категория': [label for _, label, _ in active_cats]}
    for mgr in managers_list:
        mgr_row = plan_summary[plan_summary['manager'] == mgr]
        if mgr_row.empty:
            continue
        r = mgr_row.iloc[0]
        pcts = []
        for key, _, _ in active_cats:
            fact = float(r.get(key, 0))
            plan = float(plans.get(key, 0))
            if plan > 0:
                pcts.append(f"{fact / plan * 100:.0f}%")
            else:
                pcts.append("—")
        pct_data[mgr] = pcts
    df_pct = pd.DataFrame(pct_data)

    # Отображение — три таблицы
    st.markdown("**Факт**")
    st.dataframe(df_fact, use_container_width=True, hide_index=True)

    st.markdown("**План**")
    st.dataframe(df_plan, use_container_width=True, hide_index=True)

    st.markdown("**% выполнения**")
    st.dataframe(df_pct, use_container_width=True, hide_index=True)

    st.divider()

    # === ПРОГРЕСС-БАРЫ ПО КАТЕГОРИЯМ ===
    st.subheader("📊 Выполнение по категориям")

    if total_row.empty:
        st.info("Нет данных")
    else:
        t = total_row.iloc[0]
        for key, label, unit in data_loader.PLAN_CATEGORIES:
            if key not in enabled_plans:
                continue
            fact = float(t.get(key, 0))
            plan = float(plans.get(key, 0))
            if plan <= 0:
                continue
            pct = fact / plan * 100
            if pct >= 100:
                color = "🟢"
            elif pct >= 50:
                color = "🟡"
            else:
                color = "🔴"
            st.markdown(f"**{color} {label}** — {format_int(fact)} / {format_int(plan)} ({pct:.0f}%)")
            st.progress(min(pct / 100, 1.0))

    st.divider()

    # === ДИАГРАММЫ ===
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**План vs Факт по категориям**")
        chart_data = []
        if not total_row.empty:
            t = total_row.iloc[0]
            for key, label, unit in data_loader.PLAN_CATEGORIES:
                if key not in enabled_plans:
                    continue
                plan = float(plans.get(key, 0))
                fact = float(t.get(key, 0))
                if plan <= 0 and fact <= 0:
                    continue
                chart_data.append({'Категория': label, 'План': plan, 'Факт': fact})

        if chart_data:
            df_chart = pd.DataFrame(chart_data)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_chart['Категория'], y=df_chart['План'], name='План', marker_color='#A7C7E7'))
            fig.add_trace(go.Bar(x=df_chart['Категория'], y=df_chart['Факт'], name='Факт', marker_color='#E27D60'))
            fig.update_layout(
                barmode='group',
                xaxis_tickangle=-45,
                yaxis=dict(automargin=True, tickformat=',.0f'),
                margin=dict(l=20, r=20, b=100),
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with col2:
        st.markdown("**Факт по менеджерам (продажи)**")
        mgr_data = plan_summary[plan_summary['manager'] != 'Все менеджеры'].copy()
        if not mgr_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=mgr_data['manager'], y=mgr_data['sales'], name='Факт', marker_color='#41B3A3'))
            if plan_sales > 0:
                fig.add_hline(
                    y=plan_sales, line_dash="dash", line_color="#E27D60",
                    annotation_text=f"План: {format_int(plan_sales)}", annotation_position="top right"
                )
            fig.update_layout(
                xaxis_tickangle=-45,
                yaxis=dict(automargin=True, tickformat=',.0f'),
                margin=dict(l=20, r=20, b=100),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def render_admin_settings(summary, selected_manager):
    """Expander управления метками, лимитами и сроками."""
    user_role = st.session_state.role
    
    # Только админ и суперадмин
    if user_role not in ('admin', 'super_admin'):
        return
    
    admin_settings = data_loader.get_admin_settings()
    trust_limits = data_loader.load_trust_limits()
    
    is_super = (user_role == 'super_admin')
    
    # Разрешения
    can_edit_blacklist = is_super or admin_settings.get('allow_admins_blacklist', False)
    can_edit_golden = is_super or admin_settings.get('allow_admins_golden', False)
    can_edit_trust = is_super or admin_settings.get('allow_admins_trust_limits', False)
    can_edit_status_days = is_super or admin_settings.get('allow_admins_status_days', False)
    can_edit_inactive = is_super or admin_settings.get('allow_admins_inactive_days', False)
    can_edit_potential = is_super or admin_settings.get('allow_admins_potential_days', False)
    
    # Если ни одно разрешение не дано — ничего не показываем
    if not any([can_edit_blacklist, can_edit_golden, can_edit_trust,
                can_edit_status_days, can_edit_inactive, can_edit_potential]):
        return
    
    with st.expander("⚙️ Управление метками и лимитами", expanded=False):
        
        # ============================================================
        # БЛОК 1: МЕТКИ ПРЕДПРИЯТИЙ (💀, 🏆)
        # ============================================================
        if can_edit_blacklist or can_edit_golden:
            render_metki_editor(summary, selected_manager, can_edit_blacklist, can_edit_golden)
            st.divider()
        
        # ============================================================
        # БЛОК 2: ПОРОГИ TRUST LIMITS
        # ============================================================
        if can_edit_trust:
            st.markdown("**💰 Пороги лимита доверия**")
            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                new_t1 = st.number_input(
                    "Порог 1, BYN",
                    value=float(trust_limits.get('threshold_1', 5000)),
                    step=500.0, format="%.0f",
                    key="admin_settings_t1"
                )
            with tc2:
                new_t2 = st.number_input(
                    "Порог 2, BYN",
                    value=float(trust_limits.get('threshold_2', 7000)),
                    step=500.0, format="%.0f",
                    key="admin_settings_t2"
                )
            with tc3:
                new_t3 = st.number_input(
                    "Порог 3, BYN",
                    value=float(trust_limits.get('threshold_3', 10000)),
                    step=500.0, format="%.0f",
                    key="admin_settings_t3"
                )
            st.divider()
        
        # ============================================================
        # БЛОК 3: СРОКИ СТАТУСОВ
        # ============================================================
        if can_edit_status_days:
            st.markdown("**🔄 Сроки статусов**")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                new_working = st.number_input(
                    "Актив ≤ дней",
                    value=int(admin_settings.get('working_days', 60)),
                    min_value=1, step=1,
                    key="admin_settings_working"
                )
            with sc2:
                new_passive = st.number_input(
                    "Пассив ≤ дней",
                    value=int(admin_settings.get('passive_days', 90)),
                    min_value=1, step=1,
                    key="admin_settings_passive"
                )
            with sc3:
                new_lost = st.number_input(
                    "Потери > дней",
                    value=int(admin_settings.get('lost_days', 120)),
                    min_value=1, step=1,
                    key="admin_settings_lost"
                )
            with sc4:
                new_returned = st.number_input(
                    "Камбэк разрыв > дней",
                    value=int(admin_settings.get('returned_days', 120)),
                    min_value=1, step=1,
                    key="admin_settings_returned"
                )
            st.divider()
        
        # ============================================================
        # БЛОК 4: СРОКИ МЕТОК
        # ============================================================
        if can_edit_inactive or can_edit_potential:
            st.markdown("**🏷️ Сроки меток**")
            mc1, mc2 = st.columns(2)
            with mc1:
                new_inactive = st.number_input(
                    "⏰ Нет заявок > дней",
                    value=int(admin_settings.get('inactive_days', 30)),
                    min_value=1, step=1,
                    key="admin_settings_inactive",
                    disabled=not can_edit_inactive
                )
            with mc2:
                new_potential = st.number_input(
                    "🤝 Предупреждение, дней",
                    value=int(admin_settings.get('potential_warning_days', 90)),
                    min_value=1, step=1,
                    key="admin_settings_potential",
                    disabled=not can_edit_potential
                )
            st.divider()
        
        # ============================================================
        # БЛОК 5: ДЕБИТОРКА
        # ============================================================
        if can_edit_trust:
            st.markdown("**💰 Дебиторка**")
            dc1, dc2 = st.columns(2)
            with dc1:
                new_debtor_days = st.number_input(
                    "💸 Должник > дней",
                    value=int(admin_settings.get('debtor_days', 90)),
                    min_value=1, step=1,
                    key="admin_settings_debtor_days"
                )
            with dc2:
                new_debtor_thr = st.selectbox(
                    "Превышение какого порога лимита доверия = Должник",
                    options=[1, 2, 3],
                    index=int(admin_settings.get('debtor_threshold', 2)) - 1,
                    key="admin_settings_debtor_thr"
                )
            st.divider()
        
        # ============================================================
        # БЛОК 6: ПРЕДСЧЁТ
        # ============================================================
        if can_edit_status_days:
            st.markdown("**📋 Предсчёт**")
            new_prepayment = st.number_input(
                "Активен ≤ дней",
                value=int(admin_settings.get('prepayment_active_days', 30)),
                min_value=1, step=1,
                key="admin_settings_prepayment"
            )
        
        # ============================================================
        # КНОПКА СОХРАНИТЬ
        # ============================================================
        if st.button("💾 Сохранить всё", key="admin_settings_save", type="primary"):
            errors = []
            
            # 1. Проверка TrustLimits
            if can_edit_trust:
                if not (new_t1 < new_t2 < new_t3):
                    errors.append("❌ Пороги должны возрастать: t1 < t2 < t3")
            
            if errors:
                for e in errors:
                    st.error(e)
            else:
                # 2. Метки предприятий сохраняются отдельной кнопкой внутри блока
                #    (здесь ничего не делаем)
                pass
                
                # 3. Сохраняем TrustLimits
                if can_edit_trust:
                    data_loader.save_trust_limits({
                        'threshold_1': new_t1,
                        'threshold_2': new_t2,
                        'threshold_3': new_t3,
                    })
                
                # 4. Сохраняем admin_settings
                new_settings = dict(admin_settings)
                if can_edit_status_days:
                    new_settings['working_days'] = new_working
                    new_settings['passive_days'] = new_passive
                    new_settings['lost_days'] = new_lost
                    new_settings['returned_days'] = new_returned
                    new_settings['prepayment_active_days'] = new_prepayment
                if can_edit_inactive:
                    new_settings['inactive_days'] = new_inactive
                if can_edit_potential:
                    new_settings['potential_warning_days'] = new_potential
                if can_edit_trust:
                    new_settings['debtor_days'] = new_debtor_days
                    new_settings['debtor_threshold'] = new_debtor_thr
                
                data_loader.save_admin_settings(new_settings)
                
                st.success("✅ Настройки сохранены")
                st.cache_data.clear()
                st.rerun()


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

        # Легенда обозначений
        try:
            admin_settings_legend = data_loader.get_admin_settings()
            trust_limits_legend = data_loader.load_trust_limits()

            wd = admin_settings_legend.get('working_days', 60)
            pd_days = admin_settings_legend.get('passive_days', 90)
            ld = admin_settings_legend.get('lost_days', 120)
            rd = admin_settings_legend.get('returned_days', 120)
            inad = admin_settings_legend.get('inactive_days', 30)
            ddays = admin_settings_legend.get('debtor_days', 90)
            dthr = admin_settings_legend.get('debtor_threshold', 2)
            dthr_val = int(trust_limits_legend.get(f"threshold_{dthr}", 7000))

            with st.expander("📖 Легенда обозначений", expanded=False):
                st.markdown(f"""
**📊 СТАТУСЫ ПРЕДПРИЯТИЙ**<br><br>
🆕 **Новое** — первый счёт в текущем календарном месяце<br>
🔄 **Камбэки** — перерыв > {rd} дней, последний счёт в текущем месяце<br>
✅ **Актив** — от последнего счёта ≤ {wd} дней<br>
😴 **Пассив** — от {wd + 1} до {pd_days} дней без счетов<br>
🗑️ **Потери** — > {pd_days} дней без счетов<br>
🤝 **Потенциальное** — ведём переговоры (вручную)<br><br>
**🏷️ МЕТКИ** (могут быть одновременно)<br><br>
💀 **ЧС** — не работаем (вручную)<br>
⚖️ **Суд** — есть непогашенный долг, переданный юристам<br>
🏆 **Золотой фонд** — приоритетные (вручную)<br>
⏰ **Нет заявок** — нет счетов > {inad} дней и нет дебиторки<br>
💰 **Дебиторка** — есть долг, но < {ddays} дней и < порог {dthr} ({dthr_val} BYN)<br>
💸 **Должник** — дебиторка > {ddays} дней или ≥ порог {dthr} ({dthr_val} BYN)
                """, unsafe_allow_html=True)
        except Exception as e:
            st.caption(f"⚠️ Легенда недоступна: {e}")

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
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
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

    by_mgr_debt = data_loader.get_debt_by_manager(df)
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

    # Проверяем — включены ли планы
    plans_settings_check = data_loader.get_plans_settings()
    plans_enabled = bool(plans_settings_check.get('enabled_plans', []))

    # Фильтруем USER_TABS — убираем tab0, если планы отключены
    base_tabs = USER_TABS
    if not plans_enabled:
        base_tabs = [(k, v) for k, v in USER_TABS if k != 'tab0']

    if 'all' in user_tabs:
        visible_user_tabs = base_tabs
    else:
        visible_user_tabs = [(k, v) for k, v in base_tabs if k in user_tabs]

    if user_role == 'super_admin':
        visible_tabs = list(visible_user_tabs) + list(ADMIN_TABS)
    else:
        visible_tabs = list(visible_user_tabs)

    if not visible_tabs:
        st.warning("У вас нет доступа ни к одной вкладке. Обратитесь к администратору.")
        return

    tab_objects = st.tabs([v for _, v in visible_tabs])
    # Summary — один раз для всех вкладок
    admin_settings = data_loader.get_admin_settings()
    trust_limits = data_loader.load_trust_limits()
    summary = data_loader.get_summary_cached(
        df,
        admin_settings=admin_settings,
        trust_limits=trust_limits,
    )
    tab_map = {k: tab_objects[i] for i, (k, _) in enumerate(visible_tabs)}
    
    # ===== TAB0: ПЛАН =====
    if 'tab0' in tab_map:
        with tab_map['tab0']:
            render_plan_tab(df, summary, selected_periods, selected_manager, user_role)

    # ===== TAB1: ПРЕДПРИЯТИЯ =====
    if 'tab1' in tab_map:
        with tab_map['tab1']:
            # ============================================================
            # СЕКЦИЯ 1: ПРОДАЖИ ПО ПРЕДПРИЯТИЯМ (как было)
            # ============================================================
            st.subheader("📊 Продажи по предприятиям")
            by_company = data_loader.get_sales_by_company(sales_data)

            if not by_company.empty:
                if selected_manager == 'Все менеджеры':
                    display = by_company[['company_code', 'company', 'raion', 'oblast', 'manager', 'amount']].copy()
                    display.columns = ['Код', 'Предприятие', 'Район', 'Область', 'Менеджер', 'Сумма, BYN']
                else:
                    display = by_company[['company_code', 'company', 'raion', 'oblast', 'amount']].copy()
                    display.columns = ['Код', 'Предприятие', 'Район', 'Область', 'Сумма, BYN']

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
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Нет данных")

            st.divider()

            # ============================================================
            # СЕКЦИЯ 2: КАТЕГОРИИ ПРЕДПРИЯТИЙ (новое)
            # ============================================================
            st.subheader("🏷️ Категории предприятий")

            # Считаем оба представления:
            # cat_counts — Способ 1 (приоритет, для круговой и списков)
            # counts     — Способ 2 (независимо, для KPI меток)
            # Круговая — по приоритету (одно предприятие — один сектор)
            cat_counts = data_loader.get_companies_by_category(summary, selected_manager)
            # Табы — по меткам (могут пересекаться)
            metka_counts = data_loader.get_companies_by_metka(summary, selected_manager)
            # Независимый подсчёт для KPI меток
            counts = data_loader.get_independent_counts(summary, selected_manager)

            # Всего — по фильтру менеджера
            if selected_manager == 'Все менеджеры':
                total_count = len(summary)
            else:
                total_count = sum(
                    1 for m in summary.values()
                    if m.get('manager') == selected_manager
                )

            # Статусы для ряда 1–2 — из cat_counts (Способ 1)
            status_working = len(cat_counts.get('working', []))
            status_passive = len(cat_counts.get('passive', []))
            status_new = len(cat_counts.get('new', []))
            status_lost = len(cat_counts.get('lost', []))
            status_returned = len(cat_counts.get('returned', []))
            status_potential = len(cat_counts.get('potential', []))

            # Метки для ряда 3 — из counts (Способ 2, независимо)
            metka_blacklist = counts.get('blacklist', 0)
            metka_court = counts.get('court', 0)
            metka_golden = counts.get('golden_fund', 0)
            metka_debtor = counts.get('debtor', 0)
            metka_debitorka = counts.get('debitorka', 0)
            metka_inactive = counts.get('inactive', 0)

            # ===== СТАТУСЫ =====
            st.markdown("**📊 Статусы** (предприятие в одной категории)")

            k1, k2, k3 = st.columns(3)
            with k1:
                st.markdown(f'<div class="metric-box-small"><h3>✅ Актив</h3><p>{status_working}</p></div>', unsafe_allow_html=True)
            with k2:
                st.markdown(f'<div class="metric-box-small"><h3>🏢 Всего</h3><p>{total_count}</p></div>', unsafe_allow_html=True)
            with k3:
                st.markdown(f'<div class="metric-box-small"><h3>😴 Пассив</h3><p>{status_passive}</p></div>', unsafe_allow_html=True)

            k4, k5, k6, k7 = st.columns(4)
            with k4:
                st.markdown(f'<div class="metric-box-small"><h3>🆕 Новое</h3><p>{status_new}</p></div>', unsafe_allow_html=True)
            with k5:
                st.markdown(f'<div class="metric-box-small"><h3>🗑️ Потери</h3><p>{status_lost}</p></div>', unsafe_allow_html=True)
            with k6:
                st.markdown(f'<div class="metric-box-small"><h3>🔄 Камбэки</h3><p>{status_returned}</p></div>', unsafe_allow_html=True)
            with k7:
                st.markdown(f'<div class="metric-box-small"><h3>🤝 Потенциальные</h3><p>{status_potential}</p></div>', unsafe_allow_html=True)

            # ===== МЕТКИ =====
            st.markdown("**🏷️ Метки** (могут пересекаться)")

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            with m1:
                st.markdown(f'<div class="metric-box-small"><h3>💀 ЧС</h3><p>{metka_blacklist}</p></div>', unsafe_allow_html=True)
            with m2:
                st.markdown(f'<div class="metric-box-small"><h3>⚖️ Суд</h3><p>{metka_court}</p></div>', unsafe_allow_html=True)
            with m3:
                st.markdown(f'<div class="metric-box-small"><h3>🏆 Золото</h3><p>{metka_golden}</p></div>', unsafe_allow_html=True)
            with m4:
                st.markdown(f'<div class="metric-box-small"><h3>💸 Должник</h3><p>{metka_debtor}</p></div>', unsafe_allow_html=True)
            with m5:
                st.markdown(f'<div class="metric-box-small"><h3>💰 Дебиторка</h3><p>{metka_debitorka}</p></div>', unsafe_allow_html=True)
            with m6:
                st.markdown(f'<div class="metric-box-small"><h3>⏰ Нет заявок</h3><p>{metka_inactive}</p></div>', unsafe_allow_html=True)

            st.divider()

            # Графики (круговая + столбчатая)
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.markdown("**Распределение по категориям**")
                pie_data = []
                for cat in data_loader.CATEGORY_ORDER:
                    cnt = len(cat_counts.get(cat, []))
                    if cnt > 0:
                        pie_data.append({'category': data_loader.CATEGORY_LABELS[cat], 'count': cnt})

                if pie_data:
                    pie_df = pd.DataFrame(pie_data)
                    fig = px.pie(
                        pie_df, values='count', names='category',
                        color_discrete_sequence=CONTRAST_PALETTE
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{label}</b><br>%{value} шт. (%{percent})<extra></extra>'
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("Нет данных")

            show_trust = admin_settings.get('show_trust_limits', True)

            with chart_col2:
                if show_trust:
                    st.markdown("**Превышение лимита доверия**")
                    t1 = trust_limits.get('threshold_1', 5000)
                    t2 = trust_limits.get('threshold_2', 7000)
                    t3 = trust_limits.get('threshold_3', 10000)

                    over_t1 = 0
                    over_t2 = 0
                    over_t3 = 0

                    for code, m in summary.items():
                        if selected_manager != 'Все менеджеры' and m.get('manager') != selected_manager:
                            continue
                        debt = m.get('debt_amount', 0)
                        if debt >= t3:
                            over_t3 += 1
                        elif debt >= t2:
                            over_t2 += 1
                        elif debt >= t1:
                            over_t1 += 1

                    bar_df = pd.DataFrame({
                        'Порог': [f'≥ {int(t1)}', f'≥ {int(t2)}', f'≥ {int(t3)}'],
                        'Кол-во': [over_t1, over_t2, over_t3]
                    })
                    fig = px.bar(
                        bar_df, x='Порог', y='Кол-во',
                        color='Порог',
                        color_discrete_sequence=['#F4D03F', '#F5B041', '#EC7063']
                    )
                    fig.update_traces(
                        hovertemplate='<b>%{x} BYN</b><br>%{y} предприятий<extra></extra>'
                    )
                    fig.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("")

            st.divider()

            # Таблица предприятий с метками
            st.markdown("**Все предприятия**")
            df_companies = data_loader.get_companies_with_metki_df(summary, selected_manager)

            if not df_companies.empty:
                display = df_companies.copy()
                display['debt_amount'] = display['debt_amount'].apply(format_int)
                display['court_amount'] = display['court_amount'].apply(format_int)
                display['overpay_amount'] = display['overpay_amount'].apply(format_int)

                status_map = {
                    'new': '🆕 Новое',
                    'returned': '🔄 Камбэки',
                    'working': '✅ Актив',
                    'passive': '😴 Пассив',
                    'lost': '🗑️ Потери',
                    'potential': '🤝 Потенциальное',
                }
                display['status_display'] = display['status'].map(status_map).fillna(display['status'])

                display = display[['company_code', 'company_name', 'oblast', 'raion', 'manager',
                                    'debt_amount', 'court_amount', 'overpay_amount',
                                    'status_display', 'metki']]
                display.columns = ['Код', 'Название', 'Область', 'Район', 'Менеджер',
                                    'Дебиторка, BYN', 'В суде, BYN', 'Переплата, BYN',
                                    'Статус', 'Метки']

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {len(df_companies)} предприятий")
            else:
                st.info("Нет данных")

            st.divider()

            # Управление статусом «Потенциальный»
            render_potential_manager(summary, admin_settings, selected_manager)

            # Показать сохранённые сообщения
            for key in list(st.session_state.keys()):
                if key.startswith('pot_action_'):
                    st.success(st.session_state.pop(key))
                elif key.startswith('pot_error_'):
                    st.error(st.session_state.pop(key))

            st.divider()

            # Списки по категориям
            st.markdown("**Списки по категориям**")

            # Считаем предприятия с превышением порогов
            over_limit_codes = []
            for code, m in summary.items():
                if selected_manager != 'Все менеджеры' and m.get('manager') != selected_manager:
                    continue
                debt = m.get('debt_amount', 0)
                if debt >= trust_limits.get('threshold_1', 5000):
                    over_limit_codes.append(code)
            over_limit_codes.sort(
                key=lambda c: summary[c].get('debt_amount', 0),
                reverse=True
            )

            show_trust = admin_settings.get('show_trust_limits', True)

            tab_names = [
                f"💀 ЧС ({len(metka_counts['blacklist'])})",
                f"🏆 Золото ({len(metka_counts['golden_fund'])})",
                f"🆕 Новые ({len(metka_counts['new'])})",
                f"🔄 Камбэки ({len(metka_counts['returned'])})",
                f"🤝 Потенциальные ({len(metka_counts['potential'])})",
                f"💸 Должники ({len(metka_counts['debtor'])})",
                f"💰 Дебиторка ({len(metka_counts['debitorka'])})",
                f"⏰ Нет заявок ({len(metka_counts['inactive'])})",
                f"⚖️ Суд ({len(metka_counts['court'])})",
            ]
            if show_trust:
                tab_names.append(f"⚠️ Превышение лимита ({len(over_limit_codes)})")
            overpay_count = sum(
                1 for c, m in summary.items()
                if m.get('overpay_amount', 0) > 0.5
                and (selected_manager == 'Все менеджеры' or m.get('manager') == selected_manager)
            )
            tab_names.append(f"💸 Переплаты ({overpay_count})")

            list_tabs = st.tabs(tab_names)
            list_categories = ['blacklist', 'golden_fund', 'new', 'returned',
                                'potential', 'debtor', 'debitorka', 'inactive', 'court']
            list_categories = ['blacklist', 'golden_fund', 'new', 'returned',
                                'potential', 'debtor', 'debitorka', 'inactive', 'court']

            # Существующие 8 табов
            for i, cat in enumerate(list_categories):
                with list_tabs[i]:
                    codes = metka_counts.get(cat, [])
                    if not codes:
                        st.info("Пусто")
                        continue

                    rows = []
                    for code in codes:
                        m = summary.get(code, {})
                        # Для Камбэков — информация о возврате
                        return_info = '—'
                        if cat == 'returned':
                            li = m.get('last_invoice')
                            if li:
                                d = li.get('date')
                                d_str = d.strftime('%d.%m.%Y') if hasattr(d, 'strftime') else str(d)
                                return_info = f"{d_str} — {format_int(li.get('amount', 0))} BYN"
                        rows.append({
                            'Код': m.get('company_code') or code,
                            'Название': m.get('company_name', ''),
                            'Менеджер': m.get('manager', ''),
                            'Район': m.get('raion', ''),
                            'Дебиторка': format_int(m.get('debt_amount', 0)),
                            'days_col': m.get('last_gap', 0) if cat == 'returned'
                                        else (m.get('days_since_last') if m.get('days_since_last') is not None else '—'),
                            'return_info': return_info,
                            'Предсчёт': '✅' if m.get('has_prepayment') else '❌',
                            'Метки': ' • '.join({'💀': '💀 ЧС', '🏆': '🏆 Золото', '🆕': '🆕 Новое', '🔄': '🔄 Вернувшееся', '🤝': '🤝 Потенциальное', '💸': '💸 Должник', '💰': '💰 Дебиторка', '⏰': '⏰ Нет заявок'}.get(e, e) for e in m.get('metki', [])),
                        })

                    df_list = pd.DataFrame(rows)

                    # Переименовать колонку: Камбэки → «Перерыв, дней», остальные → «Дней без заявок»
                    if cat == 'returned':
                        df_list = df_list.rename(columns={
                            'days_col': 'Перерыв, дней',
                            'return_info': 'Возврат (дата — сумма)',
                        })
                    else:
                        df_list = df_list.drop(columns=['return_info'], errors='ignore')
                        df_list = df_list.rename(columns={'days_col': 'Дней без заявок'})

                    st.dataframe(df_list, use_container_width=True, hide_index=True)
                    st.caption(f"Всего: {len(df_list)} предприятий")

            # === РАСШИРЕННЫЙ ТАБ «⚖️ СУД» ===
            # Индекс таба «Суд» — 8
            with list_tabs[8]:
                # Собираем все court_rows
                court_df = data_loader.get_all_court_rows(summary, selected_manager)

                # === МЕТРИКИ ===
                if court_df.empty:
                    st.info("Нет предприятий в суде за выбранный период")
                else:
                    n_companies = court_df['company_code'].nunique()
                    total_court = court_df['court_amount'].sum()

                    cm1, cm2 = st.columns(2)
                    with cm1:
                        st.markdown(
                            f'<div class="metric-box">'
                            f'<h3>⚖️ Предприятий в суде</h3>'
                            f'<p>{n_companies}</p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    with cm2:
                        st.markdown(
                            f'<div class="metric-box">'
                            f'<h3>💰 Итого в суде</h3>'
                            f'<p>{format_int(total_court)}</p>'
                            f'<h3>BYN</h3>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                    st.divider()

                    # === ОБЗОРНАЯ ТАБЛИЦА (существующая — по предприятиям) ===
                    st.markdown("**Сводка по предприятиям**")

                    # Группируем court_df по предприятию
                    by_company = court_df.groupby(['company_code', 'company', 'manager', 'raion', 'oblast']).agg({
                        'court_amount': 'sum',
                        'court_days': 'max',
                    }).reset_index()
                    by_company = by_company.sort_values('court_amount', ascending=False)

                    display_overview = by_company.copy()
                    display_overview['court_amount'] = display_overview['court_amount'].apply(format_int)
                    display_overview = display_overview[['company_code', 'company', 'manager', 'raion', 'court_amount', 'court_days']]
                    display_overview.columns = ['Код', 'Название', 'Менеджер', 'Район', 'В суде, BYN', 'Дней в суде']

                    st.dataframe(display_overview, use_container_width=True, hide_index=True)

                    st.divider()

                    # === ДЕТАЛЬНАЯ ТАБЛИЦА (по счетам) ===
                    st.markdown("**Детализация по счетам**")

                    display_details = court_df.copy()
                    display_details['invoice_amount'] = display_details['invoice_amount'].apply(format_int)
                    display_details['paid_amount'] = display_details['paid_amount'].apply(format_int)
                    display_details['court_amount'] = display_details['court_amount'].apply(format_int)

                    # Убираем время из дат
                    display_details['invoice_date'] = pd.to_datetime(
                        display_details['invoice_date'], errors='coerce'
                    ).dt.strftime('%d.%m.%Y').fillna('')
                    display_details['court_date'] = pd.to_datetime(
                        display_details['court_date'], errors='coerce'
                    ).dt.strftime('%d.%m.%Y').fillna('')

                    # Пометка переходящего долга
                    if 'transfer_from' not in display_details.columns:
                        display_details['transfer_from'] = None

                    def _fmt_transfer(v):
                        if v is None or pd.isna(v) or v == '':
                            return '—'
                        return f'от {v}'

                    display_details['transfer_display'] = display_details['transfer_from'].apply(_fmt_transfer)

                    # Пометка переходящего долга
                    if 'transfer_from' not in display_details.columns:
                        display_details['transfer_from'] = None

                    def _fmt_transfer(v):
                        if v is None or pd.isna(v) or v == '':
                            return '—'
                        return f'от {v}'

                    display_details['transfer_display'] = display_details['transfer_from'].apply(_fmt_transfer)

                    display_details = display_details[[
                        'company_code', 'company', 'manager', 'raion', 'research_type',
                        'invoice_num', 'invoice_date', 'invoice_amount',
                        'paid_amount', 'court_amount', 'court_date', 'transfer_display'
                    ]]
                    display_details.columns = [
                        'Код', 'Название', 'Менеджер', 'Район', 'Вид исследования',
                        'Счёт №', 'Дата счёта', 'Продажа, BYN',
                        'Оплачено, BYN', 'В суд, BYN', 'Дата в суд', 'Переходящий'
                    ]

                    st.dataframe(display_details, use_container_width=True, hide_index=True)
                    st.caption(f"Всего: {len(display_details)} счетов на сумму {format_int(total_court)} BYN")

                    st.divider()

                    # === ДИАГРАММЫ ===
                    chart1, chart2 = st.columns(2)

                    # По менеджерам
                    with chart1:
                        st.markdown("**По менеджерам**")
                        by_mgr = court_df.groupby('manager')['court_amount'].sum().reset_index()
                        by_mgr = by_mgr.sort_values('court_amount', ascending=False)

                        if not by_mgr.empty:
                            by_mgr['amount_str'] = by_mgr['court_amount'].apply(format_int)
                            fig = px.bar(
                                by_mgr, x='manager', y='court_amount',
                                labels={'manager': 'Менеджер', 'court_amount': 'Сумма, BYN'},
                                color='manager',
                                color_discrete_sequence=CONTRAST_PALETTE,
                                custom_data=['amount_str']
                            )
                            fig.update_traces(
                                hovertemplate='<b>%{x}</b><br>%{customdata[0]} BYN<extra></extra>'
                            )
                            fig.update_layout(
                                showlegend=False,
                                yaxis=dict(automargin=True, tickformat=',.0f'),
                                margin=dict(l=20, r=20)
                            )
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                    # По месяцам
                    with chart2:
                        st.markdown("**По месяцам (дата передачи в суд)**")
                        court_df['court_month'] = pd.to_datetime(court_df['court_date'], errors='coerce').dt.strftime('%Y-%m')
                        by_month = court_df.groupby('court_month')['court_amount'].sum().reset_index()
                        by_month = by_month[by_month['court_month'].notna()]
                        by_month = by_month.sort_values('court_month')

                        if not by_month.empty:
                            by_month['label'] = by_month['court_month'].apply(
                                lambda x: f"{MONTHS_RU[int(x[5:7])]} {x[:4]}" if isinstance(x, str) and len(x) == 7 else ''
                            )
                            by_month['amount_str'] = by_month['court_amount'].apply(format_int)
                            fig = px.bar(
                                by_month, x='label', y='court_amount',
                                labels={'label': 'Месяц', 'court_amount': 'Сумма, BYN'},
                                color='court_amount',
                                color_continuous_scale='Reds',
                                custom_data=['amount_str']
                            )
                            fig.update_traces(
                                hovertemplate='<b>%{x}</b><br>%{customdata[0]} BYN<extra></extra>'
                            )
                            fig.update_layout(
                                coloraxis_showscale=False,
                                yaxis=dict(automargin=True, tickformat=',.0f'),
                                margin=dict(l=20, r=20)
                            )
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                        else:
                            st.info("Нет данных по датам")

            # Таб «Превышение лимита» — только если show_trust
            if show_trust:
                with list_tabs[9]:
                    if not over_limit_codes:
                        st.info("Нет предприятий с превышением лимита")
                    else:
                        t1 = trust_limits.get('threshold_1', 5000)
                        t2 = trust_limits.get('threshold_2', 7000)
                        t3 = trust_limits.get('threshold_3', 10000)

                        rows = []
                        for code in over_limit_codes:
                            m = summary.get(code, {})
                            debt = m.get('debt_amount', 0)

                            if debt >= t3:
                                over_display = f'⚠️⚠️⚠️ ≥ {int(t3)}'
                            elif debt >= t2:
                                over_display = f'⚠️⚠️ ≥ {int(t2)}'
                            else:
                                over_display = f'⚠️ ≥ {int(t1)}'

                            rows.append({
                                'Код': m.get('company_code') or code,
                                'Название': m.get('company_name', ''),
                                'Менеджер': m.get('manager', ''),
                                'Район': m.get('raion', ''),
                                'Дебиторка': format_int(debt),
                                'Дней долга': m.get('debt_days_max', 0),
                                'Превышение': over_display,
                            })

                        df_list = pd.DataFrame(rows)
                        st.dataframe(df_list, use_container_width=True, hide_index=True)
                        st.caption(f"Всего: {len(df_list)} предприятий с превышением лимита")

            # Переплаты — индекс 10, если show_trust, иначе 9
            overpay_idx = 10 if show_trust else 9
            with list_tabs[overpay_idx]:
                overpay_list = [
                    (code, m) for code, m in summary.items()
                    if m.get('overpay_amount', 0) > 0.5
                    and (selected_manager == 'Все менеджеры' or m.get('manager') == selected_manager)
                ]

                if not overpay_list:
                    st.info("Нет предприятий с переплатами")
                else:
                    rows = []
                    for code, m in overpay_list:
                        rows.append({
                            'Код': m.get('company_code') or code,
                            'Название': m.get('company_name', ''),
                            'Менеджер': m.get('manager', ''),
                            'Район': m.get('raion', ''),
                            'Переплата': format_int(m.get('overpay_amount', 0)),
                        })
                    df_overpay = pd.DataFrame(rows)
                    df_overpay = df_overpay.sort_values('Переплата', ascending=False)
                    st.dataframe(df_overpay, use_container_width=True, hide_index=True)
                    st.caption(f"Всего: {len(df_overpay)} предприятий с переплатами")

            # Управление метками и лимитами
            st.divider()
            render_admin_settings(summary, selected_manager)

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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
                by_mgr = data_loader.get_debt_by_manager(df)
                if not by_mgr.empty:
                    display = by_mgr.copy()
                    display['debt'] = display['debt'].apply(format_int)
                    display['court'] = display['court'].apply(format_int)
                    display['debt_share'] = display['debt_share'].round(2)
                    display = display[['manager', 'debt', 'court', 'companies', 'debt_share']]
                    display.columns = ['Менеджер', 'Дебиторка, BYN', 'В суде, BYN', 'Предприятий', 'Доля в общей, %']
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
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                display = payments_structure.copy()
                display['amount'] = display['amount'].apply(format_int)
                display = display[['category', 'amount', 'count']]
                display.columns = ['Категория дебиторки', 'Оплаты, BYN', 'Кол-во']
                st.dataframe(display, use_container_width=True, hide_index=True)
            else:
                st.info("Нет оплат за выбранный период")

            st.divider()

            # Таблица «Оплаты по менеджерам» — только для админа и суперадмина
            if user_role in ('admin', 'super_admin'):
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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
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

            # Настройки бонусов — только для админа (если разрешено) и суперадмина
            admin_settings_for_bonus = data_loader.get_admin_settings()
            can_edit_bonus = (
                user_role == 'super_admin' or
                (user_role == 'admin' and admin_settings_for_bonus.get('allow_admins_bonus_settings', True))
            )

            if can_edit_bonus:
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

    # ===== TAB7: ПРЕДСЧЕТА =====
    if 'tab7' in tab_map:
        with tab_map['tab7']:
            st.subheader("📋 Предсчета")

            prep_df = data_loader.get_prepayments_data(df, selected_periods, selected_manager)

            if prep_df.empty:
                st.info("Нет предсчетов за выбранный период")
            else:
                # KPI
                total_sum = float(prep_df['invoice_amount'].sum())
                total_count = len(prep_df)
                unique_companies = prep_df['company_code'].nunique()

                k1, k2, k3 = st.columns(3)
                with k1:
                    st.markdown(f'<div class="metric-box"><h3>💰 Сумма предсчетов</h3><p>{format_int(total_sum)}</p><h3>BYN</h3></div>', unsafe_allow_html=True)
                with k2:
                    st.markdown(f'<div class="metric-box"><h3>📋 Количество</h3><p>{total_count}</p></div>', unsafe_allow_html=True)
                with k3:
                    st.markdown(f'<div class="metric-box"><h3>🏢 Хозяйств</h3><p>{unique_companies}</p></div>', unsafe_allow_html=True)

                st.divider()

                # Таблица
                display = prep_df.copy()

                # Даты без времени
                display['invoice_date'] = pd.to_datetime(
                    display['invoice_date'], errors='coerce'
                ).dt.strftime('%d.%m.%Y').fillna('')

                display['invoice_amount'] = display['invoice_amount'].apply(format_int)

                display = display[[
                    'company_code', 'company', 'oblast', 'raion', 'manager',
                    'invoice_amount', 'invoice_date', 'invoice_num', 'research_type',
                ]]
                display.columns = [
                    'Код', 'Название', 'Область', 'Район', 'Менеджер',
                    'Сумма, BYN', 'Дата', 'Счёт №', 'Вид исследования',
                ]

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Всего: {total_count} предсчетов на сумму {format_int(total_sum)} BYN")

    # ===== TAB_ACCESS =====
    if 'tab_access' in tab_map:
        with tab_map['tab_access']:
            render_access_tab()


if __name__ == "__main__":
    main()