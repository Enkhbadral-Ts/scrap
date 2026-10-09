# -*- coding: utf-8 -*-
"""
Professional Executive Styling & Structuring for Tender Report (2021-2025)
Author: Antigravity IDE
Features:
1. Executive Dashboard (KPI Summary Cards, Yearly comparisons, Tender Types, Procurement Methods, Funding Sources)
2. Detailed Tender Master Sheet (64,194 records with thematic grouped headers, frozen panes, zebra striping, currency formatting)
3. Top 100 Suppliers (Ranking, win count, total contracts, glass accounts verification)
4. Top 100 Buyers / Procuring Entities (Ranking, tender count, budget, contract sum, savings)
"""

import os
import shutil
import pandas as pd
import numpy as np
import xlsxwriter

SRC_FILE = "/Users/enkhbadraltsogbayar/Tender data/FINAL_Tender_Report_2021_2025_With_Details.xlsx"
BACKUP_FILE = "/Users/enkhbadraltsogbayar/Tender data/FINAL_Tender_Report_2021_2025_With_Details_RAW_BACKUP.xlsx"
TEMP_OUTPUT = "/Users/enkhbadraltsogbayar/Tender data/FINAL_Tender_Report_2021_2025_Styled_TEMP.xlsx"

print("1. Creating backup of original raw file...")
if not os.path.exists(BACKUP_FILE):
    shutil.copyfile(SRC_FILE, BACKUP_FILE)
    print(f"   Backup saved: {BACKUP_FILE}")
else:
    print(f"   Backup already exists: {BACKUP_FILE}")

print("2. Reading raw dataset with pandas...")
df = pd.read_excel(SRC_FILE)
print(f"   Loaded {len(df):,} rows.")

# Data Cleanups & Fixes
# Fix known clerical outlier typo: row 43999 where 23789200 was typed twice
outlier_mask = (df['Гэрээний дүн'] > 1_000_000_000_000_000) & (df['Тендерийн нэр'] == 'Урсгал засвар')
if outlier_mask.any():
    print("   Fixing clerical double-typed outlier in row 43999...")
    df.loc[outlier_mask, 'Гэрээний дүн'] = 23789200.0

# Clean Address
df['Хаяг'] = df['Хаяг'].fillna('').astype(str).replace({'$undefined': '', 'undefined': ''})

# Clean Contact
df['Холбоо барих'] = df['Холбоо барих'].fillna('').astype(str)

# Clean Reg No
def clean_reg(v):
    if pd.isna(v) or v == '':
        return ''
    try:
        f = float(v)
        if np.isnan(f):
            return ''
        return str(int(f))
    except:
        return str(v)

df['Регистрийн дугаар'] = df['Регистрийн дугаар'].apply(clean_reg)

# Calculate Savings
df['Төсвийн хэмнэлт'] = df['Нийт төсөвт өртөг'] - df['Гэрээний дүн']

# Year of Contract
df['Гэрээний он'] = pd.to_datetime(df['Гэрээ байгуулсан огноо'], errors='coerce').dt.year
df['Гэрээний он'] = df['Гэрээний он'].fillna(0).astype(int)

