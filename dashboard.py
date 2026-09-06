import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import os

# Настройка страницы
st.set_page_config(
    page_title="Мониторинг ИТ-отрасли КК",
    page_icon="📊",
    layout="wide"
)

# Загрузка пароля из load_hh_to_pg.py
BASE = os.path.dirname(os.path.abspath(__file__))
password = "postgres123"
lp = os.path.join(BASE, "load_hh_to_pg.py")
if os.path.exists(lp):
    with open(lp, encoding="utf-8") as f:
        m = re.search(r'PASSWORD\s*=\s*["\']([^"\']*)["\']', f.read())
        if m:
            password = m.group(1)

# Подключение к PostgreSQL
@st.cache_resource
def get_connection():
    # Облако (Streamlit Cloud + Supabase)
    try:
        url = st.secrets["DATABASE_URL"]
        return psycopg2.connect(url, sslmode="require")
    except Exception:
        pass
    # Локально (ваш ПК)
    password = "postgres123"
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "load_hh_to_pg.py")
        with open(p, encoding="utf-8") as f:
            m = re.search(r'PASSWORD\s*=\s*["\']([^"\']*)["\']', f.read())
            if m:
                password = m.group(1)
    except Exception:
        pass
    return psycopg2.connect(
        dbname="it_monitoring",
        user="postgres",
        password=password,
        host="localhost",
        port=5432
    )

conn = get_connection()

# Заголовок
st.title("📊 Мониторинг ИТ-отрасли Краснодарского края")
st.markdown("**Ассоциация ИТ-компаний** | Данные на сентябрь 2026")
st.markdown("---")

# Загрузка данных
@st.cache_data
def load_data():
    with conn.cursor() as cur:
        # Вакансии
        cur.execute("""
            SELECT source, company_name, vacancy_name, salary_from, salary_to, 
                   salary_avg, currency, area, url, month
            FROM hh_vacancies
            ORDER BY month DESC, salary_avg DESC NULLS LAST
        """)
        vacancies = pd.DataFrame(cur.fetchall(), 
            columns=['source', 'company_name', 'vacancy_name', 'salary_from', 
                     'salary_to', 'salary_avg', 'currency', 'area', 'url', 'month'])
        
        # Компании
        cur.execute("""
            SELECT inn, name, okved, region, registration_date, mincifry_accredited
            FROM it_companies
        """)
        companies = pd.DataFrame(cur.fetchall(),
            columns=['inn', 'name', 'okved', 'region', 'registration_date', 'mincifry_accredited'])
    
    # Преобразуем числовые колонки
    numeric_cols = ['salary_from', 'salary_to', 'salary_avg']
    for col in numeric_cols:
        vacancies[col] = pd.to_numeric(vacancies[col], errors='coerce')
    
    return vacancies, companies

vacancies, companies = load_data()

# KPI метрики
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("ИТ-компаний в кластере", len(companies))

with col2:
    st.metric("Активных вакансий", len(vacancies))

with col3:
    vacancies_with_salary = vacancies[vacancies['salary_avg'].notna()]
    if len(vacancies_with_salary) > 0:
        avg_salary = vacancies_with_salary['salary_avg'].mean()
        st.metric("Средняя зарплата", f"{avg_salary:,.0f} ₽".replace(",", " "))
    else:
        st.metric("Средняя зарплата", "н/д")

with col4:
    accredited = companies[companies['mincifry_accredited'] == True]
    acc_pct = len(accredited) * 100 / len(companies) if len(companies) > 0 else 0
    st.metric("Аккредитовано Минцифры", f"{len(accredited)} ({acc_pct:.1f}%)")

st.markdown("---")

# Раздел 1: Анализ зарплат
st.header("💰 Анализ зарплат")

col1, col2 = st.columns(2)

with col1:
    # Гистограмма распределения зарплат
    if len(vacancies_with_salary) > 0:
        fig = px.histogram(
            vacancies_with_salary,
            x='salary_avg',
            nbins=20,
            title="Распределение зарплат (вакансий)",
            labels={'salary_avg': 'Зарплата, ₽', 'count': 'Количество вакансий'},
            color_discrete_sequence=['#1f77b4']
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width='stretch')

with col2:
    # Круговая диаграмма: вакансии с зарплатой / без
    with_salary = len(vacancies_with_salary)
    without_salary = len(vacancies) - with_salary
    
    fig = px.pie(
        values=[with_salary, without_salary],
        names=['С зарплатой', 'Без зарплаты'],
        title="Доля вакансий с указанной зарплатой",
        color_discrete_sequence=['#2ca02c', '#d62728']
    )
    st.plotly_chart(fig, width='stretch')

st.markdown("---")

# Раздел 2: Топ работодателей
st.header("🏢 Топ-15 работодателей")

if len(vacancies) > 0:
    top_companies = vacancies.groupby('company_name').size().sort_values(ascending=False).head(15)
    top_companies = top_companies[top_companies.index.notna() & (top_companies.index != '')]
    
    if len(top_companies) > 0:
        fig = px.bar(
            x=top_companies.values,
            y=top_companies.index,
            orientation='h',
            title="Количество вакансий по компаниям",
            labels={'x': 'Количество вакансий', 'y': 'Компания'},
            color=top_companies.values,
            color_continuous_scale='Blues'
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, width='stretch')

st.markdown("---")

# Раздел 3: Аккредитация Минцифры
st.header("🏛️ Аккредитация Минцифры РФ")

col1, col2 = st.columns([1, 2])

