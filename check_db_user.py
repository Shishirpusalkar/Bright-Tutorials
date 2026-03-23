import sqlite3
import os

db_path = "backend/sql_app.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(user)")
    columns = cursor.fetchall()
    print("Columns in 'user':")
    for col in columns:
        print(col)
    conn.close()
