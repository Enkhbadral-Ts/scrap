import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Load top 100 base data from top100-2025.csv to ensure clean source
df_raw = pd.read_csv("top100-2025.csv")
df_2025 = df_raw[~df_raw["2025"].isin(["_", "-"])]
df_2025["rank"] = pd.to_numeric(df_2025["2025"]).astype(int)
df_2025 = df_2025.sort_values(by="rank").reset_index(drop=True)

import json
import re

def clean_name(name):
    n = str(name).lower().strip()
    n = re.sub(r'\b(ххк|хк|төүг|групп|корпораци|компани|оо|хх)\b', '', n)
    n = re.sub(r'[^a-zа-яөү0-9]', '', n)
    return n

with open("LesOutputJson.json", "r", encoding="utf-8") as f:
    les_data = json.load(f)

les_map_by_reg = {}
les_map_by_clean_name = {}
for row in les_data["Data"]:
    reg = str(row[0])
    raw_name = str(row[1])
    c_name = clean_name(raw_name)
    les_map_by_reg[reg] = row
    if c_name not in les_map_by_clean_name:
        les_map_by_clean_name[c_name] = row

# Websites mapping by rank
websites = {
    1: "https://www.ot.mn",
    2: "https://www.mak.mn",
    3: "https://www.khanbank.com",
    4: "https://www.energyresources.mn",
    5: "https://www.golomtbank.com",
    6: "https://www.tdbm.mn",
    7: "https://www.premiumnexus.mn",
    8: "https://www.apu.mn",
    9: "https://www.petrovis.mn",
    10: "https://www.mobicom.mn",
    11: "https://gs25.mn",
    12: "https://www.xacbank.mn",
    13: "https://khanaltai.mn",
    14: "https://maxgroup.mn",
    15: "https://mcs.mn",
    16: "https://www.unitel.mn",
    17: "https://www.southgobi.com",
    18: "https://www.facebook.com/boldtumureruugol",
    19: "https://boroogold.mn",
    20: "https://www.mak.mn",
    21: "https://emartmall.mn",
    22: "https://www.shunkhlai.mn",
    23: "https://www.altanjoloo.mn",
    24: "https://www.gobi.mn",
    25: "https://www.barloworld.mn",
    26: "https://www.mak.mn",
    27: "https://www.sodmongol.mn",
    28: "https://redpathmining.com",
    29: "https://merp.ttjv.mn",
    30: "https://www.teso.mn",
    31: "https://www.transwest.mn",
    32: "https://normount.mn",
    33: "https://jur-ur.mn",
    34: "https://uss.mn",
    35: "https://moenco.mn",
    36: "https://kfc.mn",
    37: "http://xxkbid.com",
    38: "https://www.altangadas.mn",
    39: "https://msmgroup.mn",
    40: "https://pizzahut.mn",
    41: "https://www.univision.mn",
    42: "http://coalmining.mn",
    43: "https://www.mcsproperty.mn",
    44: "https://ulaanbaatar-airport.mn",
    45: "https://minii-delguur.mn",
    46: "https://www.capitronbank.mn",
    47: "https://www.greengroup.mn",
    48: "https://tsairt.mn",
    49: "https://suu.mn",
    50: "https://www.sbb.mn",
    51: "https://www.bodi-intl.com",
    52: "http://usukhzoos.mn",
    53: "https://tescard.mn",
    54: "https://bayalag-er.mn",
    55: "https://mcsi.mn",
    56: "https://www.mcsproperty.mn",
    57: "https://www.shunkhlai.mn",
    58: "https://www.apu.mn",
    59: "https://www.enka.com",
    60: "https://www.mak.mn",
    61: "https://intermed.mn",
    62: "https://talkh-chikher.mn",
    63: "http://www.buuruljuut.mn",
    64: "https://m-bank.mn",
    65: "https://nbik.mn",
    66: "http://totaldistribution.mn",
    67: "https://www.skytel.mn",
    68: "http://www.platinumland.mn",
    69: "https://www.petrovis.mn",
    70: "http://www.blastcompany.mn",
    71: "http://sharyngol.mn",
    72: "https://netcapital.mn",
    73: "-",
    74: "https://www.nomin.mn",
    75: "http://www.terraenergy.mn",
    76: "https://www.gmobile.mn",
    77: "https://www.apu.mn",
    78: "https://www.shunkhlai.mn",
    79: "https://www.facebook.com/people/Vertex-Mining-Partner/100064115160892/",
    80: "https://www.nomin.mn",
    81: "http://www.tavanbogdfinance.com",
    82: "http://maximus.mn",
    83: "-",
    84: "https://special.mn",
    85: "https://www.epiroc.com",
    86: "https://www.tavanbogd-automotive.com",
    87: "https://pc-mall.mn",
    88: "http://achit-ikht.mn",
    89: "https://voltam.mn",
    90: "https://nura.mn",
    91: "https://transbank.mn",
    92: "https://mmse.mn",
    93: "https://monos.mn",
    94: "https://www.nomin.mn",
    95: "https://www.majordrilling.com",
    96: "https://monpolymet.mn",
    97: "https://www.dashvaanjil.mn",
    98: "-",
    99: "https://invescore.mn",
    100: "https://khanbogd.mn"
}

# Manual overrides for special entities
special_regs = {
    14: '2057573', # Макс Групп (Макс-Импэкс)
    43: '5040159', # М-Си-Эс Проперти
    56: '5892694', # Бьюлдингмэйнтэнэнс сервисэс
}

