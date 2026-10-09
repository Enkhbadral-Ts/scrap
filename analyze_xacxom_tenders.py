import json
import re

def clean_company_name(name):
    if not name: return ''
    name = str(name).lower()
    stopwords = ['ххк', 'хк', 'төхк', 'компани', 'бусад', 'орон нутгийн өмчит', 'xxk', 'xk', 'hxk', 'llc', 'co.,ltd', 'ltd']
    # Replace punct with space
    name = re.sub(r'[^\w\sа-яөү]', ' ', name)
    words = name.split()
    clean_words = [w for w in words if w not in stopwords]
    return ''.join(clean_words)

def main():
    print("Loading tender companies...")
    with open('tender_companies_final_clean.json', 'r', encoding='utf-8') as f:
        tender_companies = json.load(f)
    
    tender_name_map = {} # cleaned_name -> original name(s)
    for tc in tender_companies:
        for name_field in ['tender_company', 'matched_name']:
            val = tc.get(name_field)
            if val:
                c_name = clean_company_name(val)
                if len(c_name) > 3: # Ignore very short names to avoid false positives
                    if c_name not in tender_name_map:
                        tender_name_map[c_name] = set()
                    tender_name_map[c_name].add(val)
                    
    print(f"Loaded {len(tender_name_map)} unique cleaned tender company names.")
    
    print("Loading xacxom declarations...")
    with open('xacxom_declarations_partial.json', 'r', encoding='utf-8') as f:
        declarations = json.load(f)
        
    print(f"Loaded {len(declarations)} declarations.")
    
    matches = []
    
    for dec in declarations:
        stocks_str = dec.get('stock_owner_name')
        if not stocks_str or str(stocks_str).strip() == '-' or str(stocks_str).strip() == '':
            continue
            
        # Split by comma
        stock_items = [s.strip() for s in str(stocks_str).split(',')]
        
        for stock in stock_items:
            c_stock = clean_company_name(stock)
            if len(c_stock) <= 3:
                continue
                
            # Exact match on cleaned names
            if c_stock in tender_name_map:
                # Exclude common state-owned giants if we want to focus on private interests
                # "эрдэнэставантолгой" -> 'эрдэнэставантолгой'
                if 'эрдэнэставантолгой' in c_stock or 'эрдэставантолгой' in c_stock:
                    continue # 1072 shares
                
                matches.append({
                    'person': f"{dec.get('search_last_name', '')} {dec.get('search_first_name', '')}".strip(),
                    'organization': dec.get('search_organization', ''),
                    'position': dec.get('search_position', ''),
                    'declared_company': stock,
                    'matched_tender_companies': list(tender_name_map[c_stock])
                })
                
    print(f"\nFound {len(matches)} potential conflicts of interest (excluding Erdenes Tavantolgoi).")
    
    # Save matches
    with open('xacxom_tender_matches.json', 'w', encoding='utf-8') as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
        
    # Print sample
    for i, m in enumerate(matches[:10]):
        print(f"\nMatch {i+1}:")
        print(f"  Official: {m['person']} ({m['position']} @ {m['organization']})")
        print(f"  Owns: {m['declared_company']}")
        print(f"  Tender Winner: {', '.join(m['matched_tender_companies'])}")

if __name__ == "__main__":
    main()
