import json, sqlite3
from curl_cffi import requests

def get_processed():
    conn = sqlite3.connect("tender_bidders.db")
    c = conn.cursor()
    c.execute("SELECT inv_id FROM tender_sync_log")
    ids = {row[0] for row in c.fetchall()}
    conn.close()
    return ids

processed = get_processed()
with open("tenders_2024_links_cache.json") as f:
    tenders = json.load(f)

pending = [t for t in tenders if str(t["inv_id"]) not in processed]
if not pending:
    print("No pending tenders")
    exit()

t = pending[0]
inv_id = str(t["inv_id"])
print("Testing inv_id:", inv_id)

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
print("Status:", r.status_code)
try:
    data = r.json()
    print("Data:", len(data.get("data", [])))
    print("Raw JSON:", str(data)[:500])
except Exception as e:
    print("Not JSON:", r.text[:500])
