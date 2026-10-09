# -*- coding: utf-8 -*-
"""
Build Detailed Analytical Tender Report (2021-2025)
Integrates:
1. tender_companies_ai_verified (8,411 companies with UBO, shareholders, CEO, address)
2. LesOutputJson / burtgel_les.db (foundation dates, company registry)
3. FINAL_Tender_Report_2021_2025_With_Details (64,194 detailed tender records)

Excludes:
- Shilendans columns (amounts, transaction counts, matching methods, organizations)
- Phones, emails, undefined addresses

Calculates:
- Announcement-to-closed duration (in days)
- Budget vs Contract Price difference (Savings in MNT)
- Price discount percentage (%)
- Proper sorting: Company Total Amount -> Company Name -> Year -> Announcement Date
"""

import os
import re
import json
import sqlite3
import pandas as pd
import numpy as np
import xlsxwriter

DATA_DIR = "/Users/enkhbadraltsogbayar/Tender data"
RAW_TENDER_FILE = os.path.join(DATA_DIR, "FINAL_Tender_Report_2021_2025_With_Details_RAW_BACKUP.xlsx")
if not os.path.exists(RAW_TENDER_FILE):
    RAW_TENDER_FILE = os.path.join(DATA_DIR, "FINAL_Tender_Report_2021_2025_With_Details.xlsx")

OUTPUT_FILE = os.path.join(DATA_DIR, "FINAL_Tender_Report_2021_2025_With_Details.xlsx")
OUTPUT_TEMP = os.path.join(DATA_DIR, "FINAL_Tender_Report_2021_2025_TEMP.xlsx")

print("1. Loading verified company database (8,411 companies)...")
with open(os.path.join(DATA_DIR, "tender_companies_ai_verified.json"), "r", encoding="utf-8") as f:
    tc_list = json.load(f)

def norm(s):
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»“”]', '', s)
    s = re.sub(r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН)\b', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

tc_by_exact = {c.get('тендерийн_нэр', '').strip(): c for c in tc_list}
tc_by_norm = {}
for c in tc_list:
    nm = norm(c.get('тендерийн_нэр', ''))
    if nm and nm not in tc_by_norm:
        tc_by_norm[nm] = c

manual_map = {
    'China Railway Construction Bridge Engineering Bureau Group Co., Ltd.': 'China Railway Construction Bridge Engineering Bureau Group Co., Ltd',
    'Dohwa Engineering Co., Ltd.': 'Dohwa Engineering Co., Ltd',
    'INHEMETER CO.,LTD.': 'INHEMETER CO.,LTD',
    'SHARE FUTURE TECHNOLOGY (BEIJING) CO.,LTD.': 'SHARE FUTURE TECHNOLOGY (BEIJING) CO.,LTD',
    '同方威视技术股份有限公司 _x000D_NUCTECH COMPANY LIMITED': '同方威视技术股份有限公司 NUCTECH COMPANY LIMITED'
}

def get_canonical_tc(raw_name):
    r = raw_name.strip()
    if r in tc_by_exact:
        return tc_by_exact[r]
    if r in manual_map and manual_map[r] in tc_by_exact:
        return tc_by_exact[manual_map[r]]
    nm = norm(r)
    if nm in tc_by_norm:
        return tc_by_norm[nm]
    return tc_by_exact.get(r, {})

print("2. Loading burtgel_les.db for additional verification...")
conn = sqlite3.connect(os.path.join(DATA_DIR, "burtgel_les.db"))
cur = conn.cursor()

print("3. Loading raw detailed tender dataset...")
df_tenders = pd.read_excel(RAW_TENDER_FILE)
print(f"   Loaded {len(df_tenders):,} tender records.")

# Clean known clerical typo row
outlier_mask = (df_tenders['Гэрээний дүн'] > 1_000_000_000_000_000) & (df_tenders['Тендерийн нэр'] == 'Урсгал засвар')
if outlier_mask.any():
    print("   Fixing double-typed contract price typo in row 43999...")
    df_tenders.loc[outlier_mask, 'Гэрээний дүн'] = 23789200.0