# Reorder columns into 5 logical categories:
# 1. Ерөнхий мэдээлэл (Slate Navy)
# 2. Төсөв, санхүүжилт (Emerald Green)
# 3. Хугацаа, огноо (Ocean Teal)
# 4. Оролцогч талууд (Royal Indigo)
# 5. Шилэн дансны тулгалт (Plum Violet)
COLUMNS_ORDER = [
    # Group 1: Ерөнхий мэдээлэл
    ('Тендерийн дугаар', 'Тендерийн дугаар', 'code', 18),
    ('Тендерийн нэр', 'Тендерийн нэр', 'text', 38),
    ('Төрөл', 'Төрөл', 'badge_type', 14),
    ('Арга', 'Шалгаруулалтын арга', 'text', 28),
    ('Цахим тендер эсэх', 'Цахим эсэх', 'center', 12),
    
    # Group 2: Төсөв, санхүү
    ('Санхүүжилтийн эх үүсвэр', 'Санхүүжилтийн эх үүсвэр', 'text', 24),
    ('Нийт төсөвт өртөг', 'Нийт төсөвт өртөг (₮)', 'currency', 18),
    ('Гэрээний дүн', 'Гэрээний дүн (₮)', 'currency', 18),
    ('Төсвийн хэмнэлт', 'Төсвийн хэмнэлт (₮)', 'currency', 18),
    
    # Group 3: Хугацаа, огноо
    ('Зарласан огноо', 'Зарласан огноо', 'center', 16),
    ('Санал хүлээн авах огноо', 'Санал хүлээн авах', 'center', 16),
    ('Нээх огноо', 'Нээх огноо', 'center', 16),
    ('Гэрээ байгуулсан огноо', 'Гэрээ байгуулсан', 'center', 16),
    
    # Group 4: Талууд
    ('Захиалагч', 'Захиалагч байгууллага', 'text', 32),
    ('Шалгарсан байгууллага', 'Шалгарсан байгууллага', 'bold_text', 32),
    ('Регистрийн дугаар', 'Регистрийн дугаар', 'center', 16),
    ('Холбоо барих', 'Холбоо барих', 'text', 26),
    ('Хаяг', 'Байршил / Хаяг', 'text', 20),
    
    # Group 5: Шилэн данс
    ('Таарсан арга', 'Тулгасан арга', 'center', 15),
    ('Шилэн данс - Нийт авсан дүн', 'Шилэн данс: Нийт авсан (₮)', 'currency', 20),
    ('Шилэн данс - Гүйлгээний тоо', 'Шилэн данс: Гүйлгээний тоо', 'integer', 16),
    ('Шилэн данс - Шилжүүлэгч байгууллагууд', 'Шилэн данс: Шилжүүлэгч', 'text', 32)
]

print("3. Preparing Aggregations for Executive Dashboard & Rankings...")

# Valid 2021-2025 tenders for dashboard
df_recent = df[(df['Гэрээний он'] >= 2021) & (df['Гэрээний он'] <= 2025)].copy()

total_tenders = len(df)
total_budget = df['Нийт төсөвт өртөг'].sum()
total_contract = df['Гэрээний дүн'].sum()
total_savings = df['Төсвийн хэмнэлт'].sum()
glass_matched_count = df['Шилэн данс - Нийт авсан дүн'].notna().sum()
glass_matched_sum = df['Шилэн данс - Нийт авсан дүн'].sum()

# Yearly breakdown
yearly_stats = df_recent.groupby('Гэрээний он').agg(
    tender_count=('Тендерийн дугаар', 'count'),
    budget_sum=('Нийт төсөвт өртөг', 'sum'),
    contract_sum=('Гэрээний дүн', 'sum'),
    savings_sum=('Төсвийн хэмнэлт', 'sum')
).reset_index()
yearly_stats['savings_pct'] = (yearly_stats['savings_sum'] / yearly_stats['budget_sum'] * 100).fillna(0)

# Type breakdown
type_stats = df['Төрөл'].fillna('Тодорхойгүй').value_counts().reset_index()
type_stats.columns = ['Төрөл', 'Тоо']
type_stats['Эзлэх хувь'] = type_stats['Тоо'] / total_tenders * 100
type_sum = df.groupby(df['Төрөл'].fillna('Тодорхойгүй'))['Гэрээний дүн'].sum().reset_index()
type_sum.columns = ['Төрөл', 'Гэрээний нийт дүн']
type_stats = pd.merge(type_stats, type_sum, on='Төрөл')

# Top 100 Suppliers
print("   Aggregating Top 100 Suppliers...")
top_suppliers = df.groupby(['Шалгарсан байгууллага', 'Регистрийн дугаар'], as_index=False).agg(
    tender_count=('Тендерийн дугаар', 'count'),
    contract_sum=('Гэрээний дүн', 'sum'),
    budget_sum=('Нийт төсөвт өртөг', 'sum'),
    glass_sum=('Шилэн данс - Нийт авсан дүн', 'max'),
    glass_count=('Шилэн данс - Гүйлгээний тоо', 'max'),
    main_client=('Захиалагч', lambda x: x.mode()[0] if not x.empty else '')
).sort_values(by='contract_sum', ascending=False).head(100).reset_index(drop=True)
top_suppliers.insert(0, '№', range(1, len(top_suppliers) + 1))

