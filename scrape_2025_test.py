import requests
from bs4 import BeautifulSoup
import json
import re
import concurrent.futures
import pandas as pd
import time

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'X-Requested-With': 'XMLHttpRequest'
}

def get_page_links(page):
    links = []
    try:
        url = "https://user.tender.gov.mn/mn/result"
        params = {"year": 2025, "get": 1, "page": page, "sort": "createDate", "order": "desc"}
        r = requests.get(url, params=params, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        trs = soup.find_all("tr")
        if len(trs) <= 1:
            return links
            
        for tr in trs[1:]:
            txt = tr.text
            if 'Үр дүн гарсан' in txt or 'Гэрээ байгуулсан' in txt:
                tds = tr.find_all("td")
                if len(tds) >= 7:
                    a = tr.find("a", href=lambda h: h and "/result/detail/" in h)
                    if a:
                        inv_id = a["href"].split('/')[-1]
                        tender_code = tds[0].text.strip()
                        tender_name = tds[2].text.strip()
                        client = tds[3].text.strip()
                        status = tds[6].text.strip()
                        links.append({
                            'inv_id': inv_id,
                            'tender_code': tender_code,
                            'tender_name': tender_name,
                            'client': client,
                            'status': status
                        })
    except Exception as e:
        pass
    return links

def get_winner_data(item):
    inv_id = item['inv_id']
    winners = []
    try:
        payload = {
            'invitationId': inv_id,
            'search': 'search',
            'groupBy': 'tender',
            'invitationTypeId': '1'
        }
        for attempt in range(3):
            try:
                res = requests.post("https://user.tender.gov.mn/mn/result/detail/disBidderList", data=payload, headers=headers, timeout=15)
                if res.status_code != 200:
                    time.sleep(1)
                    continue
                data = res.json().get('data', [])
                for w_item in data:
                    comp_name = w_item.get("3", "").strip() or w_item.get("0", "").strip()
                    
                    amt_html = w_item.get("4", "")
                    amt_str = BeautifulSoup(amt_html, 'html.parser').text if '<' in amt_html else amt_html
                    digits = re.sub(r'[^\d.]', '', amt_str)
                    amt = float(digits) if digits else 0.0
                    
                    date_str = w_item.get("5", "")
                    
                    if comp_name and amt > 0:
                        row = item.copy()
                        row['company'] = comp_name
                        row['amount'] = amt
                        row['date'] = date_str
                        winners.append(row)
                break # Success, so break retry
            except Exception as e:
                time.sleep(2)
                continue
    except Exception as e:
        pass
    return winners

def main():
    print("Fetching first 5 pages of 2025 tenders...")
    all_links = []
    pages = list(range(1, 6))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        f_map = {ex.submit(get_page_links, p): p for p in pages}
        for i, f in enumerate(concurrent.futures.as_completed(f_map), 1):
            res = f.result()
            if res:
                all_links.extend(res)
            if i % 50 == 0:
                print(f"Scanned {i}/{len(pages)} listing pages...")
                
    # remove duplicates by inv_id
    unique_links = {d['inv_id']: d for d in all_links}.values()
    print(f"Found {len(unique_links)} finalized tenders. Fetching winners...")
    
    all_winners = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        f_map = {ex.submit(get_winner_data, item): item for item in unique_links}
        for i, f in enumerate(concurrent.futures.as_completed(f_map), 1):
            all_winners.extend(f.result())
            if i % 500 == 0:
                print(f"Fetched details for {i}/{len(unique_links)} tenders...")
                
    print(f"Found {len(all_winners)} winning bids.")
    
    if not all_winners:
        print("No winners parsed!")
        return
        
    df = pd.DataFrame(all_winners)
    # Filter out invalid company names
    df['company'] = df['company'].str.strip()
    df = df[~df['company'].str.match(r'^\d+\s*$')]
    
    df.to_csv("all_2024_winners_raw.csv", index=False)
    
    # Generate requested statistics
    total_contracts = len(df)
    total_companies = df['company'].nunique()
    total_clients = df['client'].nunique()
    
    print("\n" + "="*50)
    print("ЕРӨНХИЙ СТАТИСТИК (2024 ОН)")
    print("="*50 + "\n")
    print(f"Нийт баталгаажсан гэрээний тоо: {total_contracts}")
    print(f"Тендерт шалгарсан компаниудын тоо: {total_companies}")
    print(f"Тендер зарлагч /захиалагч/ байгууллагын тоо: {total_clients}\n")
    
    grouped = df.groupby('company').agg(
        total_won=('amount', 'sum'),
        wins=('inv_id', 'nunique')
    ).reset_index().sort_values('total_won', ascending=False)
    top = grouped.head(20)
    
    markdown_out = f"""## 2024 Оны Тендерийн Үр Дүнгийн Нэгтгэл

### Ерөнхий статистик
- **Нийт гэрээ байгуулсан тендерийн тоо:** {total_contracts}
- **Шалгарсан компаниудын тоо:** {total_companies}
- **Тендер захиалагч байгууллагуудын тоо:** {total_clients}

### Шилдэг 20 Шалгарсан компани (Борлуулалтын дүнгээр)

| Д/д | Компани | Нийт дүн (₮) | Гэрээний тоо |
| --- | --- | --- | --- |
"""
    
    for i, row in enumerate(top.itertuples(), 1):
        amt_fmt = f"{row.total_won:,.0f}"
        markdown_out += f"| {i} | {row.company} | `{amt_fmt} ₮` | {row.wins} |\n"
        
    with open("all_2024_comprehensive_stats.md", "w") as f:
        f.write(markdown_out)
        
    print("Saved statistics to all_2024_comprehensive_stats.md and raw data to all_2024_winners_raw.csv")

if __name__ == "__main__":
    main()