# Map to canonical company name and clean register number
def get_clean_reg(v):
    if pd.isna(v) or v == '':
        return ''
    try:
        f = float(v)
        if np.isnan(f):
            return ''
        return str(int(f))
    except:
        return str(v).replace('.0', '').strip()

df_tenders['clean_company'] = df_tenders['Шалгарсан байгууллага'].fillna('').astype(str).str.strip().apply(
    lambda x: get_canonical_tc(x).get('тендерийн_нэр', x)
)
df_tenders['clean_reg'] = df_tenders['Регистрийн дугаар'].apply(get_clean_reg)

# Dates parsing
df_tenders['contract_dt'] = pd.to_datetime(df_tenders['Гэрээ байгуулсан огноо'], errors='coerce')
df_tenders['announced_dt'] = pd.to_datetime(df_tenders['Зарласан огноо'], errors='coerce')
df_tenders['closed_dt'] = pd.to_datetime(df_tenders['Санал хүлээн авах огноо'], errors='coerce')

# Consistent Tender Year logic: Code Year -> Announced Year -> Contract Year -> Clip to [2021, 2025]
def get_tender_year(row):
    code = str(row.get('Тендерийн дугаар', ''))
    m = re.search(r'/(202[1-5])', code)
    if m:
        return int(m.group(1))
    ann = row.get('announced_dt')
    if pd.notna(ann) and 2021 <= ann.year <= 2025:
        return int(ann.year)
    con = row.get('contract_dt')
    if pd.notna(con) and 2021 <= con.year <= 2025:
        return int(con.year)
    m_any = re.search(r'/(20[1-3][0-9])', code)
    if m_any:
        y = int(m_any.group(1))
        if y < 2021: return 2021
        if y > 2025: return 2025
        return y
    return 2021

df_tenders['Тендерийн он'] = df_tenders.apply(get_tender_year, axis=1)

# Calculate Duration in Days (Зарласнаас хаагдах хүртэлх хугацаа)
duration_days = (df_tenders['closed_dt'] - df_tenders['announced_dt']).dt.total_seconds() / 86400.0
# Negative or > 365 days are sanitized
duration_days = duration_days.apply(lambda d: round(d, 1) if pd.notna(d) and 0 <= d <= 365 else np.nan)
df_tenders['Хугацаа_хоног'] = duration_days

# Calculate Financial Comparisons
budget_col = pd.to_numeric(df_tenders['Нийт төсөвт өртөг'], errors='coerce')
contract_col = pd.to_numeric(df_tenders['Гэрээний дүн'], errors='coerce')

df_tenders['budget_clean'] = budget_col
df_tenders['contract_clean'] = contract_col
df_tenders['savings'] = budget_col - contract_col

# Discount percentage: (Budget - Contract) / Budget * 100
def calc_discount(b, c):
    if pd.isna(b) or pd.isna(c) or b <= 0:
        return np.nan
    pct = ((b - c) / b) * 100.0
    if -100 <= pct <= 100:
        return round(pct, 2)
    return np.nan

df_tenders['discount_pct'] = [calc_discount(b, c) for b, c in zip(budget_col, contract_col)]

print("4. Enriching every tender row with LesOutput / burtgel_les company data...")
company_meta = {}

