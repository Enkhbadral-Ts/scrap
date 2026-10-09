import sqlite3, json, os
from curl_cffi import requests
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT inv_id FROM tender_sync_log")
processed = {str(row[0]) for row in c.fetchall()}
conn.close()

with open(f"/home/maaraa/tender_harvester/tenders_2024_links_cache.json") as f:
    tenders = json.load(f)
pending = [t for t in tenders if str(t["inv_id"]) not in processed]
for t in pending[:5]:
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
    print("inv_id:", inv_id, "status:", r.status_code)
    try:
        print("data length:", len(r.json().get("data", [])))
    except:
        print("Not json")
