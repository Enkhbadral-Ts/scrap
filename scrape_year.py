import sys
import os
import re
import json
import time
import argparse
import threading
import concurrent.futures
import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session(impersonate="chrome120")
    return thread_local.session

def fetch_page_links(year, page, retries=6):
    url = "https://user.tender.gov.mn/mn/result"
    params = {"year": year, "get": 1, "page": page, "sort": "createDate", "order": "desc"}
    links = []
    
    for attempt in range(retries):
        try:
            s = get_session()
            r = s.get(url, params=params, headers=headers, timeout=20)
            if r.status_code == 429:
                time.sleep(6 + attempt * 3)
                continue
            if r.status_code != 200:
                time.sleep(2)
                continue
                
            soup = BeautifulSoup(r.text, "html.parser")
            trs = soup.find_all("tr")
            if len(trs) <= 1:
                return links
                
            for tr in trs[1:]:
                tds = tr.find_all("td")
                if len(tds) >= 7:
                    st = tds[6].text.strip()
                    if "Үр дүн гарсан" in st or "Гэрээ байгуулсан" in st:
                        a = tr.find("a", href=lambda h: h and "/result/detail/" in h)
                        if a:
                            links.append({
                                "inv_id": a["href"].split("/")[-1],
                                "tender_code": tds[0].text.strip(),
                                "tender_name": tds[2].text.strip(),
                                "client": tds[3].text.strip(),
                                "status": st,
                                "date": tds[5].text.strip().split()[0] if len(tds) > 5 else ""
                            })
            return links
        except Exception:
            time.sleep(2)
    return links

def fetch_winner_data(item, retries=6):
    inv_id = item["inv_id"]
    winners = []
    payload = {
        "invitationId": inv_id,
        "search": "search",
        "groupBy": "tender",
        "invitationTypeId": "1"
    }
    
    for attempt in range(retries):
        try:
            s = get_session()
            r = s.post("https://user.tender.gov.mn/mn/result/detail/disBidderList", data=payload, headers=headers, timeout=20)
            if r.status_code == 429:
                time.sleep(6 + attempt * 3)
                continue
            if r.status_code != 200:
                time.sleep(2)
                continue
                
            data = r.json().get("data", [])
            for w_item in data:
                comp_name = w_item.get("3", "").strip() or w_item.get("0", "").strip()
                amt_html = w_item.get("4", "")
                amt_str = BeautifulSoup(amt_html, "html.parser").text if "<" in amt_html else amt_html
                digits = re.sub(r"[^\d.]", "", amt_str)
                amt = float(digits) if digits else 0.0
                date_str = w_item.get("5", "").strip()
                
                if comp_name and amt > 0:
                    row = item.copy()
                    row["company"] = comp_name
                    row["amount"] = amt
                    if date_str:
                        row["date"] = date_str
                    winners.append(row)
            break
        except Exception:
            time.sleep(2)
            
    return winners