for comp_name, group in df_tenders.groupby('clean_company'):
    sample_reg = group['clean_reg'].replace('', np.nan).dropna()
    reg = sample_reg.iloc[0] if len(sample_reg) > 0 else ''
    
    tc_info = get_canonical_tc(comp_name)
    
    if tc_info:
        c_reg = tc_info.get('регистрийн_дугаар') or reg
        c_ubo = tc_info.get('эцсийн_өмчлөгч', '')
        c_ceo = tc_info.get('гүйцэтгэх_захирал', '')
        c_sh = tc_info.get('хувьцаа_эзэмшигчид', '')
        c_date = tc_info.get('бүртгэсэн_огноо', '')
        c_form = tc_info.get('хэлбэр', '')
        c_act = tc_info.get('үйл_ажиллагааны_чиглэл', '')
        c_addr = tc_info.get('хаяг', '')
        c_status = tc_info.get('төлөв', 'идэвхтэй')
    else:
        c_reg = reg
        c_ubo, c_ceo, c_sh, c_date, c_form, c_act, c_addr, c_status = '', '', '', '', '', '', '', 'идэвхтэй'
        if reg:
            cur.execute("SELECT reg_date, form, address, activities FROM companies WHERE reg_no = ?", (reg,))
            r = cur.fetchone()
            if r:
                c_date, c_form, c_addr, c_act = r[0] or '', r[1] or '', r[2] or '', r[3] or ''
            cur.execute("SELECT role, full_name FROM company_people WHERE reg_no = ?", (reg,))
            for p_role, p_name in cur.fetchall():
                p_role_str = (p_role or '').lower()
                if 'өмчлөгч' in p_role_str and not c_ubo:
                    c_ubo = p_name
                elif ('захирал' in p_role_str or 'төлөөлөх' in p_role_str) and not c_ceo:
                    c_ceo = p_name
                elif 'эзэмшигч' in p_role_str:
                    c_sh = (c_sh + ', ' + p_name).strip(', ')

    comp_total_amt = group['contract_clean'].sum()
    
    company_meta[comp_name] = {
        'reg_no': get_clean_reg(c_reg),
        'ubo': c_ubo,
        'ceo': c_ceo,
        'shareholders': c_sh,
        'reg_date': c_date,
        'form': c_form,
        'activities': c_act,
        'address': c_addr,
        'status': c_status,
        'total_contract_amt': comp_total_amt,
        'tender_count': len(group)
    }

# Map meta into df_tenders
df_tenders['comp_total_amt'] = df_tenders['clean_company'].map(lambda x: company_meta.get(x, {}).get('total_contract_amt', 0))
df_tenders['meta_reg'] = df_tenders['clean_company'].map(lambda x: company_meta.get(x, {}).get('reg_no', ''))
df_tenders['meta_ubo'] = df_tenders['clean_company'].map(lambda x: company_meta.get(x, {}).get('ubo', ''))
df_tenders['meta_ceo'] = df_tenders['clean_company'].map(lambda x: company_meta.get(x, {}).get('ceo', ''))
df_tenders['meta_reg_date'] = df_tenders['clean_company'].map(lambda x: company_meta.get(x, {}).get('reg_date', ''))

# Clean dates formatting
def fmt_date_str(val):
    if pd.isna(val) or val is None or str(val) == 'nan':
        return ''
    s = str(val).strip()
    return s[:16] if ' ' in s else s[:10]

df_tenders['date_announced_str'] = df_tenders['Зарласан огноо'].apply(fmt_date_str)
df_tenders['date_closed_str'] = df_tenders['Санал хүлээн авах огноо'].apply(fmt_date_str)
df_tenders['date_contract_str'] = df_tenders['Гэрээ байгуулсан огноо'].apply(fmt_date_str)

print("5. Sorting detailed tenders hierarchically:")
print("   Order: Company Total Won (Desc) -> Company Name -> Year (Asc) -> Announced Date (Asc)")
df_tenders = df_tenders.sort_values(
    by=['comp_total_amt', 'clean_company', 'Тендерийн он', 'announced_dt'],
    ascending=[False, True, True, True]
).reset_index(drop=True)

print("6. Preparing Sheet 1: 8,411 Companies Master Registry...")
# Aggregate stats directly from df_tenders for 100% reconciliation
comp_year_stats = {}
for (c_name, y), grp in df_tenders.groupby(['clean_company', 'Тендерийн он']):
    if c_name not in comp_year_stats:
        comp_year_stats[c_name] = {}
    comp_year_stats[c_name][y] = {
        'count': len(grp),
        'amt': grp['contract_clean'].sum()
    }

