import pandas as pd
import json
import re

print("Loading Top 100 companies...")
df = pd.read_csv("top100-2025.csv")
df_2025 = df[~df["2025"].isin(["_", "-"])]
df_2025["2025"] = pd.to_numeric(df_2025["2025"])
df_2025 = df_2025.sort_values(by="2025")

def clean_name(name):
    # Remove common suffixes and whitespace
    n = str(name).lower().strip()
    n = re.sub(r'\b(ххк|хк|төүг|групп|корпораци|компани|оо|хх)\b', '', n)
    # Remove special characters
    n = re.sub(r'[^a-zа-яөү0-9]', '', n)
    return n

top_100 = {}
for _, row in df_2025.iterrows():
    raw_name = row["Name"]
    c_name = clean_name(raw_name)
    top_100[c_name] = {
        'rank': int(row["2025"]),
        'original_name': raw_name,
        'reg': '',
        'shareholders': '',
        'directors': '',
        'ubos': ''
    }

# Handle edge cases for names that might not match directly
# e.g., М-Си-эс групп -> мсиэс

print("Loading LesOutputJson.json (435MB)...")
with open("LesOutputJson.json", "r", encoding="utf-8") as f:
    les_data = json.load(f)

print("Matching...")
for row in les_data["Data"]:
    reg = row[0]
    raw_name = row[1]
    c_name = clean_name(raw_name)
    
    if c_name in top_100:
        # Extract shareholders
        sh_list = []
        for sh in row[5]:
            if len(sh) >= 5:
                # "Эцэг/эх/-ийн нэр", "Нэр"
                name = f"{sh[2]} {sh[3]}".strip()
                sh_list.append(name)
        
        dir_list = []
        for dr in row[6]:
            if len(dr) >= 5:
                name = f"{dr[2]} {dr[3]}".strip()
                dir_list.append(name)
                
        ubo_list = []
        for ub in row[7]:
            if len(ub) >= 3:
                name = f"{ub[1]} {ub[2]}".strip()
                ubo_list.append(name)
                
        top_100[c_name]['reg'] = reg
        top_100[c_name]['shareholders'] = ', '.join(sh_list)
        top_100[c_name]['directors'] = ', '.join(dir_list)
        top_100[c_name]['ubos'] = ', '.join(ubo_list)

# Now what if some are missing?
# Let's try to match those who are still empty by partial match
for c_name, v in top_100.items():
    if not v['reg']:
        for row in les_data["Data"]:
            r_c_name = clean_name(row[1])
            if r_c_name and (c_name in r_c_name or r_c_name in c_name):
                # We found a partial match
                # Check if it's a good match
                if len(c_name) > 4 and len(r_c_name) > 4:
                    reg = row[0]
                    # Extract same as above
                    sh_list = []
                    for sh in row[5]:
                        if len(sh) >= 5:
                            name = f"{sh[2]} {sh[3]}".strip()
                            sh_list.append(name)
                    dir_list = []
                    for dr in row[6]:
                        if len(dr) >= 5:
                            name = f"{dr[2]} {dr[3]}".strip()
                            dir_list.append(name)
                    ubo_list = []
                    for ub in row[7]:
                        if len(ub) >= 3:
                            name = f"{ub[1]} {ub[2]}".strip()
                            ubo_list.append(name)
                    v['reg'] = reg
                    v['shareholders'] = ', '.join(sh_list)
                    v['directors'] = ', '.join(dir_list)
                    v['ubos'] = ', '.join(ubo_list)
                    break

# Prepare output
out_rows = []
for c_name, v in top_100.items():
    out_rows.append(v)
    
df_out = pd.DataFrame(out_rows)
df_out = df_out.sort_values(by='rank')
df_out.to_excel('Top_100_Companies_2025_Enriched.xlsx', index=False)
print("Saved to Top_100_Companies_2025_Enriched.xlsx")

with open("/Users/enkhbadraltsogbayar/.gemini/antigravity-ide/brain/cc7ff82f-a265-4df2-ba59-943ccc23d9f2/top_100_2025_enriched.md", "w", encoding="utf-8") as f:
    f.write("# Монгол Улсын 2025 оны ТОП-100 Аж Ахуйн Нэгж (УБЕГ Мэдээлэлтэй)\n\n")
    f.write("| Эрэмбэ | Компанийн Нэр | Регистр | Хувьцаа эзэмшигч | Гүйцэтгэх захирал | Эцсийн өмчлөгч |\n")
    f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
    for _, row in df_out.iterrows():
        f.write(f"| {row['rank']} | {row['original_name']} | {row['reg']} | {row['shareholders']} | {row['directors']} | {row['ubos']} |\n")
print("Saved to markdown artifact.")
