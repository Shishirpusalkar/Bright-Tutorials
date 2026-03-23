import sqlite3
import os

db_path = "sql_app.db"

if not os.path.exists(db_path):
    print(f"Error: Database {db_path} not found.")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, question_paper_url FROM tests;")
    rows = cursor.fetchall()

    print(f"Total tests in database: {len(rows)}")
    for row in rows:
        print(f"ID: {row[0]} | Title: {row[1]} | PDF URL: {row[2]}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
