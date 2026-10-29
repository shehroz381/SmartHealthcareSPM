import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "healthcare.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Database tables:", tables)

cursor.execute("SELECT * FROM projects")
rows = cursor.fetchall()

print("\nSaved projects:")
for row in rows:
    print(row)

print("\nTotal projects saved:", len(rows))

# Additional summary of all modules
table_names = [t[0] for t in tables if t[0] not in ('sqlite_sequence',)]
print("\n--- Module Summary ---")
for tname in table_names:
    try:
        cnt = cursor.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        print(f"Table '{tname}': {cnt} record(s)")
    except Exception as e:
        print(f"Table '{tname}': {e}")

conn.close()