# Top 100 Buyers
print("   Aggregating Top 100 Procuring Entities...")
top_buyers = df.groupby('Захиалагч', as_index=False).agg(
    tender_count=('Тендерийн дугаар', 'count'),
    budget_sum=('Нийт төсөвт өртөг', 'sum'),
    contract_sum=('Гэрээний дүн', 'sum'),
    savings_sum=('Төсвийн хэмнэлт', 'sum'),
    main_winner=('Шалгарсан байгууллага', lambda x: x.mode()[0] if not x.empty else '')
).sort_values(by='contract_sum', ascending=False).head(100).reset_index(drop=True)
top_buyers.insert(0, '№', range(1, len(top_buyers) + 1))
top_buyers['savings_pct'] = (top_buyers['savings_sum'] / top_buyers['budget_sum'] * 100).fillna(0)

# Funding sources
funding_stats = df['Санхүүжилтийн эх үүсвэр'].fillna('Тодорхойгүй').value_counts().head(8).reset_index()
funding_stats.columns = ['Санхүүжилт', 'Тоо']
funding_stats['Эзлэх хувь'] = funding_stats['Тоо'] / total_tenders * 100
funding_sum = df.groupby(df['Санхүүжилтийн эх үүсвэр'].fillna('Тодорхойгүй'))['Гэрээний дүн'].sum().reset_index()
funding_sum.columns = ['Санхүүжилт', 'Гэрээний дүн']
funding_stats = pd.merge(funding_stats, funding_sum, on='Санхүүжилт')

print("4. Writing workbook using xlsxwriter with Executive Themes...")
wb = xlsxwriter.Workbook(TEMP_OUTPUT, {'constant_memory': False})

# ==========================================
# PALETTE & FORMAT DEFINITIONS
# ==========================================
# Headers
fmt_hdr_navy = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'font_color': '#FFFFFF', 'bg_color': '#1E293B', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155', 'text_wrap': True})
fmt_hdr_emerald = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'font_color': '#FFFFFF', 'bg_color': '#065F46', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#047857', 'text_wrap': True})
fmt_hdr_teal = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'font_color': '#FFFFFF', 'bg_color': '#0E7490', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#0891B2', 'text_wrap': True})
fmt_hdr_indigo = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'font_color': '#FFFFFF', 'bg_color': '#3730A3', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#4338CA', 'text_wrap': True})
fmt_hdr_violet = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 10, 'font_color': '#FFFFFF', 'bg_color': '#581C87', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#6B21A8', 'text_wrap': True})

# Group Super-headers
fmt_super_navy = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 11, 'font_color': '#FFFFFF', 'bg_color': '#0F172A', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155'})
fmt_super_emerald = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 11, 'font_color': '#FFFFFF', 'bg_color': '#064E3B', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#047857'})
fmt_super_teal = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 11, 'font_color': '#FFFFFF', 'bg_color': '#155E75', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#0891B2'})
fmt_super_indigo = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 11, 'font_color': '#FFFFFF', 'bg_color': '#312E81', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#4338CA'})
fmt_super_violet = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 11, 'font_color': '#FFFFFF', 'bg_color': '#3B0764', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#6B21A8'})

# Data Formats - Zebra Even (White)
fmt_text_even = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_bold_even = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'font_color': '#0F172A', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_center_even = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_code_even = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'font_color': '#1E293B', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_curr_even = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'num_format': '#,##0 "₮"', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_int_even = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#FFFFFF', 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})

# Data Formats - Zebra Odd (#F8FAFC)
fmt_text_odd = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_bold_odd = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'font_color': '#0F172A', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_center_odd = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_code_odd = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'font_color': '#1E293B', 'align': 'center', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_curr_odd = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'num_format': '#,##0 "₮"', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})
fmt_int_odd = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F8FAFC', 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'bottom': 1, 'top': 1, 'left': 1, 'right': 1, 'border_color': '#E2E8F0'})

# Badges for Types
fmt_badge_baraa = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#EFF6FF', 'font_color': '#1D4ED8', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#BFDBFE'})
fmt_badge_ajil = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#ECFDF5', 'font_color': '#047857', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#A7F3D0'})
fmt_badge_uilch = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#FEF3C7', 'font_color': '#B45309', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#FDE68A'})
fmt_badge_zuvluh = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'bg_color': '#FAF5FF', 'font_color': '#7E22CE', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#E9D5FF'})