rows_out = []
for _, row in df_2025.iterrows():
    rk = int(row["rank"])
    raw_name = str(row["Name"])
    c_name = clean_name(raw_name)
    
    les_row = None
    if rk in special_regs:
        les_row = les_map_by_reg.get(special_regs[rk])
    elif c_name in les_map_by_clean_name:
        les_row = les_map_by_clean_name[c_name]
    else:
        # Partial match
        for r_c, l_r in les_map_by_clean_name.items():
            if len(c_name) > 4 and (c_name in r_c or r_c in c_name):
                les_row = l_r
                break
                
    reg = ""
    sh_str = ""
    dir_str = ""
    ubo_str = ""
    
    if les_row:
        reg = str(les_row[0])
        sh_list = [f"{sh[2]} {sh[3]}".strip() for sh in les_row[5] if len(sh) >= 5]
        dir_list = [f"{dr[2]} {dr[3]}".strip() for dr in les_row[6] if len(dr) >= 5]
        ubo_list = [f"{ub[1]} {ub[2]}".strip() for ub in les_row[7] if len(ub) >= 3]
        sh_str = ', '.join(sh_list)
        dir_str = ', '.join(dir_list)
        ubo_str = ', '.join(ubo_list)
        
    if rk == 71 and not ubo_str:
        ubo_str = "Олон нийтийн / MSE: SHG"
        
    wb = websites.get(rk, "-")
    
    rows_out.append({
        'Эрэмбэ': rk,
        'Компанийн нэр': raw_name,
        'Регистрийн дугаар': reg,
        'Албан ёсны вэбсайт': wb,
        'Хувьцаа эзэмшигч': sh_str,
        'Гүйцэтгэх захирал': dir_str,
        'Эцсийн өмчлөгч': ubo_str
    })

df_final = pd.DataFrame(rows_out)
print("Final rows count:", len(df_final))
print("Websites present:", (df_final['Албан ёсны вэбсайт'] != '-').sum())

# Export function with beautiful openpyxl formatting
def save_styled_excel(df_data, file_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ТОП 100 ААН 2025"
    
    # Headers
    headers = list(df_data.columns)
    ws.append(headers)
    
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )
    
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 28
    
    regular_font = Font(name="Arial", size=10)
    link_font = Font(name="Arial", size=10, color="0563C1", underline="single")
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    
    for row_idx, r_data in df_data.iterrows():
        r_num = row_idx + 2
        ws.row_dimensions[r_num].height = 20
        row_vals = [
            r_data['Эрэмбэ'],
            r_data['Компанийн нэр'],
            r_data['Регистрийн дугаар'],
            r_data['Албан ёсны вэбсайт'],
            r_data['Хувьцаа эзэмшигч'],
            r_data['Гүйцэтгэх захирал'],
            r_data['Эцсийн өмчлөгч']
        ]
        ws.append(row_vals)
        
        is_even = (row_idx % 2 == 1)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_num, column=col_idx)
            cell.font = regular_font
            cell.border = thin_border
            if is_even:
                cell.fill = zebra_fill
            
            # Alignments
            if col_idx == 1: # Эрэмбэ
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 3: # Регистр
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 4: # Вэбсайт
                cell.alignment = Alignment(horizontal="left", vertical="center")
                wb_url = str(r_data['Албан ёсны вэбсайт'])
                if wb_url.startswith("http"):
                    cell.hyperlink = wb_url
                    cell.font = link_font
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
                
    # Auto-adjust column widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        if col_letter == 'A':
            ws.column_dimensions[col_letter].width = 10
        elif col_letter == 'B':
            ws.column_dimensions[col_letter].width = 32
        elif col_letter == 'C':
            ws.column_dimensions[col_letter].width = 16
        elif col_letter == 'D':
            ws.column_dimensions[col_letter].width = 35
        elif col_letter == 'E':
            ws.column_dimensions[col_letter].width = 45
        elif col_letter == 'F':
            ws.column_dimensions[col_letter].width = 28
        elif col_letter == 'G':
            ws.column_dimensions[col_letter].width = 35

    ws.freeze_panes = "A2"
    wb.save(file_path)
    print(f"Saved: {file_path}")

# Save both filenames
save_styled_excel(df_final, '1_Монгол_Улсын_ТОП_100_ААН_2025_Бүрэн_мэдээлэл.xlsx')
save_styled_excel(df_final, 'Top_100_Companies_2025_Enriched.xlsx')

# Update Markdown
md_path = "/Users/enkhbadraltsogbayar/.gemini/antigravity-ide/brain/cc7ff82f-a265-4df2-ba59-943ccc23d9f2/top_100_2025_enriched.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# Монгол Улсын 2025 оны ТОП-100 Аж Ахуйн Нэгж (УБЕГ Бүртгэл, Эцсийн Өмчлөгч, Вэбсайттай)\n\n")
    f.write("| Эрэмбэ | Компанийн Нэр | Регистр | Албан ёсны вэбсайт | Хувьцаа эзэмшигч | Гүйцэтгэх захирал | Эцсийн өмчлөгч |\n")
    f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
    for _, row in df_final.iterrows():
        wb = row['Албан ёсны вэбсайт']
        if wb.startswith("http"):
            wb_cell = f"[{wb}]({wb})"
        else:
            wb_cell = wb
        f.write(f"| {row['Эрэмбэ']} | {row['Компанийн нэр']} | {row['Регистрийн дугаар']} | {wb_cell} | {row['Хувьцаа эзэмшигч']} | {row['Гүйцэтгэх захирал']} | {row['Эцсийн өмчлөгч']} |\n")

print("Updated Markdown successfully.")
