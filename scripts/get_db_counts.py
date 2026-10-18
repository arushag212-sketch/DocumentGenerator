import sqlite3
from pathlib import Path

db_path = Path("data/clubdocs.db")
if not db_path.exists():
    print(f"Error: {db_path} does not exist")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]

print("=== Clean Seed Row Counts for data/clubdocs.db ===")
for t in tables:
    count = cur.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
    print(f"{t}: {count}")