# ==========================================
# 1. SHEET: 📊 Хяналтын самбар (Executive Dashboard)
# ==========================================
print("   Building Sheet 1: 📊 Хяналтын самбар...")
ws_dash = wb.add_worksheet('📊 Хяналтын самбар')
ws_dash.set_tab_color('#1E293B')
# Dashboard Title
ws_dash.hide_gridlines(0)  # Show gridlines
fmt_dash_title = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 18, 'font_color': '#0F172A', 'valign': 'vcenter'})
fmt_dash_sub = wb.add_format({'font_name': 'Segoe UI', 'font_size': 10.5, 'font_color': '#64748B', 'valign': 'vcenter'})
fmt_dash_badge = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#1E293B', 'font_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter'})

ws_dash.write('B2', 'МОНГОЛ УЛСЫН ТӨРИЙН ХУДАЛДАН АВАХ АЖИЛЛАГААНЫ НЭГДСЭН ТАЙЛАН', fmt_dash_title)
ws_dash.write('B3', 'Нийт 64,194 тендер, төсөвт өртөг, гэрээний дүн, захиалагч болон нийлүүлэгчдийн 2021-2025 оны статистик', fmt_dash_sub)

# KPI Cards Styling
def draw_kpi_card(ws, start_col, title, val_str, sub_str, bg_color, border_color, val_color):
    fmt_c_title = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9, 'bold': True, 'font_color': '#64748B', 'bg_color': bg_color, 'left': 1, 'right': 1, 'top': 1, 'border_color': border_color})
    fmt_c_val = wb.add_format({'font_name': 'Segoe UI', 'font_size': 16, 'bold': True, 'font_color': val_color, 'bg_color': bg_color, 'left': 1, 'right': 1, 'border_color': border_color})
    fmt_c_sub = wb.add_format({'font_name': 'Segoe UI', 'font_size': 8.5, 'font_color': '#475569', 'bg_color': bg_color, 'left': 1, 'right': 1, 'bottom': 1, 'border_color': border_color})
    
    ws.merge_range(4, start_col, 4, start_col + 1, title, fmt_c_title)
    ws.merge_range(5, start_col, 5, start_col + 1, val_str, fmt_c_val)
    ws.merge_range(6, start_col, 6, start_col + 1, sub_str, fmt_c_sub)

draw_kpi_card(ws_dash, 1, 'НИЙТ ШАЛГАРСАН ТЕНДЕР', f"{total_tenders:,} гэрээ", "2021 - 2025 он бүрэн хамрагдсан", '#EFF6FF', '#BFDBFE', '#1E40AF')
draw_kpi_card(ws_dash, 3, 'БАТЛАГДСАН ТӨСӨВТ ӨРТӨГ', f"{total_budget/1e12:.1f} Их наяд ₮", f"Нийт: {total_budget:,.0f} ₮", '#ECFDF5', '#A7F3D0', '#065F46')
draw_kpi_card(ws_dash, 5, 'БАЙГУУЛСАН ГЭРЭЭНИЙ ДҮН', f"{total_contract/1e12:.1f} Их наяд ₮", f"Нийт: {total_contract:,.0f} ₮", '#F0FDF4', '#86EFAC', '#166534')
draw_kpi_card(ws_dash, 7, 'ШИЛЭН ДАНС БАТАЛГААЖУУЛАЛТ', f"{glass_matched_count:,} гэрээ ({glass_matched_count/total_tenders*100:.1f}%)", f"Баталгаажсан: {glass_matched_sum/1e12:.1f} Их наяд ₮", '#FAF5FF', '#E9D5FF', '#6B21A8')

# Section Title Format
fmt_sec_hdr = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 11, 'font_color': '#0F172A', 'bottom': 2, 'bottom_color': '#1E293B'})
fmt_tbl_hdr = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'font_color': '#FFFFFF', 'bg_color': '#1E293B', 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155'})
fmt_tbl_hdr_right = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'font_color': '#FFFFFF', 'bg_color': '#1E293B', 'align': 'right', 'valign': 'vcenter', 'border': 1, 'border_color': '#334155'})
fmt_tbl_tot = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F1F5F9', 'border': 1, 'border_color': '#CBD5E1'})
fmt_tbl_tot_curr = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F1F5F9', 'num_format': '#,##0 "₮"', 'align': 'right', 'border': 1, 'border_color': '#CBD5E1'})
fmt_tbl_tot_int = wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'bg_color': '#F1F5F9', 'num_format': '#,##0', 'align': 'right', 'border': 1, 'border_color': '#CBD5E1'})
fmt_tbl_pct = wb.add_format({'font_name': 'Segoe UI', 'font_size': 9.5, 'num_format': '0.0"%"', 'align': 'right', 'border': 1, 'border_color': '#E2E8F0'})

