import re
import urllib.request
import json
import sqlite3
import pandas as pd
import numpy as np

# Load source workbook
f_src = '/Users/enkhbadraltsogbayar/Downloads/нөлөөлөгч хувьсагч 300 эрхэм зорилго .xlsx'
xl = pd.ExcelFile(f_src)
df_300 = xl.parse('ТОП 300 ХХК', skiprows=3)
df_167 = xl.parse('ТОП 167 ХК', skiprows=3)

print("Top 300 count:", len(df_300))
print("Top 167 count:", len(df_167))

# Connect to burtgel_les.db
conn = sqlite3.connect('/Users/enkhbadraltsogbayar/Tender data/burtgel_les.db')
cur = conn.cursor()

# Inspect how many have reg_date
dates_found = 0
for idx, r in df_300.iterrows():
    reg = str(r.get('Регистрийн дугаар', '')).replace('.0', '').strip()
    cur.execute('SELECT reg_date FROM companies WHERE reg_no = ?', (reg,))
    row = cur.fetchone()
    if row and row[0]:
        dates_found += 1

print(f"Foundation dates found in burtgel_les: {dates_found} / {len(df_300)}")

