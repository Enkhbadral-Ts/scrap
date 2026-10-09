import openpyxl
import pandas as pd
import sqlite3
import re

print("Testing data extraction...")
conn = sqlite3.connect('burtgel_les.db')
cur = conn.cursor()

f_new = 'нөлөөлөгч хувьсагч 300 эрхэм зорилго .xlsx'
xl = pd.ExcelFile(f_new)
df_300 = xl.parse('ТОП 300 ХХК', skiprows=3)
df_167 = xl.parse('ТОП 167 ХК', skiprows=3)

print(f"Top 300 rows: {len(df_300)}")
print(f"Top 167 rows: {len(df_167)}")