# Table 1: Yearly Comparison
ws_dash.write('B9', '1. ЖИЛ БҮРИЙН ТЕНДЕР, ТӨСӨВ БА ГЭРЭЭНИЙ ХАРЬЦУУЛАЛТ', fmt_sec_hdr)
headers_y = ['Он', 'Тендерийн тоо', 'Батлагдсан төсөв (₮)', 'Гэрээний нийт дүн (₮)', 'Төсвийн хэмнэлт (₮)', 'Хэмнэсэн %']
for col_idx, h in enumerate(headers_y):
    ws_dash.write(9, 1 + col_idx, h, fmt_tbl_hdr if col_idx == 0 else fmt_tbl_hdr_right)

row_c = 10
for _, r in yearly_stats.iterrows():
    ws_dash.write(row_c, 1, int(r['Гэрээний он']), fmt_center_even)
    ws_dash.write(row_c, 2, int(r['tender_count']), fmt_int_even)
    ws_dash.write(row_c, 3, r['budget_sum'], fmt_curr_even)
    ws_dash.write(row_c, 4, r['contract_sum'], fmt_curr_even)
    ws_dash.write(row_c, 5, r['savings_sum'], fmt_curr_even)
    ws_dash.write(row_c, 6, r['savings_pct'] / 100.0, fmt_tbl_pct)
    row_c += 1

# Total Row for Table 1
ws_dash.write(row_c, 1, 'Нийт / Дундаж', fmt_tbl_tot)
ws_dash.write(row_c, 2, yearly_stats['tender_count'].sum(), fmt_tbl_tot_int)
ws_dash.write(row_c, 3, yearly_stats['budget_sum'].sum(), fmt_tbl_tot_curr)
ws_dash.write(row_c, 4, yearly_stats['contract_sum'].sum(), fmt_tbl_tot_curr)
ws_dash.write(row_c, 5, yearly_stats['savings_sum'].sum(), fmt_tbl_tot_curr)
ws_dash.write(row_c, 6, yearly_stats['savings_sum'].sum() / yearly_stats['budget_sum'].sum(), wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 9.5, 'num_format': '0.0"%"', 'align': 'right', 'bg_color': '#F1F5F9', 'border': 1, 'border_color': '#CBD5E1'}))

# Table 2: By Type
row_c += 3
ws_dash.write(row_c - 1, 1, '2. ХУДАЛДАН АВАЛТЫН ТӨРЛӨӨР', fmt_sec_hdr)
headers_t = ['Төрөл', 'Тендерийн тоо', 'Эзлэх хувь (%)', 'Гэрээний нийт дүн (₮)']
for col_idx, h in enumerate(headers_t):
    ws_dash.write(row_c, 1 + col_idx, h, fmt_tbl_hdr if col_idx == 0 else fmt_tbl_hdr_right)

row_c += 1
for _, r in type_stats.iterrows():
    ws_dash.write(row_c, 1, r['Төрөл'], fmt_bold_even)
    ws_dash.write(row_c, 2, int(r['Тоо']), fmt_int_even)
    ws_dash.write(row_c, 3, r['Эзлэх хувь'] / 100.0, fmt_tbl_pct)
    ws_dash.write(row_c, 4, r['Гэрээний нийт дүн'], fmt_curr_even)
    row_c += 1

# Table 3: Funding Sources
row_c += 2
ws_dash.write(row_c - 1, 1, '3. САНХҮҮЖИЛТИЙН ЭХ ҮҮСВЭРЭЭР (ТОП 8)', fmt_sec_hdr)
headers_f = ['Эх үүсвэр', 'Тендерийн тоо', 'Эзлэх хувь (%)', 'Гэрээний нийт дүн (₮)']
for col_idx, h in enumerate(headers_f):
    ws_dash.write(row_c, 1 + col_idx, h, fmt_tbl_hdr if col_idx == 0 else fmt_tbl_hdr_right)

row_c += 1
for _, r in funding_stats.iterrows():
    ws_dash.write(row_c, 1, r['Санхүүжилт'], fmt_text_even)
    ws_dash.write(row_c, 2, int(r['Тоо']), fmt_int_even)
    ws_dash.write(row_c, 3, r['Эзлэх хувь'] / 100.0, fmt_tbl_pct)
    ws_dash.write(row_c, 4, r['Гэрээний дүн'], fmt_curr_even)
    row_c += 1