# Build rich 8,411 company list sorted by total contract amount
companies_rows = []
for idx, c in enumerate(tc_list):
    name = c.get('тендерийн_нэр', '')
    meta = company_meta.get(name, {})
    c_stats = comp_year_stats.get(name, {})
    
    # Calculate real totals from tender rows
    real_cnt = sum(c_stats.get(y, {}).get('count', 0) for y in [2021, 2022, 2023, 2024, 2025])
    real_amt = sum(c_stats.get(y, {}).get('amt', 0.0) for y in [2021, 2022, 2023, 2024, 2025])

    companies_rows.append({
        'Компанийн нэр': name,
        'Регистрийн дугаар': get_clean_reg(c.get('регистрийн_дугаар') or meta.get('reg_no', '')),
        'Бүртгэлийн нэр': c.get('бүртгэлийн_нэр', ''),
        'Компанийн хэлбэр': c.get('хэлбэр', ''),
        'Бүртгэсэн огноо': c.get('бүртгэсэн_огноо') or meta.get('reg_date', ''),
        'Төлөв': c.get('төлөв', 'идэвхтэй'),
        'Эцсийн өмчлөгч (UBO)': c.get('эцсийн_өмчлөгч') or meta.get('ubo', ''),
        'Хувьцаа эзэмшигчид': c.get('хувьцаа_эзэмшигчид') or meta.get('shareholders', ''),
        'Гүйцэтгэх захирал': c.get('гүйцэтгэх_захирал') or meta.get('ceo', ''),
        'Үйл ажиллагааны чиглэл': c.get('үйл_ажиллагааны_чиглэл', ''),
        'Албан ёсны хаяг': c.get('хаяг', ''),
        'Шалгарсан нийт тендерийн тоо': real_cnt,
        'Гэрээний нийт дүн (₮)': real_amt,
        '2021 он: Тоо': c_stats.get(2021, {}).get('count', 0),
        '2021 он: Дүн (₮)': c_stats.get(2021, {}).get('amt', 0.0),
        '2022 он: Тоо': c_stats.get(2022, {}).get('count', 0),
        '2022 он: Дүн (₮)': c_stats.get(2022, {}).get('amt', 0.0),
        '2023 он: Тоо': c_stats.get(2023, {}).get('count', 0),
        '2023 он: Дүн (₮)': c_stats.get(2023, {}).get('amt', 0.0),
        '2024 он: Тоо': c_stats.get(2024, {}).get('count', 0),
        '2024 он: Дүн (₮)': c_stats.get(2024, {}).get('amt', 0.0),
        '2025 он: Тоо': c_stats.get(2025, {}).get('count', 0),
        '2025 он: Дүн (₮)': c_stats.get(2025, {}).get('amt', 0.0),
    })

df_companies = pd.DataFrame(companies_rows)
df_companies['Гэрээний нийт дүн (₮)'] = pd.to_numeric(df_companies['Гэрээний нийт дүн (₮)'], errors='coerce').fillna(0)
# Sort by total contract amount descending
df_companies = df_companies.sort_values(by='Гэрээний нийт дүн (₮)', ascending=False).reset_index(drop=True)
df_companies.insert(0, '№', range(1, len(df_companies) + 1))

print(f"   Companies master prepared: {len(df_companies):,} companies.")

print("7. Writing multi-sheet Excel file with xlsxwriter...")
wb = xlsxwriter.Workbook(OUTPUT_TEMP, {'constant_memory': False})

# ==========================================
# PALETTES & FORMATS
# ==========================================
# Super Headers
fmt_sup_blue = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10.5, 'font_color': '#FFFFFF', 'bg_color': '#1E3A8A', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#3B82F6'})
fmt_sup_navy = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10.5, 'font_color': '#FFFFFF', 'bg_color': '#1E293B', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#475569'})
fmt_sup_teal = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10.5, 'font_color': '#FFFFFF', 'bg_color': '#0F766E', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#14B8A6'})
fmt_sup_gold = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10.5, 'font_color': '#FFFFFF', 'bg_color': '#854D0E', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#CA8A04'})

# Column Headers
fmt_hdr_blue = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'font_color': '#FFFFFF', 'bg_color': '#2563EB', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#60A5FA', 'text_wrap': True})
fmt_hdr_navy = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'font_color': '#FFFFFF', 'bg_color': '#334155', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#64748B', 'text_wrap': True})
fmt_hdr_teal = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'font_color': '#FFFFFF', 'bg_color': '#0D9488', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#2DD4BF', 'text_wrap': True})
fmt_hdr_gold = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'font_color': '#FFFFFF', 'bg_color': '#A16207', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FACC15', 'text_wrap': True})

