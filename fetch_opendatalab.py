"""
opendatalab.mn-ээс хуулийн этгээдийн бүртгэлийг татах.
Бүтэц: /legalentity/{letter} -> sub-categories -> /legalentity/{code}/companies
Тус бүр нь Регистрийн дугаар, Нэр, Бүртгэсэн огноо, Дарга, Хаяг-тай.
"""

import re
import json
import time
import csv
from curl_cffi import requests as cf_requests

def get_all_category_codes():
    """Get all letter pages and extract sub-category codes"""
    letters = list('ABCDEFGHIJKLMNOPQRSTU')  # from the page
    all_codes = []
    
    for letter in letters:
        url = f'https://www.opendatalab.mn/legalentity/{letter}'
        print(f'Scanning letter {letter}...')
        try:
            r = cf_requests.get(url, impersonate='chrome120', verify=False, timeout=15)
            codes = re.findall(r'/legalentity/(\d+)/companies', r.text)
            codes = list(set(codes))
            all_codes.extend(codes)
            print(f'  Found {len(codes)} sub-categories')
        except Exception as e:
            print(f'  Error: {e}')
        time.sleep(0.3)
    
    all_codes = sorted(set(all_codes))
    print(f'\nTotal unique category codes: {len(all_codes)}')
    return all_codes


def parse_companies_page(html):
    """Parse company data from HTML page"""
    companies = []
    
    # Pattern: each company block has register no, name, date, director, address
    # Find all register numbers as anchors
    blocks = re.split(r'<hr\s*/?\s*>|<div class="card|<div class="col-', html)
    
    for block in blocks:
        reg_match = re.search(r'Регистрийн дугаар\s*:?\s*</\w+>\s*(\d{7})', block)
        if not reg_match:
            reg_match = re.search(r'Регистрийн дугаар\s*:?\s*(\d{7})', block)
        if not reg_match:
            # Try to find 7-digit number near register text
            reg_match = re.search(r'(\d{7})', block)
        
        if not reg_match:
            continue
            
        reg_no = reg_match.group(1)
        
        # Extract name - usually in <strong> or <h> tag near top of block
        name_match = re.search(r'<strong[^>]*>(.*?)</strong>', block)
        name = re.sub(r'<.*?>', '', name_match.group(1)).strip() if name_match else ''
        
        # Extract date
        date_match = re.search(r'Бүртгэсэн огноо:?\s*</\w+>\s*(\d{4}-\d{2}-\d{2})', block)
        if not date_match:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', block)
        date = date_match.group(1) if date_match else ''
        
        # Extract director
        dir_match = re.search(r'Дарга:?\s*</\w+>\s*([^<]+)', block)
        director = dir_match.group(1).strip() if dir_match else ''
        
        # Extract address
        addr_match = re.search(r'Хаяг:?\s*</\w+>\s*([^<]+)', block)
        address = addr_match.group(1).strip() if addr_match else ''
        
        if reg_no and (name or date):
            companies.append({
                'register_no': reg_no,
                'name': name,
                'registered_date': date,
                'director': director,
                'address': address
            })
    
    return companies


def fetch_all_companies(codes):
    """Fetch companies for all category codes"""
    all_companies = []
    
    for i, code in enumerate(codes):
        url = f'https://www.opendatalab.mn/legalentity/{code}/companies'
        print(f'[{i+1}/{len(codes)}] Fetching code {code}...')
        
        try:
            r = cf_requests.get(url, impersonate='chrome120', verify=False, timeout=30)
            companies = parse_companies_page(r.text)
            all_companies.extend(companies)
            print(f'  Parsed {len(companies)} companies. Total: {len(all_companies)}')
        except Exception as e:
            print(f'  Error: {e}')
        
        time.sleep(0.5)
        
        # Save intermediate results every 20 codes
        if (i + 1) % 20 == 0:
            with open('opendatalab_companies_partial.json', 'w', encoding='utf-8') as f:
                json.dump(all_companies, f, ensure_ascii=False)
            print(f'  [Saved intermediate: {len(all_companies)} records]')
    
    return all_companies


def main():
    print("=== opendatalab.mn хуулийн этгээдийн бүртгэл татах ===\n")
    
    # Step 1: Get all category codes
    print("Step 1: Ангиллын кодуудыг олох...")
    codes = get_all_category_codes()
    
    with open('opendatalab_category_codes.json', 'w') as f:
        json.dump(codes, f)
    
    # Step 2: Fetch all companies
    print("\nStep 2: Компаниудын мэдээллийг татах...")
    companies = fetch_all_companies(codes)
    
    # Step 3: Save results
    print(f"\nStep 3: Хадгалах...")
    
    # Deduplicate by register_no
    seen = set()
    unique = []
    for c in companies:
        if c['register_no'] not in seen:
            seen.add(c['register_no'])
            unique.append(c)
    
    print(f"Total raw: {len(companies)}, Unique by register: {len(unique)}")
    
    # JSON
    with open('opendatalab_legal_entities.json', 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    # CSV
    with open('opendatalab_legal_entities.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['register_no', 'name', 'registered_date', 'director', 'address'])
        writer.writeheader()
        writer.writerows(unique)
    
    print(f"\nDone! Saved {len(unique)} unique legal entities.")
    print("Files: opendatalab_legal_entities.json, opendatalab_legal_entities.csv")


if __name__ == "__main__":
    main()