# Set column widths for Dashboard
ws_dash.set_column('A:A', 3)
ws_dash.set_column('B:B', 32)
ws_dash.set_column('C:C', 18)
ws_dash.set_column('D:D', 24)
ws_dash.set_column('E:E', 24)
ws_dash.set_column('F:F', 22)
ws_dash.set_column('G:G', 16)
ws_dash.set_column('H:H', 20)
ws_dash.set_column('I:I', 20)

# ==========================================
# 2. SHEET: 📑 Бүрэн тайлан (64,194 Detailed Tenders)
# ==========================================
print("   Building Sheet 2: 📑 Бүрэн тайлан (64,194 records)...")
ws_full = wb.add_worksheet('📑 Бүрэн тайлан')
ws_full.set_tab_color('#0284C7')
ws_full.freeze_panes(2, 2)  # Freeze header rows & Tender Code + Name

# Row 1: Super Header Categories
ws_full.merge_range(0, 0, 0, 4, '1. ТЕНДЕРИЙН ҮНДСЭН МЭДЭЭЛЭЛ', fmt_super_navy)
ws_full.merge_range(0, 5, 0, 8, '2. ТӨСӨВ БА САНХҮҮЖИЛТ', fmt_super_emerald)
ws_full.merge_range(0, 9, 0, 12, '3. ХУГАЦАА, ОГНООНУУД', fmt_super_teal)
ws_full.merge_range(0, 13, 0, 17, '4. ОРОЛЦОГЧ ТАЛУУД (ЗАХИАЛАГЧ, ГҮЙЦЭТГЭГЧ)', fmt_super_indigo)
ws_full.merge_range(0, 18, 0, 21, '5. ШИЛЭН ДАНСНЫ ТУЛГАЛТ', fmt_super_violet)

# Row 2: Column Headers
header_formats = [
    # Group 1 (Navy)
    fmt_hdr_navy, fmt_hdr_navy, fmt_hdr_navy, fmt_hdr_navy, fmt_hdr_navy,
    # Group 2 (Emerald)
    fmt_hdr_emerald, fmt_hdr_emerald, fmt_hdr_emerald, fmt_hdr_emerald,
    # Group 3 (Teal)
    fmt_hdr_teal, fmt_hdr_teal, fmt_hdr_teal, fmt_hdr_teal,
    # Group 4 (Indigo)
    fmt_hdr_indigo, fmt_hdr_indigo, fmt_hdr_indigo, fmt_hdr_indigo, fmt_hdr_indigo,
    # Group 5 (Violet)
    fmt_hdr_violet, fmt_hdr_violet, fmt_hdr_violet, fmt_hdr_violet
]

for col_idx, (orig_col, display_col, col_type, col_width) in enumerate(COLUMNS_ORDER):
    ws_full.write(1, col_idx, display_col, header_formats[col_idx])
    ws_full.set_column(col_idx, col_idx, col_width)

ws_full.set_row(0, 24)
ws_full.set_row(1, 28)

# Write Data Rows efficiently
num_cols = len(COLUMNS_ORDER)
raw_matrix = []
for orig_col, _, _, _ in COLUMNS_ORDER:
    raw_matrix.append(df[orig_col].values)

