"""
Олдоогүй 2,666 компанийг бүрэн fuzzy match хийж олох.

Стратеги:
  1. Token sort ratio >= 85% (үгийн дараалал хамаагүй)
  2. Partial ratio >= 90% (богино нэр урт нэрийн дотор бүрэн агуулагдах)
  3. Монгол кирилл <-> Латин хөрвүүлэлт (Эй Би Си = ABC)
  4. Нэмэлт suffix устгалт (Групп, Констракшн, Трейд г.м)
  5. Олон оноосон нэртэй компаниудыг (жишээ нь бүртгэлд "Мөнх" гэж байгааг "Мөнх импекс" тулгах)
"""

import json
import re
import csv
from rapidfuzz import fuzz, process

# --- NORMALIZATION ---
SUFFIXES = re.compile(
    r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН|'
    r'ААТҮГ|НӨҮГ|НӨААТҮГ|ТӨК|ТАХК|ТӨААТҮГ|НӨХӨРЛӨЛ|ЗБН|ХОРШОО|'
    r'ГРУППП?|ТРЕЙД|КОНСТРАКШН|КОНСТРАКШЕН|КОРПОРЕЙШН|КОРПОРЭЙШН|ИНТЕРНЭШНЛ|ИНТЕРНЕЙШНЛ|'
    r'КОМПАНИ|МОНГОЛ[ИЫ]?А?|LLC|CO\.?\s*LTD\.?|LTD|INC|CORP)\b',
    re.IGNORECASE
)

def normalize(name):
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
    return normalize(name).replace(' ', '')


def main():
    # 1. Load not-found companies
    with open('companies_not_found.txt', 'r', encoding='utf-8') as f:
        not_found = [line.strip() for line in f if line.strip()]
    print(f"Not found companies to fuzzy match: {len(not_found)}")
    
    # 2. Load opendatalab entities
    with open('opendatalab_legal_entities.json', 'r', encoding='utf-8') as f:
        entities = json.load(f)
    print(f"Opendatalab entities: {len(entities)}")
    
    # Build normalized name -> (register_no, original_name) 
    entity_lookup = {}
    for e in entities:
        norm = normalize(e['name'])
        if norm and len(norm) >= 2:
            if norm not in entity_lookup:
                entity_lookup[norm] = (e['register_no'], e['name'])
    
    entity_names = list(entity_lookup.keys())
    print(f"Normalized entity names for fuzzy search: {len(entity_names)}")
    
    # 3. Load Shilendans matches
    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        sh_matches = json.load(f)
    sh_lookup = {}
    for m in sh_matches:
        cn = m.get('cleaned_name_search', '')
        rn = m.get('register_no', '')
        if cn and rn:
            sh_lookup[normalize(cn)] = rn
    
    # 4. Load existing matched results
    with open('tender_companies_matched.json', 'r', encoding='utf-8') as f:
        existing = json.load(f)
    existing_map = {r['tender_company']: r for r in existing}
    
    # 5. Fuzzy matching
    print("\n=== FUZZY MATCHING ===")
    new_matches = 0
    fuzzy_results = []
    
    for i, company in enumerate(not_found):
        norm = normalize(company)
        if len(norm) < 2:
            fuzzy_results.append({
                'tender_company': company,
                'register_no': '',
                'match_method': 'too_short',
                'matched_name': '',
                'score': 0
            })
            continue
        
        # Try token_sort_ratio (best for word reordering)
        best_match = process.extractOne(
            norm, entity_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=85
        )
        
        if best_match:
            matched_norm, score, _ = best_match
            reg_no, orig_name = entity_lookup[matched_norm]
            
            fuzzy_results.append({
                'tender_company': company,
                'register_no': reg_no,
                'match_method': f'fuzzy_token_{score:.0f}',
                'matched_name': orig_name,
                'score': score
            })
            new_matches += 1
        else:
            # Try partial_ratio (substring match) for short names
            best_partial = process.extractOne(
                norm, entity_names,
                scorer=fuzz.partial_ratio,
                score_cutoff=92
            )
            
            if best_partial and len(norm) >= 4:
                matched_norm, score, _ = best_partial
                reg_no, orig_name = entity_lookup[matched_norm]
                
                fuzzy_results.append({
                    'tender_company': company,
                    'register_no': reg_no,
                    'match_method': f'fuzzy_partial_{score:.0f}',
                    'matched_name': orig_name,
                    'score': score
                })
                new_matches += 1
            else:
                # Try Shilendans with fuzzy
                sh_names = list(sh_lookup.keys())
                if sh_names:
                    best_sh = process.extractOne(
                        norm, sh_names,
                        scorer=fuzz.token_sort_ratio,
                        score_cutoff=88
                    )
                    if best_sh:
                        matched_norm, score, _ = best_sh
                        reg_no = sh_lookup[matched_norm]
                        fuzzy_results.append({
                            'tender_company': company,
                            'register_no': reg_no,
                            'match_method': f'fuzzy_shilendans_{score:.0f}',
                            'matched_name': matched_norm,
                            'score': score
                        })
                        new_matches += 1
                    else:
                        fuzzy_results.append({
                            'tender_company': company,
                            'register_no': '',
                            'match_method': 'not_found',
                            'matched_name': '',
                            'score': 0
                        })
                else:
                    fuzzy_results.append({
                        'tender_company': company,
                        'register_no': '',
                        'match_method': 'not_found',
                        'matched_name': '',
                        'score': 0
                    })
        
        if (i + 1) % 200 == 0:
            print(f"  Progress: {i+1}/{len(not_found)} - New matches: {new_matches}")
    
    # 6. Merge with existing results
    for fr in fuzzy_results:
        if fr['tender_company'] in existing_map:
            existing_map[fr['tender_company']] = {
                'tender_company': fr['tender_company'],
                'register_no': fr['register_no'],
                'match_method': fr['match_method'],
                'matched_name': fr['matched_name']
            }
    
    all_results = list(existing_map.values())
    
    # 7. Final stats
    total = len(all_results)
    found = sum(1 for r in all_results if r.get('register_no'))
    still_missing = total - found
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"  Total companies:      {total}")
    print(f"  ✅ Matched (total):    {found} ({100*found/total:.1f}%)")
    print(f"  ❌ Still not found:    {still_missing} ({100*still_missing/total:.1f}%)")
    print(f"  🆕 New fuzzy matches:  {new_matches}")
    
    # 8. Save final merged results
    with open('tender_companies_final.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['tender_company', 'register_no', 'match_method', 'matched_name'],
                               extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_results)
    
    with open('tender_companies_final.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    # Save remaining not-found
    remaining = [r['tender_company'] for r in all_results if not r.get('register_no')]
    with open('companies_still_not_found.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(remaining))
    
    print(f"\nSaved: tender_companies_final.csv")
    print(f"Saved: companies_still_not_found.txt ({len(remaining)} companies)")
    
    # Show some fuzzy match examples
    print(f"\n--- Fuzzy match жишээнүүд ---")
    examples = [fr for fr in fuzzy_results if fr['register_no']][:15]
    for ex in examples:
        print(f"  \"{ex['tender_company']}\" -> \"{ex['matched_name']}\" (reg: {ex['register_no']}, {ex['match_method']})")

if __name__ == "__main__":
    main()
