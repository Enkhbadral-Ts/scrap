import sqlite3
import json
from curl_cffi import requests

conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT inv_id FROM tender_sync_log WHERE year=2025 AND status='ERROR' LIMIT 1")
row = c.fetchone()
conn.close()

if not row:
    print("No ERROR tender in 2025")
    exit()

inv_id = str(row[0])
print(f"Testing inv_id: {inv_id}")

url = "https://user.tender.gov.mn/mn/result/detail/bidderList"
payload = {"invitationId": inv_id, "groupBy": "tender"}
headers = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://user.tender.gov.mn',
    'Referer': f'https://user.tender.gov.mn/mn/result/detail?invitationId={inv_id}',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'X-Requested-With': 'XMLHttpRequest'
}
s = requests.Session(impersonate="chrome120")
r = s.post(url, data=payload, headers=headers)
print("status:", r.status_code)
try:
    data = r.json()
    print("bidders_count:", len(data.get("data", [])))
except Exception as e:
    print("not json")