# Cell Formats - Even (White)
fmt_text_e = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_bold_e = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'font_color': '#0F172A', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_center_e = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_curr_e = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'num_format': '#,##0 "₮"', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_int_e = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_days_e = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'num_format': '0.0 "хоног"', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_pct_e = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'num_format': '0.0%', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})

# Cell Formats - Odd (#F8FAFC)
fmt_text_o = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_bold_o = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'font_color': '#0F172A', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_center_o = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_curr_o = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'num_format': '#,##0 "₮"', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_int_o = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_days_o = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'num_format': '0.0 "хоног"', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})
fmt_pct_o = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'num_format': '0.0%', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#E2E8F0'})

# Badges for Tender Types
badge_baraa = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#EFF6FF', 'font_color': '#1D4ED8', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE'})
badge_ajil = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#ECFDF5', 'font_color': '#047857', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#A7F3D0'})
badge_uilch = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#FEF3C7', 'font_color': '#B45309', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FDE68A'})
badge_zuvluh = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#FAF5FF', 'font_color': '#7E22CE', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E9D5FF'})

# ==========================================
# BUILD SHEET 1: 🏢 Компаниудын нэгдсэн карт
# ==========================================
print("   Writing Sheet 1: 🏢 Компаниудын нэгдсэн карт...")
ws_comp = wb.add_worksheet('🏢 Компаниудын нэгдсэн карт')
ws_comp.set_tab_color('#1E3A8A')
ws_comp.freeze_panes(1, 3)

comp_cols_cfg = [
    ('№', 'center', 6),
    ('Компанийн нэр', 'bold', 32),
    ('Регистрийн дугаар', 'center', 15),
    ('Бүртгэлийн нэр', 'text', 28),
    ('Компанийн хэлбэр', 'center', 22),
    ('Бүртгэсэн огноо', 'center', 14),
    ('Төлөв', 'center', 12),
    ('Эцсийн өмчлөгч (UBO)', 'bold', 28),
    ('Хувьцаа эзэмшигчид', 'text', 32),
    ('Гүйцэтгэх захирал', 'bold', 24),
    ('Үйл ажиллагааны чиглэл', 'text', 40),
    ('Албан ёсны хаяг', 'text', 35),
    ('Шалгарсан нийт тендерийн тоо', 'int', 18),
    ('Гэрээний нийт дүн (₮)', 'curr', 22),
    ('2021 он: Тоо', 'int', 14),
    ('2021 он: Дүн (₮)', 'curr', 18),
    ('2022 он: Тоо', 'int', 14),
    ('2022 он: Дүн (₮)', 'curr', 18),
    ('2023 он: Тоо', 'int', 14),
    ('2023 он: Дүн (₮)', 'curr', 18),
    ('2024 он: Тоо', 'int', 14),
    ('2024 он: Дүн (₮)', 'curr', 18),
    ('2025 он: Тоо', 'int', 14),
    ('2025 он: Дүн (₮)', 'curr', 18),
]

for col_idx, (col_name, _, col_width) in enumerate(comp_cols_cfg):
    ws_comp.write(0, col_idx, col_name, fmt_hdr_blue)
    ws_comp.set_column(col_idx, col_idx, col_width)
ws_comp.set_row(0, 28)

