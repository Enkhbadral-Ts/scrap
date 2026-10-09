import json
import re
from collections import defaultdict

def clean_company_name(name):
    if not name: return ''
    name = str(name).lower()
    stopwords = ['ххк', 'хк', 'төхк', 'компани', 'бусад', 'орон нутгийн өмчит', 'xxk', 'xk', 'hxk', 'llc', 'co.,ltd', 'ltd']
    name = re.sub(r'[^\w\sа-яөү]', ' ', name)
    words = name.split()
    clean_words = [w for w in words if w not in stopwords]
    return ''.join(clean_words)

# Known major public companies on MSE to ignore
PUBLIC_COMPANIES = {
    'арддаатгал', 'түмэншувуут', 'мандалдаатгал', 'монголшуудан', 'айтүүлс', 
    'гүүдсекүцк', 'гүүдсек', 'бидисекүцк', 'бидисек', 'андэнерги', 'талхчихэр', 
    'монголынцахилгаанхолбоо', 'бодьдаатгал', 'эрдэнэставантолгой', 'эрдэставантолгой',
    'голомт', 'хаан', 'хаанбанк', 'худалдаахөгжлийн', 'төрийнбанк', 'апу', 'сүү',
    'махимпэкс', 'баянгол', 'инвескор', 'ленмн', 'микхолдинг', 'монголбазальт',
    'ремикон', 'гермесцентр', 'дарханнягт', 'ээж', 'тэнгэрлиг', 'монголтамхисо'
}

def main():
    print("Loading opendatalab registry...")
    with open('opendatalab_legal_entities.json', 'r', encoding='utf-8') as f:
        registry_data = json.load(f)
        
    registry_map = {} # clean_name -> list of dicts
    for row in registry_data:
        c_name = clean_company_name(row.get('name', ''))
        if c_name:
            if c_name not in registry_map:
                registry_map[c_name] = []
            registry_map[c_name].append(row)
            
    print("Loading tender companies...")
    with open('tender_companies_final_clean.json', 'r', encoding='utf-8') as f:
        tender_companies = json.load(f)
        
    tender_name_map = {} # cleaned_name -> set of original names
    for tc in tender_companies:
        for name_field in ['tender_company', 'matched_name']:
            val = tc.get(name_field)
            if val:
                c_name = clean_company_name(val)
                if len(c_name) > 3 and c_name not in PUBLIC_COMPANIES:
                    if c_name not in tender_name_map:
                        tender_name_map[c_name] = set()
                    tender_name_map[c_name].add(val)
                    
    print("Loading ALL 54k xacxom declarations...")
    with open('xacxom_declarations.json', 'r', encoding='utf-8') as f:
        declarations = json.load(f)
        
    matches = []
    
    for dec in declarations:
        stocks_str = dec.get('stock_owner_name')
        if not stocks_str or str(stocks_str).strip() == '-' or str(stocks_str).strip() == '':
            continue
            
        first_name = str(dec.get('search_first_name', '')).strip().lower()
        last_name = str(dec.get('search_last_name', '')).strip().lower()
        official_name = f"{last_name.capitalize()} {first_name.capitalize()}".strip()
            
        stock_items = [s.strip() for s in str(stocks_str).split(',')]
        
        for stock in stock_items:
            c_stock = clean_company_name(stock)
            if len(c_stock) <= 3 or c_stock in PUBLIC_COMPANIES:
                continue
                
            if c_stock in tender_name_map:
                # Check opendatalab for director matching
                directors = []
                director_matched = False
                
                if c_stock in registry_map:
                    for reg in registry_map[c_stock]:
                        dir_name = str(reg.get('director', '')).strip().lower()
                        if dir_name:
                            directors.append(dir_name.title())
                            # Fuzzy check: if official's first name is in director's name
                            if first_name and first_name in dir_name:
                                director_matched = True
                                
                match_info = {
                    'person': official_name,
                    'organization': dec.get('search_organization', ''),
                    'position': dec.get('search_position', ''),
                    'declared_company': stock,
                    'matched_tender_companies': list(tender_name_map[c_stock]),
                    'registry_directors': list(set(directors)),
                    'is_director_match': director_matched
                }
                matches.append(match_info)
                
    print(f"\nFound {len(matches)} total matches.")
    
    # Sort so director matches are first
    matches.sort(key=lambda x: x['is_director_match'], reverse=True)
    
    with open('xacxom_tender_matches_final.json', 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
        
    high_confidence = [m for m in matches if m['is_director_match']]
    print(f"Found {len(high_confidence)} HIGH CONFIDENCE matches (Official's name matches company director!).")
    
if __name__ == "__main__":
    main()
