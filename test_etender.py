import csv
from curl_cffi import requests
from bs4 import BeautifulSoup

def main():
    companies = {}
    for p in range(1, 9):
        url = f'https://www.e-tender.mn/companies_page_{p}/' if p > 1 else 'https://www.e-tender.mn/companies/'
        r = requests.get(url, impersonate='chrome120')
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table')
        if not table: continue
        rows = table.find_all('tr')[1:]
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 3:
                name = tds[1].text.strip()
                reg = tds[2].text.strip()
                companies[name] = reg
                
    with open('etender_registry.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['company', 'registry_number'])
        for name, reg in companies.items():
            writer.writerow([name, reg])
            
    print(f"Scraped {len(companies)} companies from e-tender.mn.")

if __name__ == '__main__':
    main()