def scrape_year(year, max_pages, max_workers=18):
    print(f"\n================ STARTING SCRAPING FOR YEAR {year} ================")
    links_cache_file = f"tenders_{year}_links_cache.json"
    winners_cache_file = f"winners_{year}_cache.json"
    checked_invs_file = f"checked_{year}_invs.json"
    
    # 1. Fetch listing pages
    unique_links = []
    if os.path.exists(links_cache_file):
        print(f"Loading cached listing links from {links_cache_file}...")
        with open(links_cache_file, "r", encoding="utf-8") as f:
            unique_links = json.load(f)
        print(f"Loaded {len(unique_links)} cached finalized tenders.")
    else:
        print(f"Scanning pages 1 to {max_pages} for {year} with {max_workers} workers...")
        all_links = []
        pages = list(range(1, max_pages + 1))
        
        start_t = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            f_map = {ex.submit(fetch_page_links, year, p): p for p in pages}
            done = 0
            for f in concurrent.futures.as_completed(f_map):
                done += 1
                res = f.result()
                if res:
                    all_links.extend(res)
                if done % 100 == 0 or done == len(pages):
                    elapsed = time.time() - start_t
                    speed = done / elapsed if elapsed > 0 else 0
                    print(f"Scanned {done}/{len(pages)} listing pages ({speed:.1f} p/s)... ({len(all_links)} finalized tenders found so far)")
                    
        # Dedup by inv_id
        unique_links = list({d["inv_id"]: d for d in all_links}.values())
        print(f"Found {len(unique_links)} unique finalized tenders in {time.time()-start_t:.1f}s.")
        with open(links_cache_file, "w", encoding="utf-8") as f:
            json.dump(unique_links, f, ensure_ascii=False, indent=2)
        print(f"Saved listing cache to {links_cache_file}.")

    # 2. Fetch winner details
    winners_map = {}
    if os.path.exists(winners_cache_file):
        print(f"Loading cached winners from {winners_cache_file}...")
        with open(winners_cache_file, "r", encoding="utf-8") as f:
            winners_list = json.load(f)
            for w in winners_list:
                winners_map.setdefault(w["inv_id"], []).append(w)
        print(f"Loaded {len(winners_list)} winners from cache.")
        
    checked_invs = set()
    if os.path.exists(checked_invs_file):
        with open(checked_invs_file, "r", encoding="utf-8") as f:
            checked_invs = set(json.load(f))
            
    tenders_to_check = [item for item in unique_links if item["inv_id"] not in checked_invs and item["inv_id"] not in winners_map]
    print(f"Tenders remaining to fetch details: {len(tenders_to_check)} (Already checked: {len(checked_invs) + len(winners_map)})")
    
    all_winners = []
    for w_list in winners_map.values():
        all_winners.extend(w_list)
        
    if tenders_to_check:
        start_t = time.time()
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            f_map = {ex.submit(fetch_winner_data, item): item for item in tenders_to_check}
            for f in concurrent.futures.as_completed(f_map):
                done += 1
                item = f_map[f]
                res = f.result()
                checked_invs.add(item["inv_id"])
                if res:
                    all_winners.extend(res)
                    
                if done % 250 == 0 or done == len(tenders_to_check):
                    elapsed = time.time() - start_t
                    speed = done / elapsed if elapsed > 0 else 0
                    print(f"Processed {done}/{len(tenders_to_check)} tenders ({speed:.1f} tenders/s)... Total winners: {len(all_winners)}")
                    # Save checkpoint
                    with open(winners_cache_file, "w", encoding="utf-8") as wf:
                        json.dump(all_winners, wf, ensure_ascii=False, indent=2)
                    with open(checked_invs_file, "w", encoding="utf-8") as cf:
                        json.dump(list(checked_invs), cf)

    print(f"\nFinal count of winning contracts for {year}: {len(all_winners)}")
    if not all_winners:
        print("No winners found!")
        return
        
    # 3. Create DataFrame and export files
    df = pd.DataFrame(all_winners)
    df["company"] = df["company"].str.strip()
    df = df[~df["company"].str.match(r"^\d+\s*$")]
    df = df.drop_duplicates(subset=["inv_id", "company", "amount"])
    
    # Ensure exact column order matching 2023-2025 datasets
    cols = ["inv_id", "tender_code", "tender_name", "client", "status", "company", "amount", "date"]
    ordered_cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
    df = df[ordered_cols]
    
    raw_csv = f"all_{year}_winners_raw.csv"
    excel_csv = f"all_{year}_winners_excel_zoriulalt.csv"
    excel_xlsx = f"all_{year}_winners_excel_zoriulalt.xlsx"
    
    df.to_csv(raw_csv, index=False)
    df.to_csv(excel_csv, index=False, encoding="utf-8-sig")
    df.to_excel(excel_xlsx, index=False)
    print(f"Saved {raw_csv}, {excel_csv}, {excel_xlsx}")
    
    # 4. Generate Reports
    grouped = df.groupby("company").agg(
        total_won=("amount", "sum"),
        wins=("inv_id", "nunique")
    ).reset_index().sort_values("total_won", ascending=False)
    
    total_contracts = len(df)
    total_companies = df["company"].nunique()
    total_clients = df["client"].nunique()
    
    print("\n" + "=" * 50)
    print(f"ЕРӨНХИЙ СТАТИСТИК ({year} ОН)")
    print("=" * 50)
    print(f"Нийт баталгаажсан гэрээний тоо: {total_contracts}")
    print(f"Тендерт шалгарсан компаниудын тоо: {total_companies}")
    print(f"Тендер зарлагч /захиалагч/ байгууллагын тоо: {total_clients}\n")
    
    top20_amount = grouped.head(20)
    top20_count = df.groupby("company").agg(
        wins=("inv_id", "nunique"),
        total_won=("amount", "sum")
    ).reset_index().sort_values("wins", ascending=False).head(20)
    
    md_amount = f"""## {year} Оны Тендерийн Шилдэг 20 Компани (Дүнгээр)

### Ерөнхий статистик
- **Нийт гэрээ байгуулсан тендерийн тоо:** {total_contracts}
- **Шалгарсан компаниудын тоо:** {total_companies}
- **Тендер захиалагч байгууллагуудын тоо:** {total_clients}

### Шилдэг 20 (Борлуулалтын дүнгээр)

| Д/д | Компани | Нийт дүн (₮) | Гэрээний тоо |
| --- | --- | --- | --- |
"""
    for i, row in enumerate(top20_amount.itertuples(), 1):
        amt_fmt = f"{row.total_won:,.0f}"
        md_amount += f"| {i} | {row.company} | `{amt_fmt} ₮` | {row.wins} |\n"
        
    amount_file = f"top20_{year}_by_amount.md"
    with open(amount_file, "w", encoding="utf-8") as f:
        f.write(md_amount)
        
    md_count = f"""## {year} Оны Хамгийн Олон Тендер Авсан Топ 20 Компани

| Д/д | Компани | Гэрээний тоо | Нийт дүн (₮) |
| --- | --- | --- | --- |
"""
    for i, row in enumerate(top20_count.itertuples(), 1):
        amt_fmt = f"{row.total_won:,.0f}"
        md_count += f"| {i} | {row.company} | {row.wins} | `{amt_fmt} ₮` |\n"
        
    count_file = f"top20_{year}_by_count.md"
    with open(count_file, "w", encoding="utf-8") as f:
        f.write(md_count)
        
    print(f"Saved {amount_file} and {count_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape tender data for a given year")
    parser.add_argument("--year", type=int, required=True, help="Year to scrape (e.g. 2021, 2022)")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages (default: 1100 for 2021, 1304 for 2022)")
    parser.add_argument("--workers", type=int, default=18, help="Number of worker threads (default 18)")
    args = parser.parse_args()
    
    pages = args.pages
    if pages is None:
        if args.year == 2021:
            pages = 1100
        elif args.year == 2022:
            pages = 1304
        else:
            pages = 800
            
    scrape_year(args.year, pages, args.workers)
