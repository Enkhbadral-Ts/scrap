import sqlite3
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT count(*) FROM tender_sync_log WHERE status='EMPTY' AND synced_at > date('now')")
print("EMPTY today:", c.fetchone()[0])
conn.close()
