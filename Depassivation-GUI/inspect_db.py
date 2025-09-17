import sqlite3
import os

# Change to the script's directory to ensure correct file paths
os.chdir(os.path.dirname(os.path.abspath(__file__)))

DB_FILE = "depassivation_history.db.old"

if not os.path.exists(DB_FILE):
    print(f"ERROR: Database file '{DB_FILE}' not found.")
else:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if tables:
            print("Tables found in the database:")
            for table in tables:
                print(f"- {table[0]}")
        else:
            print("No tables found in the database.")
        conn.close()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
