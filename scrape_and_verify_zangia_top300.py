# -*- coding: utf-8 -*-
"""
High-Precision Zangia.mn Employee Scraper & Verifier for TOP 300 XXK
Cross-referenced with burtgel_les.db and official company profiles.
"""

import os
import re
import json
import sqlite3
import urllib.request
import urllib.parse
from urllib.parse import urlparse
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = "/Users/enkhbadraltsogbayar/Tender data"
SRC_EXCEL = os.path.join(DATA_DIR, "1_Монгол_Улсын_ТОП_300_ААН_Бүрэн_мэдээлэл.xlsx")
DB_PATH = os.path.join(DATA_DIR, "burtgel_les.db")
OUT_EXCEL = os.path.join(DATA_DIR, "ТОП_300_ААН_Zangia_Ажилтны_тоо_Баталгаажсан.xlsx")
OUT_JSON = os.path.join(DATA_DIR, "zangia_top300_verified_staffs.json")

# Connect DB & Preload in memory
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute('SELECT reg_no, name, reg_date, address FROM companies')
db_cache = {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}
conn.close()
print(f"Preloaded {len(db_cache)} companies from burtgel_les.db")

# Load Top 300
df_src = pd.read_excel(SRC_EXCEL, sheet_name="ТОП 300 ХХК", header=3)
print(f"Loaded {len(df_src)} companies from {SRC_EXCEL}")

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_for_search(text):
    if not text or pd.isna(text): return ""
    s = str(text).lower()
    s = re.sub(r'[\"\'\`\«\»\(\)\,\.]', ' ', s)
    s = re.sub(r'\b(ххк|хк|төхк|төүг|групп|group|llc|jsc|холдинг|holding|компани|company)\b', ' ', s)
    return ' '.join(s.split())

def normalize_strict(text):
    if not text or pd.isna(text): return ""
    s = clean_for_search(text)
    return re.sub(r'[\s\-_\/]', '', s)

def get_domain(url):
    if not url or pd.isna(url): return ""
    url = str(url).strip().lower()
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    try:
        netloc = urlparse(url).netloc
        netloc = re.sub(r'^www\.', '', netloc)
        return netloc
    except:
        return ""

def search_zangia_list(query):
    if not query or len(query.strip()) < 2: return []
    url = f"https://new-api.zangia.mn/api/company/list?query={urllib.parse.quote(query.strip())}&page=1"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as res:
            data = json.loads(res.read().decode('utf-8'))
            return data.get('items', [])
    except Exception as e:
        return []

def get_zangia_detail(alias):
    if not alias: return {}
    url = f"https://new-api.zangia.mn/api/company/detail?identifier={urllib.parse.quote(alias)}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as res:
            data = json.loads(res.read().decode('utf-8'))
            return data.get('data', {})
    except Exception as e:
        return {}

# Cache for details to prevent duplicate network calls
detail_cache = {}

def get_cached_detail(alias):
    if alias not in detail_cache:
        detail_cache[alias] = get_zangia_detail(alias)
    return detail_cache[alias]

