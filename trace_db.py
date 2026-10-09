import sqlite3
import time
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT status, count(*) FROM tender_sync_log GROUP BY status;")
print("Before:", c.fetchall())
time.sleep(10)
c.execute("SELECT status, count(*) FROM tender_sync_log GROUP BY status;")
print("After:", c.fetchall())
conn.close()