with col1:
    acc_count = len(accredited)
    not_acc_count = len(companies) - acc_count
    
    fig = px.pie(
        values=[acc_count, not_acc_count],
        names=['Аккредитованы', 'Не аккредитованы'],
        title="Проникновение федеральных льгот",
        color_discrete_sequence=['#2ca02c', '#ff7f0e']
    )
    st.plotly_chart(fig, width='stretch')

with col2:
    st.subheader("Потенциал роста")
    st.info(f"""
    **{not_acc_count} компаний** ({not_acc_count*100//len(companies)}%) ещё не получили аккредитацию Минцифры.
    
    Это означает, что они **не пользуются федеральными льготами**:
    - Сниженные страховые взносы (7.6% вместо 30%)
    - Налог на прибыль 0%
    - Отсрочка от армии для сотрудников
    
    **Задача Ассоциации:** помочь этим компаниям получить аккредитацию.
    """)

if len(accredited) > 0:
    st.subheader("Аккредитованные компании:")
    for _, row in accredited.iterrows():
        st.write(f"✅ **{row['name']}** (ИНН {row['inn']})")

st.markdown("---")

# Раздел 3.5: Рынок труда ИТ
st.header("🏢 Спрос на ИТ-специалистов в экономике региона")
st.info("""
**Важно:** этот раздел показывает ВСЕХ работодателей, нанимающих ИТ-специалистов.
Сюда входят не только ИТ-компании, но и ритейл, медицина, производство —
любой бизнес, которому нужны программисты и аналитики.

Это показатель **спроса экономики региона на ИТ-кадры**.
Сами ИТ-компании кластера — в разделе «Реестр ИТ-компаний» ниже.
""")

# Агрегация по компаниям
comp_vac = vacancies[vacancies['company_name'].notna() & (vacancies['company_name'] != '')]
company_stats = comp_vac.groupby('company_name').agg(
    Вакансий=('vacancy_name', 'count'),
    Средняя_зарплата=('salary_avg', 'mean'),
    Макс_зарплата=('salary_avg', 'max')
).reset_index().sort_values(
    ['Вакансий', 'Средняя_зарплата'], ascending=[False, False]
).reset_index(drop=True)

def fmt_sal(x):
    return f"{int(x):,} ₽".replace(",", " ") if pd.notna(x) else "н/д"

company_stats['Средняя_зарплата'] = company_stats['Средняя_зарплата'].apply(fmt_sal)
company_stats['Макс_зарплата'] = company_stats['Макс_зарплата'].apply(fmt_sal)

st.write(f"Компаний, размещающих ИТ-вакансии: **{len(company_stats)}**")

st.dataframe(
    company_stats.rename(columns={
        'company_name': 'Компания',
        'Вакансий': 'Вакансий',
        'Средняя_зарплата': 'Средняя зарплата',
        'Макс_зарплата': 'Макс. зарплата'
    }),
    width='stretch',
    height=400,
    hide_index=True
)

st.dataframe(
    company_stats.rename(columns={
        'company_name': 'Компания',
        'Вакансий': 'Вакансий',
        'Средняя_зарплата': 'Средняя зарплата, ₽',
        'Макс_зарплата': 'Макс. зарплата, ₽'
    }),
    width='stretch',
    height=400
)

st.markdown("---")

# Раздел 3.6: Реестр ИТ-компаний КК
st.header("📑 Реестр ИТ-компаний Краснодарского края")
st.info("""
**Это официальный кластер ИТ-компаний КК** по данным реестра МСП
(ОКВЭД 62 «Разработка ПО» и 63 «Обработка данных»).
Именно эти 52 компании — целевая аудитория Ассоциации.
""")

st.write(f"Всего в реестре МСП: **{len(companies)}** компаний")

st.dataframe(
    companies[['inn', 'name', 'okved', 'mincifry_accredited']].rename(columns={
        'inn': 'ИНН',
        'name': 'Наименование',
        'okved': 'ОКВЭД',
        'mincifry_accredited': 'Аккредитация Минцифры'
    }),
    width='stretch',
    height=400
)

st.markdown("---")

# Раздел 4: Таблица вакансий
st.header("📋 Таблица вакансий")

# Фильтры
col1, col2, col3 = st.columns(3)

with col1:
    min_salary = st.number_input("Мин. зарплата, ₽", value=0, step=10000)

with col2:
    max_salary = st.number_input("Макс. зарплата, ₽", value=1000000, step=10000)

with col3:
    search_term = st.text_input("Поиск по названию", "")

# Фильтрация
filtered = vacancies.copy()
if min_salary > 0:
    filtered = filtered[filtered['salary_avg'] >= min_salary]
if max_salary < 1000000:
    filtered = filtered[filtered['salary_avg'] <= max_salary]
if search_term:
    filtered = filtered[filtered['vacancy_name'].str.contains(search_term, case=False, na=False)]

st.write(f"Найдено вакансий: **{len(filtered)}**")

# Подготавливаем данные для отображения
filtered_display = filtered[['company_name', 'vacancy_name', 'salary_avg', 'area']].copy()
# Округляем зарплату и преобразуем в строку для красивого отображения
filtered_display['salary_avg'] = filtered_display['salary_avg'].apply(
    lambda x: f"{int(x):,} ₽".replace(",", " ") if pd.notna(x) else "—"
)
filtered_display = filtered_display.fillna('—')

st.dataframe(
    filtered_display,
    width='stretch',
    height=400
)

# Футер
st.markdown("---")
st.caption(f"Данные обновлены: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')} | Источник: HH.ru, Реестр МСП ФНС, Минцифры РФ")