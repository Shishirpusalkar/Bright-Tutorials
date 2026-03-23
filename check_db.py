import sqlite3
import os

db_path = "backend/sql_app.db"
print(f"Checking DB at: {os.path.abspath(db_path)}")
print(f"File exists: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")

    if ("questions",) in [t for t in tables]:
        cursor.execute("PRAGMA table_info(questions)")
        columns = cursor.fetchall()
        print("Columns in 'questions':")
        for col in columns:
            print(col)
    else:
        print("Table 'questions' not found.")
    conn.close()