for r_idx, r in df_companies.iterrows():
    is_odd = (r_idx % 2 == 1)
    f_t = fmt_text_o if is_odd else fmt_text_e
    f_b = fmt_bold_o if is_odd else fmt_bold_e
    f_c = fmt_center_o if is_odd else fmt_center_e
    f_curr = fmt_curr_o if is_odd else fmt_curr_e
    f_int = fmt_int_o if is_odd else fmt_int_e
    
    sh_row = r_idx + 1
    for c_idx, (col_name, c_type, _) in enumerate(comp_cols_cfg):
        val = r.get(col_name)
        if pd.isna(val) or val is None or str(val) == 'nan':
            ws_comp.write_blank(sh_row, c_idx, None, f_c)
            continue
        if c_type == 'curr':
            ws_comp.write_number(sh_row, c_idx, float(val), f_curr)
        elif c_type == 'int':
            ws_comp.write_number(sh_row, c_idx, int(float(val)), f_int)
        elif c_type == 'bold':
            ws_comp.write_string(sh_row, c_idx, str(val), f_b)
        elif c_type == 'center':
            s_val = str(val).strip()
            if s_val.endswith('.0'):
                s_val = s_val[:-2]
            ws_comp.write_string(sh_row, c_idx, s_val, f_c)
        else:
            ws_comp.write_string(sh_row, c_idx, str(val), f_t)

ws_comp.autofilter(0, 0, len(df_companies), len(comp_cols_cfg) - 1)

# ==========================================
# BUILD SHEET 2: 📑 Тендер тус бүрийн аналитик задаргаа
# ==========================================
print("   Writing Sheet 2: 📑 Тендер тус бүрийн аналитик задаргаа (64,194 records)...")
ws_ten = wb.add_worksheet('📑 Тендерийн задаргаа')
ws_ten.set_tab_color('#0D9488')
ws_ten.freeze_panes(2, 2)

# Super Headers
ws_ten.merge_range(0, 0, 0, 4, '1. ШАЛГАРСАН КОМПАНИ БА ЭЗЭМШИЛ (LesOutputJson)', fmt_sup_blue)
ws_ten.merge_range(0, 5, 0, 11, '2. ТЕНДЕРИЙН ҮНДСЭН МЭДЭЭЛЭЛ', fmt_sup_navy)
ws_ten.merge_range(0, 12, 0, 15, '3. ХУГАЦААНЫ ХАРЬЦУУЛАЛТ (Зарласан ба Хаагдсан)', fmt_sup_teal)
ws_ten.merge_range(0, 16, 0, 19, '4. ҮНИЙН ХАРЬЦУУЛАЛТ (Төсөвт өртөг ба Гэрээний үнэ)', fmt_sup_gold)

tender_cols_cfg = [
    # Group 1: Компани ба Эзэмшил
    ('Шалгарсан компани', 'clean_company', 'bold', fmt_hdr_blue, 32),
    ('Регистрийн дугаар', 'meta_reg', 'center', fmt_hdr_blue, 16),
    ('Эцсийн өмчлөгч (UBO)', 'meta_ubo', 'bold', fmt_hdr_blue, 26),
    ('Гүйцэтгэх захирал', 'meta_ceo', 'text', fmt_hdr_blue, 24),
    ('Компани байгуулагдсан огноо', 'meta_reg_date', 'center', fmt_hdr_blue, 16),
    
    # Group 2: Тендерийн үндсэн мэдээлэл
    ('Тендерийн он', 'Тендерийн он', 'center', fmt_hdr_navy, 12),
    ('Тендерийн дугаар', 'Тендерийн дугаар', 'bold_center', fmt_hdr_navy, 18),
    ('Тендерийн нэр', 'Тендерийн нэр', 'text', fmt_hdr_navy, 36),
    ('Төрөл', 'Төрөл', 'badge_type', fmt_hdr_navy, 14),
    ('Шалгаруулалтын арга', 'Арга', 'text', fmt_hdr_navy, 28),
    ('Санхүүжилтийн эх үүсвэр', 'Санхүүжилтийн эх үүсвэр', 'text', fmt_hdr_navy, 24),
    ('Захиалагч байгууллага', 'Захиалагч', 'text', fmt_hdr_navy, 34),
    
    # Group 3: Хугацааны харьцуулалт
    ('Зарласан огноо', 'date_announced_str', 'center', fmt_hdr_teal, 16),
    ('Санал хүлээн авах (хаагдсан)', 'date_closed_str', 'center', fmt_hdr_teal, 18),
    ('⏱ Зарласнаас хаагдсан (хоног)', 'Хугацаа_хоног', 'days', fmt_hdr_teal, 18),
    ('Гэрээ байгуулсан огноо', 'date_contract_str', 'center', fmt_hdr_teal, 16),
    
    # Group 4: Үнийн харьцуулалт
    ('Нийт төсөвт өртөг (₮)', 'budget_clean', 'curr', fmt_hdr_gold, 20),
    ('Гэрээний үнэ / дүн (₮)', 'contract_clean', 'curr', fmt_hdr_gold, 20),
    ('Төсвийн зөрүү / Хэмнэлт (₮)', 'savings', 'curr', fmt_hdr_gold, 20),
    ('📉 Үнийн бууралт (%)', 'discount_pct', 'pct', fmt_hdr_gold, 16),
]