print("   Streaming data rows into Sheet 2...")
for row_idx in range(len(df)):
    is_odd = (row_idx % 2 == 1)
    
    # Pick format set
    f_text = fmt_text_odd if is_odd else fmt_text_even
    f_bold = fmt_bold_odd if is_odd else fmt_bold_even
    f_center = fmt_center_odd if is_odd else fmt_center_even
    f_code = fmt_code_odd if is_odd else fmt_code_even
    f_curr = fmt_curr_odd if is_odd else fmt_curr_even
    f_int = fmt_int_odd if is_odd else fmt_int_even
    
    sheet_row = row_idx + 2
    
    for col_idx in range(num_cols):
        val = raw_matrix[col_idx][row_idx]
        col_type = COLUMNS_ORDER[col_idx][2]
        
        # Check null / nan
        if pd.isna(val) or val is None or str(val) == 'nan':
            ws_full.write_blank(sheet_row, col_idx, None, f_center)
            continue
            
        if col_type == 'currency':
            try:
                ws_full.write_number(sheet_row, col_idx, float(val), f_curr)
            except:
                ws_full.write_string(sheet_row, col_idx, str(val), f_text)
        elif col_type == 'integer':
            try:
                ws_full.write_number(sheet_row, col_idx, int(float(val)), f_int)
            except:
                ws_full.write_string(sheet_row, col_idx, str(val), f_center)
        elif col_type == 'code':
            ws_full.write_string(sheet_row, col_idx, str(val), f_code)
        elif col_type == 'bold_text':
            ws_full.write_string(sheet_row, col_idx, str(val), f_bold)
        elif col_type == 'center':
            ws_full.write_string(sheet_row, col_idx, str(val), f_center)
        elif col_type == 'badge_type':
            val_str = str(val).strip()
            if 'Бараа' in val_str:
                ws_full.write_string(sheet_row, col_idx, val_str, fmt_badge_baraa)
            elif 'Ажил' in val_str:
                ws_full.write_string(sheet_row, col_idx, val_str, fmt_badge_ajil)
            elif 'Үйлчилгээ' in val_str:
                ws_full.write_string(sheet_row, col_idx, val_str, fmt_badge_uilch)
            elif 'Зөвлөх' in val_str:
                ws_full.write_string(sheet_row, col_idx, val_str, fmt_badge_zuvluh)
            else:
                ws_full.write_string(sheet_row, col_idx, val_str, f_center)
        else:
            ws_full.write_string(sheet_row, col_idx, str(val), f_text)
            
    if row_idx > 0 and row_idx % 15000 == 0:
        print(f"      Processed {row_idx:,} / {len(df):,} rows...")

# Auto-filter on detailed table
ws_full.autofilter(1, 0, len(df) + 1, num_cols - 1)

# ==========================================
# 3. SHEET: 🏆 ТОП 100 Нийлүүлэгч (Top 100 Winners)
# ==========================================
print("   Building Sheet 3: 🏆 ТОП 100 Нийлүүлэгч...")
ws_top_win = wb.add_worksheet('🏆 ТОП 100 Нийлүүлэгч')
ws_top_win.set_tab_color('#2563EB')
ws_top_win.freeze_panes(2, 2)

# Title
ws_top_win.merge_range('B1:I1', 'МОНГОЛ УЛСЫН ТӨРИЙН ХУДАЛДАН АВАХ АЖИЛЛАГААНЫ ТОП 100 НИЙЛҮҮЛЭГЧ КОМПАНИ (2021-2025)', wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 13, 'font_color': '#FFFFFF', 'bg_color': '#1E40AF', 'valign': 'vcenter', 'align': 'center'}))
ws_top_win.set_row(0, 30)

top_win_headers = [
    ('№', 'integer', 6),
    ('Шалгарсан байгууллага', 'bold_text', 36),
    ('Регистрийн дугаар', 'center', 16),
    ('Тендерийн тоо', 'integer', 16),
    ('Гэрээний нийт дүн (₮)', 'currency', 24),
    ('Нийт төсөвт өртөг (₮)', 'currency', 24),
    ('Шилэн данс: Нийт авсан (₮)', 'currency', 24),
    ('Шилэн данс: Гүйлгээний тоо', 'integer', 18),
    ('Хамгийн том захиалагч байгууллага', 'text', 34)
]

for col_idx, (h_name, _, h_width) in enumerate(top_win_headers):
    ws_top_win.write(1, col_idx, h_name, fmt_hdr_indigo)
    ws_top_win.set_column(col_idx, col_idx, h_width)
ws_top_win.set_row(1, 26)

for r_idx, r in top_suppliers.iterrows():
    is_odd = (r_idx % 2 == 1)
    f_text = fmt_text_odd if is_odd else fmt_text_even
    f_bold = fmt_bold_odd if is_odd else fmt_bold_even
    f_center = fmt_center_odd if is_odd else fmt_center_even
    f_curr = fmt_curr_odd if is_odd else fmt_curr_even
    f_int = fmt_int_odd if is_odd else fmt_int_even
    
    sh_row = r_idx + 2
    ws_top_win.write_number(sh_row, 0, int(r['№']), f_center)
    ws_top_win.write_string(sh_row, 1, str(r['Шалгарсан байгууллага']), f_bold)
    ws_top_win.write_string(sh_row, 2, str(r['Регистрийн дугаар']), f_center)
    ws_top_win.write_number(sh_row, 3, int(r['tender_count']), f_int)
    ws_top_win.write_number(sh_row, 4, float(r['contract_sum']), f_curr)
    ws_top_win.write_number(sh_row, 5, float(r['budget_sum']), f_curr)
    
    if pd.notna(r['glass_sum']) and r['glass_sum'] > 0:
        ws_top_win.write_number(sh_row, 6, float(r['glass_sum']), f_curr)
    else:
        ws_top_win.write_string(sh_row, 6, '-', f_center)
        
    if pd.notna(r['glass_count']) and r['glass_count'] > 0:
        ws_top_win.write_number(sh_row, 7, int(r['glass_count']), f_int)
    else:
        ws_top_win.write_string(sh_row, 7, '-', f_center)
        
    ws_top_win.write_string(sh_row, 8, str(r['main_client']), f_text)

