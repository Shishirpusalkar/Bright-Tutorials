import sqlite3

conn = sqlite3.connect("sql_app.db")
cursor = conn.cursor()
cursor.execute("UPDATE alembic_version SET version_num='81313a31af60'")
conn.commit()
print("Updated alembic_version to 81313a31af60")
conn.close()