def process_company(row_tuple):
    idx, row = row_tuple
    rank = row['Эрэмбэ']
    c_name = str(row['Компанийн нэр']).strip()
    reg_no = str(row['Регистрийн дугаар']).strip()
    ub_name = str(row['Улсын бүртгэлийн нэр']).strip() if pd.notna(row['Улсын бүртгэлийн нэр']) else ""
    target_web = get_domain(row['Албан ёсны вэбсайт'])
    target_ceo = str(row['Гүйцэтгэх захирал']).strip().lower() if pd.notna(row['Гүйцэтгэх захирал']) else ""
    
    # DB lookup
    db_res = db_cache.get(reg_no)
    db_name = db_res[0] if db_res else ""
    db_fdate = db_res[1][:4] if db_res and db_res[1] else ""
    db_addr = db_res[2].lower() if db_res and db_res[2] else ""
    
    clean_target = clean_for_search(c_name)
    target_words = [w for w in clean_target.split() if len(w) > 1]
    norm_target = normalize_strict(c_name)
    norm_ub = normalize_strict(ub_name)
    
    # Build search queries
    queries = []
    if clean_target:
        queries.append(clean_target)
    if ub_name and ub_name != c_name:
        clean_ub = clean_for_search(ub_name)
        if clean_ub and clean_ub not in queries:
            queries.append(clean_ub)
            
    # Add domain brand query
    if target_web:
        domain_core = target_web.split('.')[0]
        if len(domain_core) >= 3 and domain_core not in ['com', 'org', 'gov', 'edu', 'net', 'mail']:
            queries.append(domain_core)
            
    # Add first two significant words if target has 3+ words
    if len(target_words) >= 3:
        queries.append(' '.join(target_words[:2]))
        
    # Search all queries
    candidate_map = {}
    for q in queries:
        items = search_zangia_list(q)
        for it in items:
            alias = it.get('alias')
            if alias and alias not in candidate_map:
                candidate_map[alias] = it
                
    best_candidate = None
    highest_score = -100
    
    for alias, it in candidate_map.items():
        dt = get_cached_detail(alias)
        z_name = dt.get('name', '')
        clean_z = clean_for_search(z_name)
        norm_z = normalize_strict(z_name)
        z_words = [w for w in clean_z.split() if len(w) > 1]
        z_web = get_domain(dt.get('website'))
        z_staff = dt.get('staffs_cnt')
        z_fyear = str(dt.get('founded_year', '')).strip()
        z_addr = str(dt.get('address', '')).lower()
        z_about = str(dt.get('about', '')).lower()
        
        score = 0
        reasons = []
        
        # 1. Domain match (Highest confidence: +70)
        if target_web and z_web:
            if target_web == z_web or target_web.endswith('.' + z_web) or z_web.endswith('.' + target_web):
                score += 70
                reasons.append("Вэбсайт_домэйн_тохирсон")
            elif target_web.split('.')[0] == z_web.split('.')[0]:
                score += 50
                reasons.append("Вэбсайт_үндсэн_нэр_тохирсон")
                
        # 2. Strict normalized name match (+60)
        if norm_z and (norm_z == norm_target or norm_z == norm_ub):
            score += 60
            reasons.append("Нэр_яг_тохирсон")
        elif norm_z and (norm_z in norm_target or norm_target in norm_z):
            score += 45
            reasons.append("Нэр_бүрэн_агуулагдсан")
            
        # 3. Word-level matching
        t_set = set(target_words)
        z_set = set(z_words)
        if t_set and z_set:
            overlap = t_set.intersection(z_set)
            if overlap == t_set:
                score += 40
                reasons.append("Бүх_үг_тохирсон")
            elif len(overlap) >= 2 and len(overlap) >= len(t_set) - 1:
                score += 25
                reasons.append("Голлох_үгс_тохирсон")
            elif len(overlap) == 1 and len(t_set) == 1:
                score += 30
                reasons.append("Нэг_үгт_нэр_тохирсон")
            else:
                # Intruder words penalty
                intruders = z_set - t_set
                if intruders and not (target_web and z_web and target_web == z_web):
                    score -= 30
                    
        # 4. Founded year match (+15)
        if db_fdate and z_fyear and db_fdate == z_fyear:
            score += 15
            reasons.append("Байгуулагдсан_он_тохирсон")
            
        # 5. Address/District match (+10)
        if db_addr and z_addr:
            districts = ['сүхбаатар', 'баянгөл', 'баянзүрх', 'хан-уул', 'сонгинохайрхан', 'чихэлтэй', 'дархан', 'эрдэнэт']
            for d in districts:
                if d in db_addr and d in z_addr:
                    score += 10
                    reasons.append("Дүүрэг_байршил_тохирсон")
                    break
                    
        # 6. CEO name match in about (+20)
        if target_ceo and len(target_ceo) > 3 and target_ceo in z_about:
            score += 20
            reasons.append("Захирлын_нэр_тохирсон")
            
        # Acceptance Threshold: Must have at least 45 points to be accepted!
        if score > highest_score:
            highest_score = score
            if score >= 45:
                best_candidate = {
                    'alias': alias,
                    'name': z_name,
                    'staffs_cnt': z_staff if z_staff is not None else 0,
                    'founded_year': z_fyear,
                    'website': dt.get('website'),
                    'address': dt.get('address'),
                    'phone': dt.get('phone'),
                    'score': score,
                    'reasons': reasons
                }
                
    result = {
        'rank': rank,
        'comp_name': c_name,
        'reg_no': reg_no,
        'ub_name': ub_name,
        'official_web': row['Албан ёсны вэбсайт'],
        'zangia_matched': bool(best_candidate),
        'zangia_name': best_candidate['name'] if best_candidate else None,
        'zangia_alias': best_candidate['alias'] if best_candidate else None,
        'staffs_cnt': best_candidate['staffs_cnt'] if best_candidate else None,
        'zangia_founded_year': best_candidate['founded_year'] if best_candidate else None,
        'zangia_web': best_candidate['website'] if best_candidate else None,
        'match_score': best_candidate['score'] if best_candidate else None,
        'match_reasons': ', '.join(best_candidate['reasons']) if best_candidate else "Олдоогүй / Баталгаажаагүй"
    }
    return result

