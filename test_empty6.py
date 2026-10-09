import sqlite3, json, os
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT inv_id FROM tender_sync_log")
processed = {str(row[0]) for row in c.fetchall()}
conn.close()

for y in [2024, 2025, 2023, 2022, 2021]:
    with open(f"/home/maaraa/tender_harvester/tenders_{y}_links_cache.json") as f:
        tenders = json.load(f)
    pending = [t for t in tenders if str(t["inv_id"]) not in processed]
    print(f"Year {y}: {len(pending)} pending tenders")
