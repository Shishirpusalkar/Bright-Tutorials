import sqlite3
import os

db_path = "sql_app.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(0)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    tables = cursor.fetchall()

    print("Clearing tables...")
    for table_name in tables:
        name = table_name[0]
        if name == "alembic_version":
            continue  # Keep migration history
        print(f"  Clearing {name}...")
        cursor.execute(f"DELETE FROM {name};")

    conn.commit()
    conn.close()
    print("Database cleared successfully (Migration history preserved).")
except Exception as e:
    print(f"Error clearing database: {e}")
    exit(1)
