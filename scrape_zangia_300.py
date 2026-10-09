# -*- coding: utf-8 -*-
"""
Scrape Zangia Company Details & Employee Counts for TOP 300 XXK & TOP 167 HK
"""
import urllib.request
import urllib.parse
import json
import re
import time
import os
import pandas as pd

SRC_FILE = '/Users/enkhbadraltsogbayar/Downloads/нөлөөлөгч хувьсагч 300 эрхэм зорилго .xlsx'
OUT_CACHE = '/Users/enkhbadraltsogbayar/Tender data/zangia_all_companies_cache.json'

xl = pd.ExcelFile(SRC_FILE)
df_300 = xl.parse('ТОП 300 ХХК', skiprows=2)
df_167 = xl.parse('ТОП 167 ХК', skiprows=2)

cache = {}
if os.path.exists(OUT_CACHE):
    try:
        with open(OUT_CACHE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        print(f"Loaded existing cache with {len(cache)} companies.")
    except Exception as e:
        print("Error loading cache:", e)

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}

def clean_company_name(name):
    clean = re.sub(r'[\"\'\`\«\»]', '', str(name))
    clean = re.sub(r'(ХХК|ХК|ТӨХК|ТӨҮГ|Групп|Group|LLC|JSC|Холдинг)', '', clean).strip()
    return clean

def extract_emp_from_text(text):
    if not text:
        return None
    matches = re.findall(r'(\d+[\s,.]?\d*)\s*(?:гаруй|орчим)?\s*(?:мэргэшсэн|чадварлаг)?\s*(?:ажилтан|ажилчид|хүнтэй|албан хаагч)', text, re.I)
    if matches:
        val = matches[0].replace(',', '').replace('.', '').replace(' ', '')
        try:
            n = int(val)
            if 5 <= n <= 50000:
                return n
        except: pass
    return None

def fetch_zangia_detail(alias):
    url = f'https://new-api.zangia.mn/api/company/detail?identifier={alias}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read()).get('data', {})
            staffs = data.get('staffs_cnt')
            about = data.get('about', '')
            founded = data.get('founded_year')
            address = data.get('address')
            comp_id = data.get('comp_id')
            
            parsed_emp = None
            if not staffs or staffs == 0:
                parsed_emp = extract_emp_from_text(about)
                
            return {
                'alias': alias,
                'comp_id': comp_id,
                'staffs_cnt': staffs if staffs and staffs > 0 else (parsed_emp or None),
                'founded_year': founded,
                'address': address,
                'about_sample': re.sub(r'<[^>]+>', ' ', about or '')[:200].strip()
            }
    except Exception as e:
        return None

def search_zangia_company(cname):
    clean = clean_company_name(cname)
    words = [w for w in clean.split() if len(w) > 1]
    if not words:
        return None
        
    query = words[0]
    url = f'https://new-api.zangia.mn/api/company/list?query={urllib.parse.quote(query)}&page=1'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            items = json.loads(r.read()).get('items', [])
            for it in items:
                it_name = it.get('name', '').lower()
                # Check if words match
                match = False
                if len(words) == 1:
                    match = words[0].lower() in it_name
                else:
                    match = any(w.lower() in it_name for w in words[:2])
                    
                if match:
                    alias = it.get('alias')
                    staffs = it.get('staffs_cnt')
                    # If staffs is 0, let's fetch detail
                    if not staffs or staffs == 0:
                        detail = fetch_zangia_detail(alias)
                        if detail and detail.get('staffs_cnt'):
                            return detail
                    return {
                        'alias': alias,
                        'comp_id': it.get('comp_id'),
                        'staffs_cnt': staffs if staffs and staffs > 0 else None,
                        'name': it.get('name')
                    }
    except Exception as e:
        pass
    return None

all_targets = []
for idx, r in df_300.iterrows():
    all_targets.append(('TOP300', r['№'], r['Компанийн нэр'], r.get('Албан ёсны вэбсайт')))

for idx, r in df_167.iterrows():
    all_targets.append(('TOP167', r['№'], r['Компанийн нэр'], r.get('Албан ёсны вэбсайт')))

print(f"Total targets to inspect/scrape: {len(all_targets)}")

count_found = 0
for i, (cat, num, cname, web) in enumerate(all_targets):
    cname_clean = str(cname).strip()
    if cname_clean in cache and cache[cname_clean].get('staffs_cnt'):
        count_found += 1
        continue
        
    # Check if direct zangia url
    res = None
    if pd.notna(web) and 'zangia' in str(web).lower():
        m = re.search(r'company/([^/]+)', str(web))
        if m:
            alias = m.group(1)
            res = fetch_zangia_detail(alias)
            
    if not res:
        res = search_zangia_company(cname_clean)
        
    if res:
        cache[cname_clean] = res
        count_found += 1
        print(f"[{i+1}/{len(all_targets)}] [{cat} #{num}] {cname_clean} -> {res.get('staffs_cnt')} staffs ({res.get('alias')})")
    else:
        cache[cname_clean] = {'staffs_cnt': None, 'not_found': True}
        
    if (i+1) % 25 == 0:
        with open(OUT_CACHE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

with open(OUT_CACHE, 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

print(f"Done! Successfully retrieved Zangia info for {count_found} companies.")
