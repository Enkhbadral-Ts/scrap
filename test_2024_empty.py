import sqlite3
from curl_cffi import requests
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT inv_id FROM tender_sync_log WHERE year=2024 AND status='EMPTY' LIMIT 1")
row = c.fetchone()
conn.close()

inv_id = str(row[0])
s = requests.Session(impersonate="chrome120")
r = s.get(f"https://user.tender.gov.mn/mn/result/detail/{inv_id}", timeout=10)
print("status:", r.status_code)
is_cf = (
    "cf-mitigated" in r.headers or
    "challenge-platform" in r.text.lower() or
    "__cf" in r.text.lower()
)
print("is_cf:", is_cf)
