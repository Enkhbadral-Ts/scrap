"""
fetch_xacxom_all_years.py
Хуучин скрипт зөвхөн ret[0] (нэг жил) авсан.
Энэ скрипт retdata доторх БҮХ жилийн мэдүүлгийг авна.

Стратеги:
  - xacxom_people_list.json-аас хүмүүсийн жагсаалт авах (54,908 хүн)
  - Хүн бүрийн /api/public/xacxom/{aid_user_num} дуудаж, 
    retdata доторх БҮХ жилүүдийг хадгалах
  - Шинэ файл: xacxom_declarations_all_years.json
"""

import json
import csv
import time
import os
import concurrent.futures
import threading
from curl_cffi import requests

BASE = "https://xacxom.iaac.mn/api"
thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session(impersonate="chrome120")
    return thread_local.session

def fetch_all_years(person, retries=5):
    """Нэг хүний БҮХ жилийн мэдүүлгийг авах"""
    uid = person['aid_user_num']
    results = []
    
    for attempt in range(retries):
        try:
            s = get_session()
            r = s.get(f'{BASE}/public/xacxom/{uid}',
                     verify=False, timeout=15)
            if r.status_code == 429:
                time.sleep(3 + attempt * 2)
                continue
            if r.status_code != 200:
                time.sleep(1)
                continue
            
            data = r.json()
            retdata = data.get('retdata', [])
            
            for item in retdata:
                item['aid_user_num'] = uid
                item['search_first_name'] = person.get('first_name', '')
                item['search_last_name'] = person.get('last_name', '')
                item['search_organization'] = person.get('organization_name', '')
                item['search_position'] = person.get('position_name', '')
                results.append(item)
            
            return results
        except Exception as e:
            time.sleep(1)
    
    return results

def main():
    print("=" * 60)
    print("  XACXOM БҮХ ЖИЛИЙН МЭДҮҮЛЭГ ТАТАХ")
    print("=" * 60)
    
    # Load people list
    with open('xacxom_people_list.json', 'r', encoding='utf-8') as f:
        people = json.load(f)
    print(f"\nНийт хүн: {len(people):,}")
    
    # Calculate expected records
    total_expected = sum(len(p.get('years', [])) for p in people)
    print(f"Нийт хүлээгдэж буй мэдүүлэг: {total_expected:,}")
    
    # Load checkpoint if exists
    checkpoint_file = 'xacxom_allyears_checkpoint.json'
    all_details = []
    done_uids = set()
    
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)
        all_details = checkpoint.get('data', [])
        done_uids = set(checkpoint.get('done_uids', []))
        print(f"Checkpoint loaded: {len(all_details):,} records, {len(done_uids):,} people done")
    
    # Filter remaining
    remaining = [p for p in people if p['aid_user_num'] not in done_uids]
    print(f"Үлдсэн: {len(remaining):,} хүн")
    
    if not remaining:
        print("Бүгд дууссан!")
    else:
        start_time = time.time()
        done = 0
        errors = 0
        
        # Use ThreadPoolExecutor for speed (12 workers to be respectful)
        batch_size = 500
        workers = 12
        
        for batch_start in range(0, len(remaining), batch_size):
            batch = remaining[batch_start:batch_start + batch_size]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(fetch_all_years, p): p for p in batch}
                for future in concurrent.futures.as_completed(futures):
                    person = futures[future]
                    done += 1
                    try:
                        results = future.result()
                        if results:
                            all_details.extend(results)
                        done_uids.add(person['aid_user_num'])
                    except Exception as e:
                        errors += 1
            
            # Progress
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 0
            total_done = len(done_uids)
            print(f"  [{total_done:,}/{len(people):,}] Records: {len(all_details):,} "
                  f"| Speed: {speed:.1f}/s | Errors: {errors} "
                  f"| ETA: {(len(remaining)-done)/speed/60:.1f}min" if speed > 0 else "")
            
            # Save checkpoint every batch
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'data': all_details,
                    'done_uids': list(done_uids)
                }, f, ensure_ascii=False)
    
    # Save final
    print(f"\nSaving final files...")
    
    with open('xacxom_declarations_all_years.json', 'w', encoding='utf-8') as f:
        json.dump(all_details, f, ensure_ascii=False, indent=2)
    
    # Stats
    from collections import Counter
    year_dist = Counter(d.get('year') for d in all_details)
    print(f"\n{'='*60}")
    print(f"  ДУУСЛАА!")
    print(f"{'='*60}")
    print(f"  Нийт мэдүүлэг: {len(all_details):,}")
    print(f"  Жилийн тархалт:")
    for yr in sorted(year_dist.keys()):
        print(f"    {yr}: {year_dist[yr]:,}")
    
    # Save CSV too
    if all_details:
        keys = ['aid_user_num', 'search_first_name', 'search_last_name', 'search_organization',
                'search_position', 'year', 'owner_total', 'family_total',
                'total_construction_value', 'transports', 'transport_total_value',
                'animals', 'animal_total_value', 'land_total_value',
                'savings_mon_total', 'savings_other_total', 'loan_total_value',
                'stock_owner_name', 'stock_total_value', 'equipment_value',
                'gift_total_value', 'name', 'position_name', 'org_names',
                'rocivilservice', 'rank']
        
        with open('xacxom_declarations_all_years.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_details)
        print(f"  xacxom_declarations_all_years.csv saved")
    
    # Cleanup checkpoint
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
        print("  Checkpoint removed")

if __name__ == "__main__":
    main()
