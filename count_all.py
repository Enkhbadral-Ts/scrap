import sqlite3
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT count(*) FROM tender_bidders")
bidders = c.fetchone()[0]
c.execute("SELECT status, count(*) FROM tender_sync_log GROUP BY status")
logs = c.fetchall()
print(f"Bidders: {bidders}")
print(f"Logs: {logs}")
conn.close()
