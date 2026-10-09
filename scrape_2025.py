import requests
from bs4 import BeautifulSoup
import json
import re
import concurrent.futures
import pandas as pd
import time

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
                break
            except Exception as e:
                time.sleep(2)
                continue
    except Exception as e:
        pass
    return winners

def main():
    print("Fetching ALL pages of 2025 tenders...")
    all_links = []
    pages = list(range(1, 1000))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        f_map = {ex.submit(get_page_links, p): p for p in pages}
        for i, f in enumerate(concurrent.futures.as_completed(f_map), 1):
            res = f.result()
            if res:
                all_links.extend(res)
            if i % 50 == 0:
                print(f"Scanned {i}/{len(pages)} listing pages...")
                
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
    df['company'] = df['company'].str.strip()
    df = df[~df['company'].str.match(r'^\d+\s*$')]
    
    # Save as EXCEL-ready UTF-8 BOM CSV
    df.to_csv("all_2025_winners_excel_zoriulalt.csv", index=False, encoding='utf-8-sig')
    
    total_contracts = len(df)
    total_companies = df['company'].nunique()
    total_clients = df['client'].nunique()
    
    print("\n" + "="*50)
    print("ЕРӨНХИЙ СТАТИСТИК (2025 ОН)")
    print("="*50 + "\n")
    print(f"Нийт баталгаажсан гэрээний тоо: {total_contracts}")
    print(f"Тендерт шалгарсан компаниудын тоо: {total_companies}")
    print(f"Тендер зарлагч /захиалагч/ байгууллагын тоо: {total_clients}\n")
    
    grouped = df.groupby('company').agg(
        wins=('inv_id', 'nunique'),
        total_won=('amount', 'sum')
    ).reset_index().sort_values(['total_won'], ascending=False)
    
    top = grouped.head(20)
    
    markdown_out = f"""## Хамгийн өндөр дүнгээр тендер авсан Топ 20 Компани (2025 Он)
- **Нийт гэрээ байгуулсан байгууллагын тоо:** {total_contracts}
- **Тендерт шалгарсан компаниудын тоо:** {total_companies}

| Д/д | Компани | Гэрээний тоо | Нийт дүн (₮) |
| --- | --- | --- | --- |
"""
    for i, row in enumerate(top.itertuples(), 1):
        markdown_out += f"| {i} | {row.company} | {row.wins} | `{row.total_won:,.0f} ₮` |\n"
        
    with open("top20_2025_by_amount.md", "w") as f:
        f.write(markdown_out)

if __name__ == "__main__":
    main()
