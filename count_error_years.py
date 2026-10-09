import sqlite3
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT year, status, count(*) FROM tender_sync_log GROUP BY year, status;")
for row in c.fetchall(): print(row)
conn.close()
