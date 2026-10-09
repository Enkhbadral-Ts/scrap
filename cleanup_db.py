import sqlite3
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("DELETE FROM tender_sync_log WHERE status IN ('EMPTY', 'ERROR');")
print("Deleted rows:", c.rowcount)
conn.commit()
conn.close()
