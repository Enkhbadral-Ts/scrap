import sqlite3
import json
from curl_cffi import requests
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT inv_id FROM tender_sync_log")
processed = {row[0] for row in c.fetchall()}
conn.close()

with open("/home/maaraa/tender_harvester/tenders_2024_links_cache.json") as f:
    tenders = json.load(f)

pending = [t for t in tenders if str(t["inv_id"]) not in processed]
if pending:
    t = pending[0]
    inv_id = str(t["inv_id"])
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
    print("inv_id:", inv_id)
    print("status:", r.status_code)
    print("text:", r.text)
