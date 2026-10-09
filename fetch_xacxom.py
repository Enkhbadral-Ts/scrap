"""
АТГ xacxom.iaac.mn - Хөрөнгө орлогын мэдүүлгийн бүрэн дата татах.

Стратеги:
  1. /api/public/dropdown/organizations?type=xacxom - 1,910 байгууллагын жагсаалт авах
  2. Байгууллага бүрийн /api/public/xacxom/search - хүмүүсийн жагсаалт авах
  3. Хүн бүрийн /api/public/xacxom/{aid_user_num} - дэлгэрэнгүй мэдүүлэг авах
"""

import json
import csv
import time
from curl_cffi import requests

BASE = "https://xacxom.iaac.mn/api"

def get_organizations():
    """1,910 байгууллагын жагсаалт"""
    r = requests.get(f'{BASE}/public/dropdown/organizations?type=xacxom',
                     impersonate='chrome120', verify=False, timeout=30)
    data = r.json()
    orgs = data.get('retdata', [])
    # Filter to leaf orgs only (ones that have people)
    return [o for o in orgs if o.get('isleaf', False)]

def get_people_by_org(org_id):
    """Тухайн байгууллагын бүх хүмүүсийн жагсаалт"""
    r = requests.post(f'{BASE}/public/xacxom/search',
                      json={"organizationID": org_id},
                      impersonate='chrome120', verify=False, timeout=30)
    data = r.json()
    return data.get('retdata', [])

def get_declaration_detail(aid_user_num):
    """Нэг хүний нарийвчилсан мэдүүлэг"""
    r = requests.get(f'{BASE}/public/xacxom/{aid_user_num}',
                     impersonate='chrome120', verify=False, timeout=15)
    data = r.json()
    ret = data.get('retdata', [])
    return ret[0] if ret else None

def main():
    # Step 1: Get organizations
    print("Step 1: Байгууллагуудыг авч байна...")
    orgs = get_organizations()
    print(f"  Leaf байгууллагууд: {len(orgs)}")
    
    # Step 2: Get all people (by org)
    print("\nStep 2: Хүмүүсийн жагсаалт авч байна...")
    all_people = {}  # aid_user_num -> person info
    
    for i, org in enumerate(orgs):
        org_id = org['value']
        org_name = org['title']
        
        try:
            people = get_people_by_org(org_id)
            for p in people:
                uid = p['aid_user_num']
                if uid not in all_people:
                    all_people[uid] = p
            
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(orgs)}] Total unique people: {len(all_people)}")
            
            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            print(f"  ERROR org {org_id} ({org_name}): {e}")
    
    print(f"\n  Total unique people: {len(all_people)}")
    
    # Save people list
    with open('xacxom_people_list.json', 'w', encoding='utf-8') as f:
        json.dump(list(all_people.values()), f, ensure_ascii=False, indent=2)
    print(f"  Saved: xacxom_people_list.json")
    
    # Step 3: Get detailed declarations
    print("\nStep 3: Дэлгэрэнгүй мэдүүлэг авч байна...")
    all_details = []
    people_list = list(all_people.values())
    
    for i, person in enumerate(people_list):
        uid = person['aid_user_num']
        try:
            detail = get_declaration_detail(uid)
            if detail:
                # Merge person info with detail
                detail['aid_user_num'] = uid
                detail['search_first_name'] = person.get('first_name', '')
                detail['search_last_name'] = person.get('last_name', '')
                detail['search_organization'] = person.get('organization_name', '')
                detail['search_position'] = person.get('position_name', '')
                all_details.append(detail)
            
            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{len(people_list)}] Details fetched: {len(all_details)}")
                
                # Save intermediate
                if (i + 1) % 500 == 0:
                    with open('xacxom_declarations_partial.json', 'w', encoding='utf-8') as f:
                        json.dump(all_details, f, ensure_ascii=False)
                    print(f"    [Saved intermediate: {len(all_details)} records]")
            
            time.sleep(0.05)
        except Exception as e:
            print(f"  ERROR {uid}: {e}")
    
    # Step 4: Save final
    print(f"\nStep 4: Хадгалж байна...")
    print(f"  Total declarations: {len(all_details)}")
    
    with open('xacxom_declarations.json', 'w', encoding='utf-8') as f:
        json.dump(all_details, f, ensure_ascii=False, indent=2)
    
    # Save as CSV too
    if all_details:
        keys = ['aid_user_num', 'search_first_name', 'search_last_name', 'search_organization',
                'search_position', 'year', 'owner_total', 'family_total',
                'total_construction_value', 'transports', 'transport_total_value',
                'animals', 'animal_total_value', 'land_total_value',
                'savings_mon_total', 'savings_other_total', 'loan_total_value',
                'stock_owner_name', 'stock_total_value', 'equipment_value',
                'gift_total_value', 'name', 'position_name', 'org_names']
        
        with open('xacxom_declarations.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_details)
    
    print(f"\n✅ Done!")
    print(f"  xacxom_declarations.json: {len(all_details)} declarations")
    print(f"  xacxom_declarations.csv: {len(all_details)} rows")

if __name__ == "__main__":
    main()
