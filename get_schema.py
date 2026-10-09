import sqlite3
conn = sqlite3.connect("/home/maaraa/tender_harvester/tender_bidders.db")
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tender_sync_log'")
print(c.fetchone()[0])
conn.close()
