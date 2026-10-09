from curl_cffi import requests
import time

def get_total_pages(year):
    url = "https://user.tender.gov.mn/api/public/tender/bidderList"
    payload = {
        "isScore": 0,
        "isSort": 0,
        "page": 1,
        "perpage": 10,
        "sortField": "invDate",
        "sortOrder": "desc",
        "tenderType": "",
        "year": str(year)
    }
    
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, impersonate="chrome120", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            total_items = data.get("total", 0)
            return total_items
        else:
            return f"Error: {resp.status_code}"
    except Exception as e:
        return f"Error: {e}"

print(f"2023 Total items on site: {get_total_pages(2023)}")
time.sleep(2)
print(f"2024 Total items on site: {get_total_pages(2024)}")
time.sleep(2)
print(f"2025 Total items on site: {get_total_pages(2025)}")
