# -*- coding: utf-8 -*-
"""
Test reading and preparing dataset for styling.
"""
import pandas as pd
import numpy as np

FILE_PATH = "/Users/enkhbadraltsogbayar/Tender data/FINAL_Tender_Report_2021_2025_With_Details.xlsx"
df = pd.read_excel(FILE_PATH)
print("Loaded successfully. Shape:", df.shape)

# Clean address
df['Хаяг'] = df['Хаяг'].fillna('').astype(str).replace({'$undefined': '', 'undefined': ''})

# Clean reg no
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

# Year
df['Гэрээний он'] = pd.to_datetime(df['Гэрээ байгуулсан огноо'], errors='coerce').dt.year
df['Гэрээний он'] = df['Гэрээний он'].fillna(0).astype(int)

# Diff
df['Төсвийн хэмнэлт'] = df['Нийт төсөвт өртөг'] - df['Гэрээний дүн']

print("Sample cleaned reg:", df['Регистрийн дугаар'].head(5).tolist())
print("Sample cleaned address:", df['Хаяг'].head(5).tolist())