for col_idx, (hdr_name, _, _, hdr_fmt, col_width) in enumerate(tender_cols_cfg):
    ws_ten.write(1, col_idx, hdr_name, hdr_fmt)
    ws_ten.set_column(col_idx, col_idx, col_width)

ws_ten.set_row(0, 24)
ws_ten.set_row(1, 28)

# Streaming data into Sheet 2
num_t_cols = len(tender_cols_cfg)
col_series = [df_tenders[field].values for _, field, _, _, _ in tender_cols_cfg]

for r_idx in range(len(df_tenders)):
    is_odd = (r_idx % 2 == 1)
    f_t = fmt_text_o if is_odd else fmt_text_e
    f_b = fmt_bold_o if is_odd else fmt_bold_e
    f_c = fmt_center_o if is_odd else fmt_center_e
    f_curr = fmt_curr_o if is_odd else fmt_curr_e
    f_days = fmt_days_o if is_odd else fmt_days_e
    f_pct = fmt_pct_o if is_odd else fmt_pct_e
    
    sh_row = r_idx + 2
    
    for c_idx in range(num_t_cols):
        val = col_series[c_idx][r_idx]
        c_type = tender_cols_cfg[c_idx][2]
        
        if pd.isna(val) or val is None or str(val) == 'nan' or str(val) == '':
            ws_ten.write_blank(sh_row, c_idx, None, f_c)
            continue
            
        if c_type == 'curr':
            ws_ten.write_number(sh_row, c_idx, float(val), f_curr)
        elif c_type == 'days':
            ws_ten.write_number(sh_row, c_idx, float(val), f_days)
        elif c_type == 'pct':
            # Store as decimal for standard Excel percentage formatting (0.054 -> 5.4%)
            ws_ten.write_number(sh_row, c_idx, float(val) / 100.0, f_pct)
        elif c_type == 'bold':
            ws_ten.write_string(sh_row, c_idx, str(val), f_b)
        elif c_type in ('center', 'bold_center'):
            s_val = str(val).strip()
            if s_val.endswith('.0'):
                s_val = s_val[:-2]
            ws_ten.write_string(sh_row, c_idx, s_val, f_b if c_type == 'bold_center' else f_c)
        elif c_type == 'badge_type':
            val_str = str(val).strip()
            if 'Бараа' in val_str:
                ws_ten.write_string(sh_row, c_idx, val_str, badge_baraa)
            elif 'Ажил' in val_str:
                ws_ten.write_string(sh_row, c_idx, val_str, badge_ajil)
            elif 'Үйлчилгээ' in val_str:
                ws_ten.write_string(sh_row, c_idx, val_str, badge_uilch)
            elif 'Зөвлөх' in val_str:
                ws_ten.write_string(sh_row, c_idx, val_str, badge_zuvluh)
            else:
                ws_ten.write_string(sh_row, c_idx, val_str, f_c)
        else:
            ws_ten.write_string(sh_row, c_idx, str(val), f_t)
            
    if r_idx > 0 and r_idx % 20000 == 0:
        print(f"      Written {r_idx:,} / {len(df_tenders):,} tender records...")

ws_ten.autofilter(1, 0, len(df_tenders) + 1, num_t_cols - 1)

print("8. Closing workbook and saving atomically...")
wb.close()
print("   Workbook generated successfully!")

# Move temporary file to final target
os.replace(OUTPUT_TEMP, OUTPUT_FILE)
print(f"SUCCESS! Perfectly formatted and merged dataset saved to: {OUTPUT_FILE}")