ws_top_win.autofilter(1, 0, len(top_suppliers) + 1, len(top_win_headers) - 1)

# ==========================================
# 4. SHEET: 🏛 ТОП 100 Захиалагч (Top 100 Buyers)
# ==========================================
print("   Building Sheet 4: 🏛 ТОП 100 Захиалагч...")
ws_top_buy = wb.add_worksheet('🏛 ТОП 100 Захиалагч')
ws_top_buy.set_tab_color('#0D9488')
ws_top_buy.freeze_panes(2, 2)

ws_top_buy.merge_range('B1:H1', 'МОНГОЛ УЛСЫН ХАМГИЙН ӨНДӨР ДҮНТЭЙ ТЕНДЕР ЗАРЛАСАН ТОП 100 ЗАХИАЛАГЧ БАЙГУУЛЛАГА (2021-2025)', wb.add_format({'bold': True, 'font_name': 'Segoe UI', 'font_size': 13, 'font_color': '#FFFFFF', 'bg_color': '#0F766E', 'valign': 'vcenter', 'align': 'center'}))
ws_top_buy.set_row(0, 30)

top_buy_headers = [
    ('№', 'integer', 6),
    ('Захиалагч байгууллага', 'bold_text', 38),
    ('Тендерийн тоо', 'integer', 16),
    ('Батлагдсан төсөв (₮)', 'currency', 24),
    ('Гэрээний нийт дүн (₮)', 'currency', 24),
    ('Төсвийн хэмнэлт (₮)', 'currency', 24),
    ('Хэмнэсэн %', 'pct', 16),
    ('Гол шалгарсан нийлүүлэгч', 'text', 34)
]

for col_idx, (h_name, _, h_width) in enumerate(top_buy_headers):
    ws_top_buy.write(1, col_idx, h_name, fmt_hdr_teal)
    ws_top_buy.set_column(col_idx, col_idx, h_width)
ws_top_buy.set_row(1, 26)

for r_idx, r in top_buyers.iterrows():
    is_odd = (r_idx % 2 == 1)
    f_text = fmt_text_odd if is_odd else fmt_text_even
    f_bold = fmt_bold_odd if is_odd else fmt_bold_even
    f_center = fmt_center_odd if is_odd else fmt_center_even
    f_curr = fmt_curr_odd if is_odd else fmt_curr_even
    f_int = fmt_int_odd if is_odd else fmt_int_even
    
    sh_row = r_idx + 2
    ws_top_buy.write_number(sh_row, 0, int(r['№']), f_center)
    ws_top_buy.write_string(sh_row, 1, str(r['Захиалагч']), f_bold)
    ws_top_buy.write_number(sh_row, 2, int(r['tender_count']), f_int)
    ws_top_buy.write_number(sh_row, 3, float(r['budget_sum']), f_curr)
    ws_top_buy.write_number(sh_row, 4, float(r['contract_sum']), f_curr)
    ws_top_buy.write_number(sh_row, 5, float(r['savings_sum']), f_curr)
    ws_top_buy.write_number(sh_row, 6, float(r['savings_pct']) / 100.0, fmt_tbl_pct)
    ws_top_buy.write_string(sh_row, 7, str(r['main_winner']), f_text)

ws_top_buy.autofilter(1, 0, len(top_buyers) + 1, len(top_buy_headers) - 1)

print("5. Closing workbook and saving file...")
wb.close()
print("   Workbook written successfully!")

# Replace destination file atomically
print(f"6. Moving styled output to {SRC_FILE}...")
os.replace(TEMP_OUTPUT, SRC_FILE)
print("SUCCESS! File styled and refreshed with executive aesthetics.")
