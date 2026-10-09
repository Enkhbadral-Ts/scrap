import pandas as pd
import json
import re

years = [2021, 2022, 2023, 2024, 2025]
all_companies = set()

# Words to strip
suffixes = [
    r'\bХХК\b', r'\bХК\b', r'\bОНӨААТҮГ\b', r'\bТӨХК\b', r'\bТӨҮГ\b', r'\bББСБ\b',
    r'\bЗГҮГ\b', r'\bУТҮГ\b', r'\bНҮТББ\b', r'\bТББ\b', r'\bОНӨҮГ\b', r'\bХЗХ\b',
    r'\bААН\b', r'ХХК', r'ОНӨААТҮГ'
]

pattern = re.compile('|'.join(suffixes), flags=re.IGNORECASE)

def clean_name(name):
    if not isinstance(name, str):
        return ""
    name = name.replace('"', '').replace("'", '').replace("”", "").replace("“", "")
    name = pattern.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.rstrip(',.')
    return name.strip()

for y in years:
    try:
        df = pd.read_csv(f'all_{y}_winners_excel_zoriulalt.csv')
        companies = df['company'].dropna().unique()
        for c in companies:
            all_companies.add(c)
    except Exception as e:
        print(f"Error reading {y}: {e}")

print(f"Total raw unique companies: {len(all_companies)}")

cleaned_map = {}
for raw in all_companies:
    cleaned = clean_name(raw)
    if cleaned:
        cleaned_map[raw] = cleaned

print(f"Total cleaned companies mapped: {len(cleaned_map)}")

# Extract unique cleaned names
unique_cleaned = set(cleaned_map.values())
print(f"Unique search queries to run on Shilendans: {len(unique_cleaned)}")

with open('company_cleaning_map.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned_map, f, ensure_ascii=False, indent=4)
