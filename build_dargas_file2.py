"""
build_dargas_file2.py
Reads xacxom_tender_conflicts_100_percent_verified.xlsx (210 cases)
Finds every tender they won from 2021-2025.
Outputs 2_Дарга_нарын_тендерийн_дэлгэрэнгүй.xlsx
"""

import pandas as pd
import glob
import os

print("1. Loading 210 cases...")
df1 = pd.read_excel('xacxom_tender_conflicts_100_percent_verified.xlsx')

# Identify the target companies
regs = set(df1['компанийн_регистр'].astype(str).str.strip())
print(f"Target companies: {len(regs)}")

print("2. Loading all tenders...")
tender_files = glob.glob('all_202*_winners_raw.csv')
all_tenders = []
for f in tender_files:
    df_t = pd.read_csv(f, dtype=str)
    all_tenders.append(df_t)
df_tenders = pd.concat(all_tenders, ignore_index=True)

print(f"Total tenders loaded: {len(df_tenders)}")

# We need a mapping from company name in the tender file to registry number.
# `tender_companies_ai_verified.json` has this mapping.
import json
with open('tender_companies_ai_verified.json', 'r', encoding='utf-8') as f:
    tc_data = json.load(f)

name_to_reg = {}
for tc in tc_data:
    reg = str(tc.get('регистрийн_дугаар')).strip()
    if reg in regs:
        name1 = tc.get('тендерийн_нэр')
        name2 = tc.get('бүртгэлийн_нэр')
        if name1: name_to_reg[str(name1).strip().lower()] = reg
        if name2: name_to_reg[str(name2).strip().lower()] = reg

# Now match tenders
detailed_rows = []
for _, r in df_tenders.iterrows():
    cname = str(r.get('company', '')).strip()
    if cname.lower() in name_to_reg:
        reg = name_to_reg[cname.lower()]
        
        # Find all officials related to this company in the 210 cases
        officials = df1[df1['компанийн_регистр'].astype(str).str.strip() == reg]
        
        for _, off in officials.iterrows():
            row = {
                'албан_тушаалтан': off['албан_тушаалтан'],
                'албан_тушаал': off['албан_тушаал'],
                'ажилладаг_байгууллага': off['ажилладаг_байгууллага'],
                'холбогдсон_компани': off['холбогдсон_компани'],
                'компанийн_регистр': reg,
                'компани_дахь_үүрэг': off['компани_дахь_үүрэг'],
                'мэдүүлсэн_хувьцааны_нэр': off.get('мэдүүлсэн_хувьцааны_нэр', ''),
                'тендерийн_он': str(r.get('date', ''))[:4],
                'тендерийн_огноо': r.get('date', ''),
                'захиалагч_байгууллага (Хаанаас зарласан)': r.get('client', ''),
                'тендерийн_код': r.get('tender_code', ''),
                'тендерийн_нэр (Ямар тендер шалгарсан)': r.get('tender_name', ''),
                'гэрээний_дүн_төгрөг': float(r.get('amount', 0)),
                'өөрийн_байгууллагын_тендер_эсэх': off['өөрийн_байгууллагаас_авсан_эсэх'],
                'эрсдэлийн_ангилал': off['эрсдэлийн_ангилал']
            }
            detailed_rows.append(row)

df_det = pd.DataFrame(detailed_rows)
df_det.to_excel('2_Дарга_нарын_тендерийн_дэлгэрэнгүй.xlsx', index=False)
print(f"Saved 2_Дарга_нарын_тендерийн_дэлгэрэнгүй.xlsx with {len(df_det)} rows.")
