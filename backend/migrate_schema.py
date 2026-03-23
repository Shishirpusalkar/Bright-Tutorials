import sqlite3

db_path = "sql_app.db"


def add_column(cursor, table, column, type):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type};")
        print(f"Added column {column} to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"Column {column} already exists in {table}")
        else:
            print(f"Error adding column {column}: {e}")


try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add page_number to questions
    add_column(cursor, "questions", "page_number", "INTEGER")

    # Add visual_bbox to questions
    add_column(cursor, "questions", "visual_bbox", "JSON")

    # Add is_symmetrical to tests
    add_column(cursor, "tests", "is_symmetrical", "BOOLEAN")

    # Add symmetry_message to tests
    add_column(cursor, "tests", "symmetry_message", "TEXT")

    conn.commit()
    conn.close()
    print("Schema update complete.")
except Exception as e:
    print(f"Failed to update schema: {e}")
