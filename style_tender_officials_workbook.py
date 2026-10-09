# -*- coding: utf-8 -*-
"""
Style and beautify the Government Officials Tender Conflict of Interest Workbook:
- Thematic header coloring by logical functional groups
- Clear visual alerts for Critical / Direct Conflict / High Risk
- Freeze panes on row 1 and key identity columns
- Thousand separators and currency formatting (₮, мян.₮)
- Professional Executive Dashboard sheet with KPI summary cards & shortlist
- Auto-filtering and auto-fit column widths
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import shutil
import os

SRC_FILE = "/Users/enkhbadraltsogbayar/Tender data/1_Дарга_нарын_тендерийн_нэгтгэл_ШИНЭЧИЛСЭН.xlsx"
BACKUP_FILE = "/Users/enkhbadraltsogbayar/Tender data/1_Дарга_нарын_тендерийн_нэгтгэл_ШИНЭЧИЛСЭН_backup.xlsx"

# 1. Backup original
shutil.copyfile(SRC_FILE, BACKUP_FILE)
print(f"Backed up original file to: {BACKUP_FILE}")

wb = openpyxl.load_workbook(SRC_FILE)

# Color Palettes (Modern, Executive, Harmonious)
COLORS = {
    # Headers
    'hdr_official': '1A365D',   # Deep Navy
    'hdr_company': '2B6CB0',    # Slate Blue
    'hdr_tender': '1B4D3E',     # Dark Teal / Emerald
    'hdr_owner': '312E81',      # Royal Indigo
    'hdr_conflict': '581845',   # Plum Burgundy
    'hdr_finance': '1E4D2B',    # Forest Olive
    'hdr_risk': '801414',       # Deep Crimson / Alert Red
    'hdr_timeline': '334155',   # Dark Slate / Charcoal
    
    # Risk Badges
    'crit_fill': 'FCE4E4',      # Soft light red
    'crit_text': '900C3F',      # Dark crimson
    'crit_border': 'E6B0AA',
    
    'direct_fill': 'FFEAD2',    # Soft warm orange
    'direct_text': 'B7410E',    # Dark orange-red
    'direct_border': 'EDBB99',
    
    'high_fill': 'FEF3C7',      # Soft warm yellow
    'high_text': '92400E',      # Dark amber
    'high_border': 'F9E79F',
    
    # General status
    'yes_fill': 'DCFCE7',       # Soft green
    'yes_text': '166534',
    'no_fill': 'F1F5F9',        # Subtle slate
    'no_text': '64748B',
    
    # Card Fills for Dashboard
    'card_bg_1': 'EFF6FF',      # Light blue
    'card_border_1': '93C5FD',
    'card_bg_2': 'F0FDF4',      # Light green
    'card_border_2': '86EFAC',
    'card_bg_3': 'FEF2F2',      # Light red
    'card_border_3': 'FCA5A5',
    'card_bg_4': 'FAF5FF',      # Light purple
    'card_border_4': 'D8B4FE',
    
    # Borders & Zebra
    'border_light': 'E2E8F0',
    'zebra_even': 'FFFFFF',
    'zebra_odd': 'F8FAFC',
}

# Border styles
thin_border = Border(
    left=Side(style='thin', color=COLORS['border_light']),
    right=Side(style='thin', color=COLORS['border_light']),
    top=Side(style='thin', color=COLORS['border_light']),
    bottom=Side(style='thin', color=COLORS['border_light'])
)
header_border = Border(
    left=Side(style='thin', color='FFFFFF'),
    right=Side(style='thin', color='FFFFFF'),
    top=Side(style='medium', color='CBD5E1'),
    bottom=Side(style='medium', color='0F172A')
)

font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
font_body = Font(name="Segoe UI", size=9.5, color="1E293B")
font_body_bold = Font(name="Segoe UI", size=9.5, bold=True, color="0F172A")
font_body_muted = Font(name="Segoe UI", size=9, color="64748B")

# Map of column index to header category color
HEADER_GROUPS = {
    # 1-4: Албан тушаалтан
    1: COLORS['hdr_official'],
    2: COLORS['hdr_official'],
    3: COLORS['hdr_official'],
    4: COLORS['hdr_official'],
    # 5-7: Компани
    5: COLORS['hdr_company'],
    6: COLORS['hdr_company'],
    7: COLORS['hdr_company'],
    # 8-9: Тендерийн нийт
    8: COLORS['hdr_tender'],
    9: COLORS['hdr_tender'],
    # 10-12: Эзэмшил
    10: COLORS['hdr_owner'],
    11: COLORS['hdr_owner'],
    12: COLORS['hdr_owner'],
    # 13-17: Шууд зөрчил & ХАСХОМ
    13: COLORS['hdr_conflict'],
    14: COLORS['hdr_conflict'],
    15: COLORS['hdr_conflict'],
    16: COLORS['hdr_conflict'],
    17: COLORS['hdr_conflict'],
    # 18-19: Санхүү / Орлого
    18: COLORS['hdr_finance'],
    19: COLORS['hdr_finance'],
    # 20-22: Эрсдэл ба зөрчлийн дүгнэлт
    20: COLORS['hdr_risk'],
    21: COLORS['hdr_risk'],
    22: COLORS['hdr_risk'],
    # 23-32: Хугацааны нарийвчилсан шинжилгээ
    23: COLORS['hdr_timeline'],
    24: COLORS['hdr_timeline'],
    25: COLORS['hdr_timeline'],
    26: COLORS['hdr_timeline'],
    27: COLORS['hdr_timeline'],
    28: COLORS['hdr_timeline'],
    29: COLORS['hdr_timeline'],
    30: COLORS['hdr_timeline'],
    31: COLORS['hdr_timeline'],
    32: COLORS['hdr_timeline'],
}

CLEAN_HEADERS = {
    1: "Албан тушаалтан",
    2: "Албан тушаал",
    3: "Ажилладаг байгууллага",
    4: "Мэдүүлгийн он",
    5: "Холбогдсон компани",
    6: "Компанийн регистр",
    7: "Компани дахь үүрэг",
    8: "Нийт тендерийн тоо",
    9: "Нийт гэрээний дүн (₮)",
    10: "Эцсийн өмчлөгчид (UBO)",
    11: "Хувьцаа эзэмшигчид",
    12: "Захирлууд",
    13: "Өөрийн байгууллагаас авсан эсэх",
    14: "Өөрийн байгууллагын тендерүүд",
    15: "ХАСХОМ-д мэдүүлсэн эсэх",
    16: "Мэдүүлсэн хувьцааны нэр",
    17: "Хөрөнгө орлогод мэдүүлсэн бүх хувьцаа",
    18: "Жилийн орлого (мян.₮)",
    19: "Хувьцааны үнэлгээ (мян.₮)",
    20: "Бодит зөрчил мөн эсэх",
    21: "Шалгалтын статус",
    22: "Эрсдэлийн ангилал",
    23: "ХОМ мэдүүлсэн жилүүд",
    24: "Тендер авсан жилүүд",
    25: "Дарга байх үед авсан тендерүүд",
    26: "Дарга биш үед авсан тендерүүд",
    27: "Дарга байх үеийн дүн (₮)",
    28: "Дарга биш үеийн дүн (₮)",
    29: "Хувьцаа өөрчлөлт",
    30: "Хугацааны үнэлгээ",
    31: "Сүүлийн мэдүүлэг он",
    32: "2025 онд ажиллаж буй эсэх"
}

ws_data = wb['Sheet1']
ws_data.title = "Нэгтгэсэн жагсаалт (210)"

print("Formatting main data sheet...")

# Format Header Row
ws_data.row_dimensions[1].height = 38
for c in range(1, ws_data.max_column + 1):
    cell = ws_data.cell(1, c)
    if c in CLEAN_HEADERS:
        cell.value = CLEAN_HEADERS[c]
    hdr_color = HEADER_GROUPS.get(c, '334155')
    cell.fill = PatternFill(start_color=hdr_color, end_color=hdr_color, fill_type="solid")
    cell.font = font_header
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = header_border

# Format Data Rows
for r in range(2, ws_data.max_row + 1):
    ws_data.row_dimensions[r].height = 24
    
    # Check risk level
    risk_val = str(ws_data.cell(r, 22).value or '')
    is_crit = 'КРИТИКАЛ' in risk_val
    is_direct = 'ШУУД ЗӨРЧИЛ' in risk_val
    is_high = 'ӨНДӨР ЭРСДЭЛ' in risk_val
    
    # Check own org tender
    own_org_cell = ws_data.cell(r, 13)
    is_own_org = (own_org_cell.value is True) or (str(own_org_cell.value).strip() in ['True', 'ТИЙМ', '1'])
    
    # Zebra base fill
    base_fill_color = COLORS['zebra_odd'] if r % 2 == 1 else COLORS['zebra_even']
    
    for c in range(1, ws_data.max_column + 1):
        cell = ws_data.cell(r, c)
        cell.border = thin_border
        val = cell.value
        
        # Default font & alignment
        cell.font = font_body
        cell.fill = PatternFill(start_color=base_fill_color, end_color=base_fill_color, fill_type="solid")
        cell.alignment = Alignment(vertical="center")
        
        # Column 1: Official Name (Bold)
        if c == 1:
            cell.font = font_body_bold
            
        # Column 4, 31: Year
        elif c in [4, 31]:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        # Column 6: Register
        elif c == 6:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.number_format = '@'
            
        # Column 8: Tender Count
        elif c == 8:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.number_format = '#,##0'
            cell.font = font_body_bold
            
        # Column 9, 27, 28: Monetary Amounts (₮)
        elif c in [9, 27, 28]:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0 "₮"'
            if c in [9, 27] and val and float(val or 0) > 0:
                cell.font = font_body_bold
                
        # Column 18, 19: Amounts in thousand ₮
        elif c in [18, 19]:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0 " мян.₮"'
            
        # Column 13: Өөрийн байгууллагаас авсан эсэх
        elif c == 13:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if is_own_org:
                cell.value = "🚨 ТИЙМ (Өөрийн байгууллага)"
                cell.fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9.5, bold=True, color="991B1B")
            else:
                cell.value = "Үгүй"
                cell.font = font_body_muted
                
        # Column 14: Өөрийн байгууллагын тендерүүд
        elif c == 14:
            if is_own_org and val:
                cell.fill = PatternFill(start_color="FFF1F2", end_color="FFF1F2", fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9, bold=True, color="9F1239")
                
        # Column 15, 20: Booleans
        elif c in [15, 20]:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if val is True or str(val).strip() == 'True':
                cell.value = "Тийм"
                cell.font = Font(name="Segoe UI", size=9.5, color="166534")
            elif val is False or str(val).strip() == 'False':
                cell.value = "Үгүй"
                cell.font = font_body_muted
                
        # Column 21: Шалгалтын статус
        elif c == 21:
            if is_crit:
                cell.font = Font(name="Segoe UI", size=9, bold=True, color=COLORS['crit_text'])
            elif is_direct:
                cell.font = Font(name="Segoe UI", size=9, bold=True, color=COLORS['direct_text'])
                
        # Column 22: Эрсдэлийн ангилал (HIGHLIGHT BADGES)
        elif c == 22:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if is_crit:
                cell.fill = PatternFill(start_color=COLORS['crit_fill'], end_color=COLORS['crit_fill'], fill_type="solid")
                cell.font = Font(name="Segoe UI", size=10, bold=True, color=COLORS['crit_text'])
                cell.border = Border(left=Side(style='thin', color='B91C1C'), right=Side(style='thin', color='B91C1C'),
                                     top=Side(style='thin', color='B91C1C'), bottom=Side(style='thin', color='B91C1C'))
            elif is_direct:
                cell.fill = PatternFill(start_color=COLORS['direct_fill'], end_color=COLORS['direct_fill'], fill_type="solid")
                cell.font = Font(name="Segoe UI", size=10, bold=True, color=COLORS['direct_text'])
                cell.border = Border(left=Side(style='thin', color='EA580C'), right=Side(style='thin', color='EA580C'),
                                     top=Side(style='thin', color='EA580C'), bottom=Side(style='thin', color='EA580C'))
            elif is_high:
                cell.fill = PatternFill(start_color=COLORS['high_fill'], end_color=COLORS['high_fill'], fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9.5, bold=True, color=COLORS['high_text'])
                cell.border = Border(left=Side(style='thin', color='D97706'), right=Side(style='thin', color='D97706'),
                                     top=Side(style='thin', color='D97706'), bottom=Side(style='thin', color='D97706'))
                                     
        # Column 30: Хугацааны үнэлгээ
        elif c == 30:
            val_str = str(val or '')
            if val_str.startswith('✅'):
                cell.fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9, bold=True, color="065F46")
            elif val_str.startswith('⚠️'):
                cell.fill = PatternFill(start_color="FFFBEB", end_color="FFFBEB", fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9, bold=False, color="92400E")
            elif val_str.startswith('❌'):
                cell.fill = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9, bold=False, color="1E40AF")
            elif val_str.startswith('ℹ️'):
                cell.fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
                cell.font = font_body_muted
                
        # Column 32: 2025 онд ажиллаж буй эсэх
        elif c == 32:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if str(val).strip() == 'ТИЙМ':
                cell.fill = PatternFill(start_color=COLORS['yes_fill'], end_color=COLORS['yes_fill'], fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9.5, bold=True, color=COLORS['yes_text'])
            else:
                cell.fill = PatternFill(start_color=COLORS['no_fill'], end_color=COLORS['no_fill'], fill_type="solid")
                cell.font = Font(name="Segoe UI", size=9.5, bold=False, color=COLORS['no_text'])

# Freeze Panes: Row 1 & Columns A-D (Official, Position, Org, Year)
ws_data.freeze_panes = 'E2'

# Auto Filter on all columns
ws_data.auto_filter.ref = f"A1:{get_column_letter(ws_data.max_column)}{ws_data.max_row}"

# Auto-fit Column Widths (with sensible limits)
for col in ws_data.columns:
    col_idx = col[0].column
    max_len = 0
    # check first 50 rows for speed
    for cell in col[:60]:
        val = str(cell.value or '')
        if '\n' in val:
            val = max(val.split('\n'), key=len)
        max_len = max(max_len, len(val))
    header_len = len(str(ws_data.cell(1, col_idx).value or ''))
    col_width = max(max_len + 3, header_len + 4)
    # Clamp column widths
    col_width = max(12, min(col_width, 50))
    # Special columns
    if col_idx in [1, 5]: col_width = max(col_width, 22)
    if col_idx in [2, 3]: col_width = max(col_width, 28)
    if col_idx in [9, 27, 28]: col_width = max(col_width, 22)
    if col_idx in [13, 22]: col_width = max(col_width, 26)
    if col_idx in [14, 25, 26, 29]: col_width = max(col_width, 42)
    if col_idx in [21, 30]: col_width = max(col_width, 36)
    
    ws_data.column_dimensions[get_column_letter(col_idx)].width = col_width

# -------------------------------------------------------------
# 2. CREATE EXECUTIVE DASHBOARD SHEET (📊 Хураангуй Дашборд)
# -------------------------------------------------------------
print("Building Executive Dashboard sheet...")

ws_dash = wb.create_sheet(title="📊 Хураангуй Дашборд", index=0)
ws_dash.views.sheetView[0].showGridLines = True

# Colors for Dashboard
navy_title = Font(name="Segoe UI", size=16, bold=True, color="1E3A8A")
sub_title = Font(name="Segoe UI", size=10, italic=True, color="475569")
kpi_num = Font(name="Segoe UI", size=20, bold=True, color="0F172A")
kpi_label = Font(name="Segoe UI", size=9.5, bold=True, color="475569")
kpi_sub = Font(name="Segoe UI", size=8.5, color="64748B")

# Title Block
ws_dash.row_dimensions[2].height = 28
ws_dash.row_dimensions[3].height = 18
ws_dash.cell(2, 2, "ТӨРИЙН АЛБАН ТУШААЛТНУУДЫН АШИГ СОНИРХЛЫН ЗӨРЧИЛ & ТЕНДЕРИЙН НЭГДСЭН ТАЙЛАН").font = navy_title
ws_dash.cell(3, 2, "Эх сурвалж: Авлигатай Тэмцэх Газар (ХАСХОМ) & Төрийн Худалдан Авалтын Цахим Систем (Tender.gov.mn) · 2026 он").font = sub_title

# Calculate KPIs
total_count = ws_data.max_row - 1
crit_count = sum(1 for r in range(2, ws_data.max_row + 1) if 'КРИТИКАЛ' in str(ws_data.cell(r, 22).value))
direct_count = sum(1 for r in range(2, ws_data.max_row + 1) if 'ШУУД ЗӨРЧИЛ' in str(ws_data.cell(r, 22).value))
high_count = sum(1 for r in range(2, ws_data.max_row + 1) if 'ӨНДӨР ЭРСДЭЛ' in str(ws_data.cell(r, 22).value))
own_org_count = crit_count + direct_count # 12
active_2025 = sum(1 for r in range(2, ws_data.max_row + 1) if str(ws_data.cell(r, 32).value).strip() == 'ТИЙМ')
total_amt = sum(float(ws_data.cell(r, 9).value or 0) for r in range(2, ws_data.max_row + 1))
during_boss_amt = sum(float(ws_data.cell(r, 27).value or 0) for r in range(2, ws_data.max_row + 1))

# Draw 4 KPI Cards (Rows 5 to 7)
ws_dash.row_dimensions[5].height = 20
ws_dash.row_dimensions[6].height = 32
ws_dash.row_dimensions[7].height = 18

cards = [
    {
        'col_start': 2, 'col_end': 3,
        'bg': COLORS['card_bg_1'], 'border': COLORS['card_border_1'],
        'label': "НИЙТ ХОЛБОГДСОН ДАРГА",
        'val': f"{total_count} АНХААРАХ ЭТГЭЭД",
        'sub': f"Үүнээс {active_2025} нь 2025 онд албан тушаалтай",
        'val_color': "1E40AF"
    },
    {
        'col_start': 4, 'col_end': 5,
        'bg': COLORS['card_bg_3'], 'border': COLORS['card_border_3'],
        'label': "ШУУД ЗӨРЧИЛТЭЙ (ӨӨРИЙН БАЙГУУЛЛАГА)",
        'val': f"{own_org_count} АЛБАН ТУШААЛТАН",
        'sub': f"3 Критикал + 9 Шууд зөрчилтэй",
        'val_color': "B91C1C"
    },
    {
        'col_start': 6, 'col_end': 7,
        'bg': COLORS['card_bg_2'], 'border': COLORS['card_border_2'],
        'label': "НИЙТ ГЭРЭЭНИЙ ДҮН",
        'val': f"{total_amt/1e9:,.1f} ТЭРБУМ ₮",
        'sub': f"Дарга байхдаа: {during_boss_amt/1e9:,.1f} тэрбум ₮",
        'val_color': "15803D"
    },
    {
        'col_start': 8, 'col_end': 9,
        'bg': COLORS['card_bg_4'], 'border': COLORS['card_border_4'],
        'label': "ХАСХОМ-Д ЗАРЛАСАН БАЙДАЛ",
        'val': f"201 ХҮН (95.7%)",
        'sub': f"Өөрийн мэдүүлэг дэх компани тендер авсан",
        'val_color': "6B21A8"
    }
]

for card in cards:
    cs = card['col_start']
    ce = card['col_end']
    b_color = card['border']
    bg_color = card['bg']
    
    # Merge cells
    ws_dash.merge_cells(start_row=5, start_column=cs, end_row=5, end_column=ce)
    ws_dash.merge_cells(start_row=6, start_column=cs, end_row=6, end_column=ce)
    ws_dash.merge_cells(start_row=7, start_column=cs, end_row=7, end_column=ce)
    
    c_lbl = ws_dash.cell(5, cs, card['label'])
    c_lbl.font = Font(name="Segoe UI", size=8.5, bold=True, color="475569")
    c_lbl.alignment = Alignment(horizontal="center", vertical="center")
    
    c_val = ws_dash.cell(6, cs, card['val'])
    c_val.font = Font(name="Segoe UI", size=14, bold=True, color=card['val_color'])
    c_val.alignment = Alignment(horizontal="center", vertical="center")
    
    c_sub = ws_dash.cell(7, cs, card['sub'])
    c_sub.font = Font(name="Segoe UI", size=8, color="64748B")
    c_sub.alignment = Alignment(horizontal="center", vertical="center")
    
    # Border & Fill for merged range
    c_side = Side(style='medium', color=b_color)
    for r in range(5, 8):
        for c in range(cs, ce + 1):
            cell = ws_dash.cell(r, c)
            cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
            # Apply border to outer edges
            top_s = c_side if r == 5 else None
            bot_s = c_side if r == 7 else None
            left_s = c_side if c == cs else None
            right_s = c_side if c == ce else None
            cell.border = Border(top=top_s, bottom=bot_s, left=left_s, right=right_s)

# SECTION 1: TOP 12 DIRECT CONFLICT CASES (TABLE)
ws_dash.cell(10, 2, "🚨 ХАМГИЙН НОЦТОЙ 12 АЛБАН ТУШААЛТАН (ӨӨРИЙН ДАРГАЛДАГ/АЖИЛЛАДАГ БАЙГУУЛЛАГААС ТЕНДЕР АВСАН)").font = Font(name="Segoe UI", size=11, bold=True, color="991B1B")

top_headers = ["№", "Албан тушаалтан", "Албан тушаал", "Ажилладаг байгууллага", "Холбогдсон компани", "Өөрийн байгууллагаас авсан тендер", "Нийт гэрээний дүн (₮)", "Эрсдэлийн ангилал"]
ws_dash.row_dimensions[11].height = 26

for idx, th in enumerate(top_headers, 2):
    cell = ws_dash.cell(11, idx, th)
    cell.fill = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")
    cell.font = Font(name="Segoe UI", size=9.5, bold=True, color="FFFFFF")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = Border(bottom=Side(style='medium', color='000000'))

# Collect the 12 direct conflict rows from main sheet
direct_rows = []
for r in range(2, ws_data.max_row + 1):
    risk = str(ws_data.cell(r, 22).value or '')
    if 'КРИТИКАЛ' in risk or 'ШУУД ЗӨРЧИЛ' in risk:
        direct_rows.append({
            'name': ws_data.cell(r, 1).value,
            'pos': ws_data.cell(r, 2).value,
            'org': ws_data.cell(r, 3).value,
            'comp': ws_data.cell(r, 5).value,
            'own_tenders': ws_data.cell(r, 14).value,
            'total_amt': float(ws_data.cell(r, 9).value or 0),
            'risk': risk
        })

# Sort: Critical first, then by total amount descending
direct_rows.sort(key=lambda x: (0 if 'КРИТИКАЛ' in x['risk'] else 1, -x['total_amt']))

curr_row = 12
for idx, d in enumerate(direct_rows, 1):
    ws_dash.row_dimensions[curr_row].height = 22
    is_crit = 'КРИТИКАЛ' in d['risk']
    row_fill = PatternFill(start_color="FFF1F2" if is_crit else "FFF7ED", end_color="FFF1F2" if is_crit else "FFF7ED", fill_type="solid")
    
    c1 = ws_dash.cell(curr_row, 2, idx)
    c1.alignment = Alignment(horizontal="center", vertical="center")
    
    c2 = ws_dash.cell(curr_row, 3, d['name'])
    c2.font = font_body_bold
    
    c3 = ws_dash.cell(curr_row, 4, d['pos'])
    c4 = ws_dash.cell(curr_row, 5, d['org'])
    c5 = ws_dash.cell(curr_row, 6, d['comp'])
    c5.font = font_body_bold
    
    c6 = ws_dash.cell(curr_row, 7, d['own_tenders'])
    c6.font = Font(name="Segoe UI", size=9, color="991B1B", bold=True)
    
    c7 = ws_dash.cell(curr_row, 8, d['total_amt'])
    c7.number_format = '#,##0 "₮"'
    c7.font = font_body_bold
    c7.alignment = Alignment(horizontal="right", vertical="center")
    
    c8 = ws_dash.cell(curr_row, 9, d['risk'])
    c8.alignment = Alignment(horizontal="center", vertical="center")
    c8.font = Font(name="Segoe UI", size=9, bold=True, color="991B1B" if is_crit else "C2410C")
    
    for c in range(2, 10):
        cell = ws_dash.cell(curr_row, c)
        cell.fill = row_fill
        cell.border = thin_border
        
    curr_row += 1

# SECTION 2: RISK BREAKDOWN TABLE
curr_row += 2
ws_dash.cell(curr_row, 2, "📈 ЭРСДЭЛИЙН АНГИЛЛЫН ХУВААРИЛАЛТ БОЛОН ТАЙЛБАР").font = Font(name="Segoe UI", size=11, bold=True, color="1E3A8A")

curr_row += 1
ws_dash.row_dimensions[curr_row].height = 24
stat_headers = ["Эрсдэлийн зэрэг", "Тоо хэмжээ", "Эзлэх хувь", "Нийт гэрээний дүн", "Тайлбар & Авч хэрэгжүүлэх арга хэмжээ"]
for idx, sh_title in enumerate(stat_headers, 2):
    cell = ws_dash.cell(curr_row, idx, sh_title)
    cell.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    cell.font = Font(name="Segoe UI", size=9.5, bold=True, color="FFFFFF")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = Border(bottom=Side(style='medium', color='000000'))

risk_breakdown = [
    ("🔴 КРИТИКАЛ (Tier 1 + 3)", crit_count, f"{crit_count/total_count*100:.1f}%", 
     sum(float(ws_data.cell(r, 9).value or 0) for r in range(2, ws_data.max_row + 1) if 'КРИТИКАЛ' in str(ws_data.cell(r, 22).value)),
     "Өөрийн ажилладаг газраас тендер авсан БӨГӨӨД ХАСХОМ-д өөрөө мэдүүлсэн (Хуулийн ноцтой зөрчил)", "FCE4E4", "900C3F"),
    ("🟠 ШУУД ЗӨРЧИЛ (Tier 1)", direct_count, f"{direct_count/total_count*100:.1f}%",
     sum(float(ws_data.cell(r, 9).value or 0) for r in range(2, ws_data.max_row + 1) if 'ШУУД ЗӨРЧИЛ' in str(ws_data.cell(r, 22).value)),
     "Өөрийн ажилладаг/даргалдаг байгууллагаас компани нь тендер авсан (Ашиг сонирхлын хуулийн шууд хориглолт)", "FFEAD2", "B7410E"),
    ("🟡 ӨНДӨР ЭРСДЭЛ (Tier 3)", high_count, f"{high_count/total_count*100:.1f}%",
     sum(float(ws_data.cell(r, 9).value or 0) for r in range(2, ws_data.max_row + 1) if 'ӨНДӨР ЭРСДЭЛ' in str(ws_data.cell(r, 22).value)),
     "АТГ-ын ХАСХОМ-д өөрөө зарласан хувьцаа эзэмшдэг компани нь улсын тендер авсан (Нөлөөллийн эрсдэл)", "FEF3C7", "92400E"),
]

for title_r, cnt_r, pct_r, amt_r, desc_r, bg_r, text_r in risk_breakdown:
    curr_row += 1
    ws_dash.row_dimensions[curr_row].height = 24
    
    c1 = ws_dash.cell(curr_row, 2, title_r)
    c1.font = Font(name="Segoe UI", size=9.5, bold=True, color=text_r)
    c1.fill = PatternFill(start_color=bg_r, end_color=bg_r, fill_type="solid")
    
    c2 = ws_dash.cell(curr_row, 3, cnt_r)
    c2.font = font_body_bold
    c2.alignment = Alignment(horizontal="center", vertical="center")
    
    c3 = ws_dash.cell(curr_row, 4, pct_r)
    c3.alignment = Alignment(horizontal="center", vertical="center")
    
    c4 = ws_dash.cell(curr_row, 5, amt_r)
    c4.number_format = '#,##0 "₮"'
    c4.font = font_body_bold
    c4.alignment = Alignment(horizontal="right", vertical="center")
    
    c5 = ws_dash.cell(curr_row, 6, desc_r)
    c5.font = font_body
    
    for c in range(2, 7):
        ws_dash.cell(curr_row, c).border = thin_border
        if c != 2:
            ws_dash.cell(curr_row, c).fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

# Set column widths for Dashboard
dash_col_widths = {
    1: 4,
    2: 6,
    3: 24,
    4: 28,
    5: 32,
    6: 45,
    7: 35,
    8: 24,
    9: 25
}
for c_idx, w in dash_col_widths.items():
    ws_dash.column_dimensions[get_column_letter(c_idx)].width = w

# 3. Save Styled Workbook
wb.save(SRC_FILE)
# Also copy to Downloads so user can access it immediately
shutil.copyfile(SRC_FILE, "/Users/enkhbadraltsogbayar/Downloads/1_Дарга_нарын_тендерийн_нэгтгэл_ШИНЭЧИЛСЭН.xlsx")

print("Finished successfully! Styled workbook saved to:")
print(f"  1. {SRC_FILE}")
print(f"  2. /Users/enkhbadraltsogbayar/Downloads/1_Дарга_нарын_тендерийн_нэгтгэл_ШИНЭЧИЛСЭН.xlsx")
