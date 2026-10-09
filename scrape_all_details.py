import json
import re
import pandas as pd
from curl_cffi import requests as cffi_requests
import concurrent.futures
import time
import os
import threading

def fetch_details(inv_id):
    url = f"https://tender.gov.mn/mn/invitation/detail/{inv_id}"
    headers = {"RSC": "1"}
    
    for attempt in range(5):
        try:
            r = cffi_requests.get(url, impersonate="chrome120", headers=headers, timeout=15)
            if r.status_code == 200:
                text = r.text
                res = {}
                sm = re.search(r'startDate=(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})', text)
                if sm:
                    res["Зарласан огноо"] = sm.group(1)
                    
                labels = re.findall(r'"label":"([^"]+)","value":("?[^"}]+)("?)', text)
                for lbl, val, endq in labels:
                    val = val.strip(',').strip('"')
                    if lbl not in res:
                        res[lbl] = val
                
                # If we got at least something, return it
                if res:
                    return inv_id, res
                return inv_id, {}
            elif r.status_code == 429:
                time.sleep(5 + attempt * 2)
            else:
                time.sleep(1)
        except Exception as e:
            time.sleep(2)
    return inv_id, {}

def main():
    excel_path = "FINAL_Tender_Report_2021_2025.xlsx"
    print(f"Loading {excel_path}...")
    df = pd.read_excel(excel_path)
    
    unique_tender_codes = df["Тендерийн дугаар"].dropna().unique().tolist()
    print(f"Total unique tender codes in report: {len(unique_tender_codes)}")
    
    # Build mapping from tender_code -> inv_id
    code_to_id = {}
    for year in range(2021, 2026):
        cache_file = f"tenders_{year}_links_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for row in data:
                    code = row.get("tender_code")
                    inv_id = row.get("inv_id")
                    if code and inv_id:
                        code_to_id[code.strip()] = inv_id.strip()
    
    inv_id_to_code = {}
    to_fetch_ids = set()
    for code in unique_tender_codes:
        code_str = str(code).strip()
        if code_str in code_to_id:
            i_id = code_to_id[code_str]
            to_fetch_ids.add(i_id)
            inv_id_to_code[i_id] = code_str
            
    print(f"Mapped {len(to_fetch_ids)} unique inv_ids to fetch.")
    
    cache_file = "tender_details_cache.json"
    results = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            results = json.load(f)
            print(f"Loaded {len(results)} details from cache.")
            
    to_fetch = [uid for uid in to_fetch_ids if uid not in results or not results[uid].get("Арга")]
    print(f"Remaining to fetch: {len(to_fetch)}")
    
    start_time = time.time()
    done = 0
    lock = threading.Lock()
    
    if to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            future_to_id = {executor.submit(fetch_details, uid): uid for uid in to_fetch}
            for future in concurrent.futures.as_completed(future_to_id):
                uid = future_to_id[future]
                done += 1
                try:
                    res_id, data = future.result()
                    if data:
                        with lock:
                            results[uid] = data
                except Exception as e:
                    pass
                    
                if done % 100 == 0 or done == len(to_fetch):
                    elapsed = time.time() - start_time
                    speed = done / elapsed if elapsed > 0 else 0
                    print(f"Progress: {done}/{len(to_fetch)} ({speed:.1f} req/s). Found {len(results)} details.")
                    with lock:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("Finished fetching details!")
    
    # Map back to dataframe
    fields_to_add = [
        "Зарласан огноо",
        "Санал хүлээн авах огноо",
        "Нээх огноо",
        "Төрөл",
        "Санхүүжилтийн эх үүсвэр",
        "Нийт төсөвт өртөг",
        "Арга",
        "Цахим тендер эсэх",
        "Холбоо барих",
        "Хаяг"
    ]
    
    for field in fields_to_add:
        df[f"{field}"] = df["Тендерийн дугаар"].map(
            lambda c: results.get(code_to_id.get(str(c).strip()), {}).get(field, "")
        )
    
    # Rename old date column
    if 'Тендер зарласан огноо' in df.columns:
        df = df.rename(columns={'Тендер зарласан огноо': 'Гэрээ байгуулсан огноо'})
    
    final_output = "FINAL_Tender_Report_2021_2025_With_Details.xlsx"
    print(f"Saving merged data to {final_output}...")
    df.to_excel(final_output, index=False)
    print("Done!")

if __name__ == "__main__":
    main()
