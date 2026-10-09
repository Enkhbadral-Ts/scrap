import json
import re
import pandas as pd

def norm(s):
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»“”]', '', s)
    s = re.sub(r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН)\b', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

with open('tender_companies_ai_verified.json', 'r', encoding='utf-8') as f:
    tc_list = json.load(f)

df_raw = pd.read_excel('FINAL_Tender_Report_2021_2025_With_Details_RAW_BACKUP.xlsx')
raw_comps = sorted(list(set(df_raw['Шалгарсан байгууллага'].dropna().astype(str).str.strip())))

print(f"Total raw company names: {len(raw_comps)}")
print(f"Total tc_list entries: {len(tc_list)}")

# Exact matches first
tc_by_exact = {c.get('тендерийн_нэр', '').strip(): c for c in tc_list}
tc_by_norm = {}
for c in tc_list:
    nm = norm(c.get('тендерийн_нэр', ''))
    if nm not in tc_by_norm:
        tc_by_norm[nm] = c

# Specific known manual overrides for the remaining few
manual_map = {
    'China Railway Construction Bridge Engineering Bureau Group Co., Ltd.': 'China Railway Construction Bridge Engineering Bureau Group Co., Ltd',
    'Dohwa Engineering Co., Ltd.': 'Dohwa Engineering Co., Ltd',
    'INHEMETER CO.,LTD.': 'INHEMETER CO.,LTD',
    'SHARE FUTURE TECHNOLOGY (BEIJING) CO.,LTD.': 'SHARE FUTURE TECHNOLOGY (BEIJING) CO.,LTD',
    '同方威视技术股份有限公司 _x000D_NUCTECH COMPANY LIMITED': '同方威视技术股份有限公司 NUCTECH COMPANY LIMITED'
}

raw_to_tc = {}
unmatched = []

for r in raw_comps:
    if r in tc_by_exact:
        raw_to_tc[r] = tc_by_exact[r]
    elif r in manual_map and manual_map[r] in tc_by_exact:
        raw_to_tc[r] = tc_by_exact[manual_map[r]]
    else:
        nm = norm(r)
        if nm in tc_by_norm:
            raw_to_tc[r] = tc_by_norm[nm]
        else:
            unmatched.append(r)

print(f"Successfully matched: {len(raw_to_tc)} / {len(raw_comps)}")
print(f"Unmatched: {len(unmatched)}")
if unmatched:
    print("Unmatched items:", unmatched)

