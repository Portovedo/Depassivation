import sqlite3
import os
import sys
from datetime import datetime

# Change to the script's directory to ensure correct file paths
os.chdir(os.path.dirname(os.path.abspath(__file__)))

OLD_DB_FILE = "depassivation_history.db.old"
NEW_DB_FILE = "depassivation_history.db"

def migrate_data():
    """Migrates data from the old database schema to the new one."""
    if not os.path.exists(OLD_DB_FILE):
        print(f"INFO: Old database file '{OLD_DB_FILE}' not found. Nothing to migrate.")
        return

    print(f"INFO: Starting database migration from '{OLD_DB_FILE}' to '{NEW_DB_FILE}'...")

    old_conn = None
    new_conn = None
    migration_successful = False

    try:
        # Connect directly to the databases
        print(f"INFO: Connecting to OLD database: {OLD_DB_FILE}")
        old_conn = sqlite3.connect(OLD_DB_FILE)
        old_conn.row_factory = sqlite3.Row
        old_cursor = old_conn.cursor()

        print(f"INFO: Connecting to NEW database: {NEW_DB_FILE}")
        new_conn = sqlite3.connect(NEW_DB_FILE)
        new_cursor = new_conn.cursor()

        # Check if the 'tests' table exists in the old DB
        print("INFO: Checking for 'tests' table in old database...")
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tests'")
        if old_cursor.fetchone() is None:
            print("ERROR: 'tests' table not found in the old database. Aborting migration.")
            return
        print("INFO: 'tests' table found. Proceeding with migration.")

        # 1. Fetch all tests from the old database
        print("INFO: Fetching tests from old database...")
        old_cursor.execute("SELECT * FROM tests ORDER BY id ASC")
        old_tests = old_cursor.fetchall()

        if not old_tests:
            print("INFO: Old database has no tests to migrate.")
            migration_successful = True
            return

        migrated_count = 0
        for old_test in old_tests:
            new_cursor.execute(
                "INSERT INTO tests (battery_id, timestamp, profile_name) VALUES (?, ?, ?)",
                (old_test['battery_id'], old_test['timestamp'], None)
            )
            new_test_id = new_cursor.lastrowid

            cycle_type = "Unknown"
            if old_test['result']:
                if "Baseline" in old_test['result']: cycle_type = "Baseline"
                elif "Depassivation" in old_test['result']: cycle_type = "Depassivation"
                elif "Check" in old_test['result']: cycle_type = "Check"

            new_cursor.execute(
                """INSERT INTO cycles (test_id, cycle_type, timestamp, duration, pass_fail_voltage,
                                     min_voltage, max_current, power, resistance, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_test_id, cycle_type, old_test['timestamp'], old_test['duration'],
                    old_test['pass_fail_voltage'], old_test['min_voltage'], old_test.get('max_current'),
                    old_test.get('power'), old_test.get('resistance'), old_test['result']
                )
            )
            new_cycle_id = new_cursor.lastrowid

            old_cursor.execute("SELECT * FROM data_points WHERE test_id = ?", (old_test['id'],))
            old_data_points = old_cursor.fetchall()

            for dp in old_data_points:
                new_cursor.execute(
                    "INSERT INTO readings (cycle_id, timestamp_ms, voltage, current) VALUES (?, ?, ?, ?)",
                    (new_cycle_id, dp['timestamp_ms'], dp['voltage'], dp['current'])
                )
            migrated_count += 1
            print(f"  - Migrated old test ID {old_test['id']} to new test ID {new_test_id} with cycle ID {new_cycle_id}")

        new_conn.commit()
        migration_successful = True
        print(f"\nINFO: Successfully migrated {migrated_count} test(s).")

    except sqlite3.Error as e:
        print(f"ERROR: An error occurred during migration: {e}")
        if new_conn:
            new_conn.rollback()
    finally:
        if old_conn:
            old_conn.close()
        if new_conn:
            new_conn.close()

    if migration_successful:
        try:
            final_db_name = f"depassivation_history_{datetime.now().strftime('%Y%m%d%H%M%S')}.db.migrated"
            os.rename(OLD_DB_FILE, final_db_name)
            print(f"INFO: Renamed old database to '{final_db_name}'")
        except OSError as e:
            print(f"ERROR: Could not rename old database file: {e}")

if __name__ == "__main__":
    migrate_data()