print("Starting verified scrape across all 300 companies...")
all_results = []
rows_list = list(df_src.iterrows())

# Run with thread pool of 5 workers
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(process_company, item) for item in rows_list]
    done_count = 0
    for fut in as_completed(futures):
        res = fut.result()
        all_results.append(res)
        done_count += 1
        if done_count % 25 == 0 or done_count == len(rows_list):
            matched_so_far = sum(1 for r in all_results if r['zangia_matched'])
            print(f"Progress: {done_count}/300 companies processed | Verified matched: {matched_so_far}")

# Sort by rank
all_results.sort(key=lambda x: x['rank'])

# Save to JSON
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print(f"Saved verified JSON cache to {OUT_JSON}")

# Convert to DataFrame and style Excel
df_out = pd.DataFrame(all_results)
df_out.columns = [
    'Эрэмбэ', 'Компанийн нэр', 'Регистрийн дугаар', 'Улсын бүртгэлийн нэр',
    'Албан ёсны вэбсайт', 'Zangia-д олдсон эсэх', 'Zangia-ийн нэр',
    'Zangia Alias', 'Ажилтны тоо (staffs_cnt)', 'Zangia байгуулагдсан он',
    'Zangia вэбсайт', 'Тохирлын оноо', 'Баталгаажсан шалгуур'
]

# Write to Excel with formatting
with pd.ExcelWriter(OUT_EXCEL, engine='xlsxwriter') as writer:
    df_out.to_excel(writer, sheet_name='ТОП 300 Ажилтны тоо', index=False)
    workbook = writer.book
    worksheet = writer.sheets['ТОП 300 Ажилтны тоо']
    
    header_fmt = workbook.add_format({
        'bold': True,
        'bg_color': '#1B365D',
        'font_color': '#FFFFFF',
        'font_name': 'Segoe UI',
        'font_size': 11,
        'align': 'center',
        'valign': 'vcenter',
        'border': 1
    })
    
    cell_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'valign': 'vcenter'
    })
    
    num_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'align': 'right',
        'num_format': '#,##0'
    })
    
    center_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'align': 'center'
    })
    
    matched_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'align': 'center',
        'bg_color': '#D4EDDA',
        'font_color': '#155724'
    })
    
    unmatched_fmt = workbook.add_format({
        'font_name': 'Segoe UI',
        'font_size': 10,
        'align': 'center',
        'bg_color': '#F8D7DA',
        'font_color': '#721C24'
    })
    
    for col_num, value in enumerate(df_out.columns.values):
        worksheet.write(0, col_num, value, header_fmt)
        
    worksheet.set_column('A:A', 8, center_fmt)
    worksheet.set_column('B:B', 32, cell_fmt)
    worksheet.set_column('C:C', 14, center_fmt)
    worksheet.set_column('D:D', 32, cell_fmt)
    worksheet.set_column('E:E', 25, cell_fmt)
    worksheet.set_column('F:F', 16, center_fmt)
    worksheet.set_column('G:G', 32, cell_fmt)
    worksheet.set_column('H:H', 22, cell_fmt)
    worksheet.set_column('I:I', 18, num_fmt)
    worksheet.set_column('J:J', 16, center_fmt)
    worksheet.set_column('K:K', 25, cell_fmt)
    worksheet.set_column('L:L', 14, center_fmt)
    worksheet.set_column('M:M', 35, cell_fmt)

print(f"Successfully generated formatted Excel: {OUT_EXCEL}")
