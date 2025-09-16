# db/peek.py
import sqlite3
from config.config_loader import CONFIG
p = CONFIG['database']['path']
conn = sqlite3.connect(p)
cur = conn.cursor()
for row in cur.execute("SELECT id, name, email, filename, skills_json, location, experience, text_hash FROM candidates;"):
    print(row)
conn.close()

