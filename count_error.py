import sqlite3
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT status, count(*) FROM tender_sync_log GROUP BY status;")
print(c.fetchall())
conn.close()
