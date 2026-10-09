import sqlite3
from curl_cffi import requests
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT inv_id FROM tender_sync_log WHERE year=2025 AND status='EMPTY' ORDER BY synced_at DESC LIMIT 1")
row = c.fetchone()
conn.close()

if row:
    inv_id = str(row[0])
    s = requests.Session(impersonate="chrome120")
    base_resp = s.get(f"https://user.tender.gov.mn/mn/result/detail/{inv_id}", timeout=10)
    print("inv_id:", inv_id)
    print("status:", base_resp.status_code)
    print("text:", base_resp.text[:500])
