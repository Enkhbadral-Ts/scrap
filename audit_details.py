import pandas as pd
import numpy as np

file_path = 'FINAL_Tender_Report_2021_2025_With_Details.xlsx'
print("1. Loading both sheets into pandas...")
df_s1 = pd.read_excel(file_path, sheet_name=0, dtype={'Регистрийн дугаар': str})
df_s2 = pd.read_excel(file_path, sheet_name=1, header=1, dtype={'Регистрийн дугаар': str})

print(f"Sheet 1 shape: {df_s1.shape}")
print(f"Sheet 2 shape: {df_s2.shape}")

# Reconciliation check
print("\n2. Reconciling Sheet 1 company totals with Sheet 2 tender sum...")
s2_grouped = df_s2.groupby('Шалгарсан компани').agg(
    s2_cnt=('Тендерийн дугаар', 'count'),
    s2_amt=('Гэрээний үнэ / дүн (₮)', 'sum')
).reset_index()

merged = pd.merge(df_s1, s2_grouped, left_on='Компанийн нэр', right_on='Шалгарсан компани', how='outer')

cnt_mismatch = (merged['Шалгарсан нийт тендерийн тоо'] != merged['s2_cnt']).sum()
amt_diff = (merged['Гэрээний нийт дүн (₮)'].fillna(0) - merged['s2_amt'].fillna(0)).abs()
amt_mismatch = (amt_diff > 1.0).sum()

print(f"Total companies in Sheet 1: {len(df_s1):,}")
print(f"Companies matching between sheets: {len(merged):,}")
print(f"Company count mismatches: {cnt_mismatch}")
print(f"Company amount mismatches (> 1₮ difference): {amt_mismatch}")

# Internal consistency of Sheet 1: Year sums vs Total sum
y_counts = df_s1[['2021 он: Тоо', '2022 он: Тоо', '2023 он: Тоо', '2024 он: Тоо', '2025 он: Тоо']].sum(axis=1)
y_amounts = df_s1[['2021 он: Дүн (₮)', '2022 он: Дүн (₮)', '2023 он: Дүн (₮)', '2024 он: Дүн (₮)', '2025 он: Дүн (₮)']].sum(axis=1)

year_cnt_mismatch = (y_counts != df_s1['Шалгарсан нийт тендерийн тоо']).sum()
year_amt_mismatch = ((y_amounts - df_s1['Гэрээний нийт дүн (₮)']).abs() > 1.0).sum()
print(f"Sheet 1 internal yearly count sum mismatches: {year_cnt_mismatch}")
print(f"Sheet 1 internal yearly amount sum mismatches: {year_amt_mismatch}")

# Duration check
print("\n3. Tender Duration Analysis (Зарласнаас хаагдах хүртэлх хугацаа):")
dur = df_s2['⏱ Зарласнаас хаагдсан (хоног)'].dropna()
print(f"Valid duration rows: {len(dur):,} / {len(df_s2):,} ({len(dur)/len(df_s2)*100:.1f}%)")
print(f"Average duration: {dur.mean():.1f} хоног")
print(f"Median duration: {dur.median():.1f} хоног")
print(f"Min duration: {dur.min():.1f} хоног | Max duration: {dur.max():.1f} хоног")

under_5_days = (dur < 5.0).sum()
under_7_days = (dur < 7.0).sum()
print(f"Tenders closed in < 5 days (Сэжигтэй / богино хугацаатай): {under_5_days:,} ({under_5_days/len(dur)*100:.2f}%)")
print(f"Tenders closed in < 7 days: {under_7_days:,} ({under_7_days/len(dur)*100:.2f}%)")

# Savings & Discount check
print("\n4. Price & Discount Analysis:")
savings = df_s2['Төсвийн зөрүү / Хэмнэлт (₮)'].dropna()
discounts = df_s2['📉 Үнийн бууралт (%)'].dropna()
print(f"Total budget across all tenders: {df_s2['Нийт төсөвт өртөг (₮)'].sum():,.0f} ₮")
print(f"Total contract price across all: {df_s2['Гэрээний үнэ / дүн (₮)'].sum():,.0f} ₮")
total_savings = df_s2['Нийт төсөвт өртөг (₮)'].sum() - df_s2['Гэрээний үнэ / дүн (₮)'].sum()
print(f"Total government savings: {total_savings:,.0f} ₮")
zero_discount = (discounts == 0).sum()
print(f"Tenders won at EXACT 100% budget (0% discount): {zero_discount:,} ({zero_discount/len(discounts)*100:.1f}%)")
print(f"Average discount when discount > 0: {discounts[discounts > 0].mean()*100:.2f}% (note: decimal in excel)")

# Year breakdown in Sheet 2
print("\n5. Tenders Count and Amount by Year (Sheet 2):")
year_summary = df_s2.groupby('Тендерийн он').agg(
    тоо=('Тендерийн дугаар', 'count'),
    төсөв=('Нийт төсөвт өртөг (₮)', 'sum'),
    гэрээний_үнэ=('Гэрээний үнэ / дүн (₮)', 'sum'),
    хэмнэлт=('Төсвийн зөрүү / Хэмнэлт (₮)', 'sum')
)
print(year_summary)

# Legal Entity / UBO Coverage
print("\n6. Ownership & Legal Entity Coverage (LesOutputJson):")
has_ubo = df_s2['Эцсийн өмчлөгч (UBO)'].dropna().apply(lambda x: len(str(x).strip()) > 0 and str(x) != 'nan').sum()
has_ceo = df_s2['Гүйцэтгэх захирал'].dropna().apply(lambda x: len(str(x).strip()) > 0 and str(x) != 'nan').sum()
has_reg_date = df_s2['Компани байгуулагдсан огноо'].dropna().apply(lambda x: len(str(x).strip()) > 0 and str(x) != 'nan').sum()
print(f"Tenders with UBO identified: {has_ubo:,} / {len(df_s2):,} ({has_ubo/len(df_s2)*100:.1f}%)")
print(f"Tenders with CEO identified: {has_ceo:,} / {len(df_s2):,} ({has_ceo/len(df_s2)*100:.1f}%)")
print(f"Tenders with Company Reg Date: {has_reg_date:,} / {len(df_s2):,} ({has_reg_date/len(df_s2)*100:.1f}%)")

