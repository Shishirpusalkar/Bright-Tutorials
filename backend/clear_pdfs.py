import sqlite3
import os
import glob

db_path = "sql_app.db"
upload_dir = "static/uploads/tests"
temp_dir = "static/uploads/temp"

if not os.path.exists(db_path):
    print(f"Error: Database {db_path} not found.")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- Database Cleanup ---")

    # 1. Clear Gemini Cache
    cursor.execute("DELETE FROM parsed_paper_cache;")
    print(f"Cleared Gemini cache (parsed_paper_cache).")

    # 2. Clear all test-related data
    cursor.execute("DELETE FROM attempt_answers;")
    cursor.execute("DELETE FROM attempts;")
    cursor.execute("DELETE FROM questions;")
    cursor.execute("DELETE FROM tests;")

    print("Wiped all tests, questions, attempts, and attempt_answers.")

    conn.commit()
    conn.close()

    print("\n--- Filesystem Cleanup ---")

    # 3. Delete physical PDF files
    if os.path.exists(upload_dir):
        pdf_pattern = os.path.join(upload_dir, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)

        deleted_count = 0
        for pdf_file in pdf_files:
            try:
                os.remove(pdf_file)
                deleted_count += 1
            except Exception as fe:
                print(f"  Error deleting {pdf_file}: {fe}")

        print(f"Deleted {deleted_count} physical PDF files from {upload_dir}.")
    else:
        print(f"Upload directory {upload_dir} does not exist.")

    if os.path.exists(temp_dir):
        pdf_pattern = os.path.join(temp_dir, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)

        deleted_count = 0
        for pdf_file in pdf_files:
            try:
                os.remove(pdf_file)
                deleted_count += 1
            except Exception as fe:
                print(f"  Error deleting {pdf_file}: {fe}")

        print(f"Deleted {deleted_count} physical PDF files from {temp_dir}.")
    else:
        print(f"Temp directory {temp_dir} does not exist.")

    print("\nCleanup completed successfully.")

except Exception as e:
    print(f"Fatal error during cleanup: {e}")
    exit(1)
