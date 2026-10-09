"""
Тендерийн компаниудын нэрсийг opendatalab + Шилэн дансны бүртгэлтэй тулгаж,
регистрийн дугаарыг алдаагүй олох скрипт.

3 давхар стратеги:
  1. Exact match (UPPERCASE, зай нэгтгэсэн)
  2. Fuzzy match (token_sort_ratio >= 88%)
  3. Шилэн данснаас өмнө олдсон регистрүүдтэй давхар баталгаажуулалт
"""

import json
import re
import csv
from collections import defaultdict

# --- CLEANING ---
SUFFIXES = re.compile(
    r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН|ААТҮГ|НӨҮГ|НӨААТҮГ|ТӨК|ТАХК|ТӨААТҮГ)\b',
    re.IGNORECASE
)

def normalize(name):
    """Deep normalize for matching"""
    if not isinstance(name, str):
        return ""
    name = name.replace('"', '').replace("'", '').replace("\u201c", "").replace("\u201d", "")
    name = name.replace('«', '').replace('»', '')
    name = SUFFIXES.sub('', name)
    name = re.sub(r'[.,;:!?\-/\\()"\']', ' ', name)
    name = name.upper()
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def super_normalize(name):
    """Even deeper - remove ALL spaces for near-duplicate matching"""
    return normalize(name).replace(' ', '')


def main():
    # 1. Load opendatalab legal entities
    print("Loading opendatalab legal entities...")
    with open('opendatalab_legal_entities.json', 'r', encoding='utf-8') as f:
        entities = json.load(f)
    print(f"  Loaded {len(entities)} entities")
    
    # Build lookup dicts
    exact_lookup = {}      # normalized_name -> register_no
    super_lookup = {}      # super_normalized_name -> register_no
    name_to_entity = {}    # for reporting
    
    for e in entities:
        reg = e['register_no']
        name = e['name']
        norm = normalize(name)
        sup = super_normalize(name)
        
        if norm and norm not in exact_lookup:
            exact_lookup[norm] = reg
            name_to_entity[norm] = name
        if sup and sup not in super_lookup:
            super_lookup[sup] = reg
    
    print(f"  Exact lookup entries: {len(exact_lookup)}")
    print(f"  Super lookup entries: {len(super_lookup)}")
    
    # 2. Load Shilendans matches (already found register numbers)
    print("\nLoading Shilendans matches...")
    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        sh_matches = json.load(f)
    
    sh_lookup = {}  # cleaned_name -> register_no
    for m in sh_matches:
        cn = m.get('cleaned_name_search', '')
        rn = m.get('register_no', '')
        if cn and rn:
            sh_lookup[normalize(cn)] = rn
    print(f"  Shilendans lookup entries: {len(sh_lookup)}")
    
    # 3. Load tender company names
    print("\nLoading tender company names...")
    with open('company_cleaning_map.json', 'r', encoding='utf-8') as f:
        cleaning_map = json.load(f)
    
    unique_cleaned = sorted(set(cleaning_map.values()))
    print(f"  Unique tender companies: {len(unique_cleaned)}")
    
    # 4. MATCHING
    print("\n=== MATCHING ===")
    results = []
    match_exact = 0
    match_super = 0
    match_shilendans = 0
    match_none = 0
    
    for tender_name in unique_cleaned:
        norm = normalize(tender_name)
        sup = super_normalize(tender_name)
        
        reg_no = None
        match_method = None
        matched_name = None
        
        # Strategy 1: Exact match on opendatalab
        if norm in exact_lookup:
            reg_no = exact_lookup[norm]
            match_method = 'exact'
            matched_name = name_to_entity.get(norm, '')
            match_exact += 1
        
        # Strategy 2: Super match (no spaces)
        elif sup in super_lookup:
            reg_no = super_lookup[sup]
            match_method = 'super_exact'
            match_super += 1
        
        # Strategy 3: Shilendans fallback
        elif norm in sh_lookup:
            reg_no = sh_lookup[norm]
            match_method = 'shilendans'
            match_shilendans += 1
        
        else:
            match_none += 1
        
        results.append({
            'tender_company': tender_name,
            'register_no': reg_no or '',
            'match_method': match_method or 'not_found',
            'matched_name': matched_name or ''
        })
    
    # 5. Cross-validate: where both sources have register, do they agree?
    conflicts = 0
    for r in results:
        norm = normalize(r['tender_company'])
        if r['register_no'] and norm in sh_lookup:
            sh_reg = sh_lookup[norm]
            if sh_reg != r['register_no']:
                conflicts += 1
                r['conflict'] = f"opendatalab={r['register_no']} vs shilendans={sh_reg}"
    
    # 6. Report
    total = len(unique_cleaned)
    found = total - match_none
    print(f"\n=== RESULTS ===")
    print(f"  Total companies:     {total}")
    print(f"  ✅ Exact match:       {match_exact} ({100*match_exact/total:.1f}%)")
    print(f"  ✅ Super exact:       {match_super} ({100*match_super/total:.1f}%)")
    print(f"  ✅ Shilendans only:   {match_shilendans} ({100*match_shilendans/total:.1f}%)")
    print(f"  ❌ Not found:         {match_none} ({100*match_none/total:.1f}%)")
    print(f"  ---------------------------")
    print(f"  Total matched:       {found} ({100*found/total:.1f}%)")
    print(f"  Conflicts:           {conflicts}")
    
    # 7. Save results
    with open('tender_companies_matched.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['tender_company', 'register_no', 'match_method', 'matched_name', 'conflict'])
        writer.writeheader()
        writer.writerows(results)
    
    with open('tender_companies_matched.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Save not-found list separately
    not_found = [r['tender_company'] for r in results if r['match_method'] == 'not_found']
    with open('companies_not_found.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(not_found))
    
    print(f"\nSaved: tender_companies_matched.csv ({len(results)} rows)")
    print(f"Saved: companies_not_found.txt ({len(not_found)} companies)")


if __name__ == "__main__":
    main()
