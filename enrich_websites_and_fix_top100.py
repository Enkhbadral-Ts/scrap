import pandas as pd
import json

# Load existing enriched data
df = pd.read_excel('Top_100_Companies_2025_Enriched.xlsx')

# Complete the 3 missing entities from LesOutputJson
# 14: Макс Групп -> Макс-Импэкс (2057573) / Толгой компани
# 43: М-Си-Эс Пропери (М-Си-Эс Проперти) -> 5040159
# 56: Бюлдинг Мэйнтэнэнс Сервисэс -> 5892694

with open('LesOutputJson.json', 'r', encoding='utf-8') as f:
    les_data = json.load(f)

les_map = {}
for row in les_data['Data']:
    les_map[str(row[0])] = row

# Helper to format
def parse_entity(row):
    sh_list = [f"{sh[2]} {sh[3]}".strip() for sh in row[5] if len(sh) >= 5]
    dir_list = [f"{dr[2]} {dr[3]}".strip() for dr in row[6] if len(dr) >= 5]
    ubo_list = [f"{ub[1]} {ub[2]}".strip() for ub in row[7] if len(ub) >= 3]
    return row[0], ', '.join(sh_list), ', '.join(dir_list), ', '.join(ubo_list)

# Update rank 14
r14 = les_map.get('2057573')
if r14:
    reg, sh, dr, ub = parse_entity(r14)
    df.loc[df['rank'] == 14, 'reg'] = reg
    df.loc[df['rank'] == 14, 'shareholders'] = sh
    df.loc[df['rank'] == 14, 'directors'] = dr
    df.loc[df['rank'] == 14, 'ubos'] = ub

# Update rank 43
r43 = les_map.get('5040159')
if r43:
    reg, sh, dr, ub = parse_entity(r43)
    df.loc[df['rank'] == 43, 'reg'] = reg
    df.loc[df['rank'] == 43, 'shareholders'] = sh
    df.loc[df['rank'] == 43, 'directors'] = dr
    df.loc[df['rank'] == 43, 'ubos'] = ub

# Update rank 56
r56 = les_map.get('5892694')
if r56:
    reg, sh, dr, ub = parse_entity(r56)
    df.loc[df['rank'] == 56, 'reg'] = reg
    df.loc[df['rank'] == 56, 'shareholders'] = sh
    df.loc[df['rank'] == 56, 'directors'] = dr
    df.loc[df['rank'] == 56, 'ubos'] = ub

# Ensure reg is formatted cleanly without trailing .0
def clean_reg(val):
    if pd.isna(val):
        return ""
    try:
        return str(int(float(val)))
    except Exception:
        return str(val)

df['reg'] = df['reg'].apply(clean_reg)

# Website mapping dictionary by rank
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

df['website'] = df['rank'].map(websites).fillna('-')

# Reorder columns
cols = ['rank', 'original_name', 'reg', 'website', 'shareholders', 'directors', 'ubos']
df = df[cols]

# Save to Excel
df.to_excel('Top_100_Companies_2025_Enriched.xlsx', index=False)
print("Saved enriched excel successfully with", len(df), "rows.")

# Save to Markdown
md_path = "/Users/enkhbadraltsogbayar/.gemini/antigravity-ide/brain/cc7ff82f-a265-4df2-ba59-943ccc23d9f2/top_100_2025_enriched.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# Монгол Улсын 2025 оны ТОП-100 Аж Ахуйн Нэгж (УБЕГ Бүртгэл, Эцсийн Өмчлөгч, Вэбсайттай)\n\n")
    f.write("| Эрэмбэ | Компанийн Нэр | Регистр | Албан ёсны вэбсайт | Хувьцаа эзэмшигч | Гүйцэтгэх захирал | Эцсийн өмчлөгч |\n")
    f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
    for _, row in df.iterrows():
        wb = row['website']
        if wb.startswith("http"):
            wb_cell = f"[{wb}]({wb})"
        else:
            wb_cell = wb
        f.write(f"| {row['rank']} | {row['original_name']} | {row['reg']} | {wb_cell} | {row['shareholders']} | {row['directors']} | {row['ubos']} |\n")

print("Saved markdown artifact successfully.")
