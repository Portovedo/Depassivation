import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

PROFILES_FILE = "profiles.json"
CONFIG_FILE = "config.json"
DB_FILE = "depassivation_history.db"

class DataHandler:
    def __init__(self, app):
        self.app = app
        self.profiles = {}
        self.current_test_id = None

    @contextmanager
    def _get_db_cursor(self, commit=False, row_factory=None):
        """A context manager for safely handling database connections."""
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            if row_factory:
                conn.row_factory = row_factory
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            yield cursor
            if commit:
                conn.commit()
        except sqlite3.Error as e:
            self.app.log_message(f"ERROR: Database error: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def _init_database(self):
        with self._get_db_cursor(commit=True) as cursor:
            # --- Create batteries table for tracking individual batteries ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batteries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            """)

            # --- Create tests table if it doesn't exist (for fresh installs) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    battery_id INTEGER,
                    timestamp TEXT NOT NULL,
                    duration REAL NOT NULL,
                    pass_fail_voltage REAL NOT NULL,
                    min_voltage REAL,
                    result TEXT,
                    FOREIGN KEY (battery_id) REFERENCES batteries (id) ON DELETE SET NULL
                )
            """)

            # --- Perform robust migration if old schema is detected ---
            cursor.execute("PRAGMA table_info(tests)")
            columns = [column[1] for column in cursor.fetchall()]

            # Migration for battery_id
            if 'battery_id' not in columns:
                self.app.log_message("INFO: Old database schema detected. Migrating 'tests' table for battery_id...")
                # ... (migration code for battery_id remains the same)

            # Migration for new metrics
            if 'max_current' not in columns:
                self.app.log_message("INFO: Migrating 'tests' table to add new metrics columns...")
                cursor.execute("ALTER TABLE tests ADD COLUMN max_current REAL")
                cursor.execute("ALTER TABLE tests ADD COLUMN resistance REAL")
                cursor.execute("ALTER TABLE tests ADD COLUMN power REAL")
                self.app.log_message("INFO: New metrics columns added successfully.")

            # --- Create data_points table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    voltage REAL NOT NULL,
                    current REAL NOT NULL,
                    FOREIGN KEY (test_id) REFERENCES tests (id) ON DELETE CASCADE
                )
            """)

    # --- NEW Battery Management Methods ---
    def create_battery(self, name):
        """Creates a new battery profile. Returns the ID of the new battery or None on failure."""
        if not name:
            self.app.log_message("ERROR: Battery name cannot be empty.")
            return None
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = "INSERT INTO batteries (name, created_at) VALUES (?, ?)"
        try:
            with self._get_db_cursor(commit=True) as cursor:
                cursor.execute(sql, (name, timestamp))
                self.app.log_message(f"INFO: Registered new battery: {name}")
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            self.app.log_message(f"ERROR: Battery with name '{name}' already exists.")
            return None

    def get_all_batteries(self):
        """Returns a list of all batteries, ordered by name."""
        sql = "SELECT id, name FROM batteries ORDER BY name ASC"
        with self._get_db_cursor(row_factory=sqlite3.Row) as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
        return []

    # --- MODIFIED Test Management Methods ---
    def create_new_test(self, battery_id, duration, pass_fail_voltage):
        """Creates a new test record linked to a specific battery."""
        if battery_id is None:
            self.app.log_message("ERROR: Cannot create test without a selected battery.")
            return None

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = "INSERT INTO tests (battery_id, timestamp, duration, pass_fail_voltage) VALUES (?, ?, ?, ?)"

        with self._get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (battery_id, timestamp, duration, pass_fail_voltage))
            self.current_test_id = cursor.lastrowid
            self.app.log_message(f"INFO: Started new test (ID: {self.current_test_id}) for battery ID: {battery_id}")
            return self.current_test_id
        return None

    def log_data_point(self, timestamp_ms, voltage, current):
        if self.current_test_id is None:
            return
        sql = "INSERT INTO data_points (test_id, timestamp_ms, voltage, current) VALUES (?, ?, ?, ?)"
        with self._get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (self.current_test_id, timestamp_ms, voltage, current))

    def update_test_result(self, min_voltage, max_current, power, resistance, result):
        if self.current_test_id is None:
            return
        sql = """UPDATE tests
                 SET min_voltage = ?, max_current = ?, power = ?, resistance = ?, result = ?
                 WHERE id = ?"""
        with self._get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (min_voltage, max_current, power, resistance, result, self.current_test_id))

    def get_test_data(self, test_id):
        if test_id is None: return []
        sql = "SELECT timestamp_ms, voltage, current FROM data_points WHERE test_id = ? ORDER BY timestamp_ms ASC"
        with self._get_db_cursor() as cursor:
            cursor.execute(sql, (test_id,))
            data = cursor.fetchall()
            return [(ts / 1000.0, v, c) for ts, v, c in data]
        return []

    def get_tests_for_battery(self, battery_id):
        """Fetches all tests for a specific battery ID."""
        if battery_id is None: return []
        sql = "SELECT id, timestamp, result, duration FROM tests WHERE battery_id = ? ORDER BY timestamp DESC"
        with self._get_db_cursor() as cursor:
            cursor.execute(sql, (battery_id,))
            return cursor.fetchall()
        return []

    def get_uncategorized_tests(self):
        """Fetches all tests that are not linked to any battery."""
        sql = "SELECT id, timestamp, result, duration FROM tests WHERE battery_id IS NULL ORDER BY timestamp DESC"
        with self._get_db_cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
        return []

    def get_test_summary(self, test_id):
        if test_id is None: return None
        sql = "SELECT * FROM tests WHERE id = ?"
        with self._get_db_cursor(row_factory=sqlite3.Row) as cursor:
            cursor.execute(sql, (test_id,))
            return cursor.fetchone()
        return None

    def delete_test(self, test_id):
        if test_id is None: return False
        sql = "DELETE FROM tests WHERE id = ?"
        with self._get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (test_id,))
            return cursor.rowcount > 0
        return False

    def delete_battery(self, battery_id):
        if battery_id is None: return False
        # 'ON DELETE SET NULL' on the tests table will handle disassociating tests.
        sql = "DELETE FROM batteries WHERE id = ?"
        with self._get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (battery_id,))
            self.app.log_message(f"INFO: Deleted battery ID: {battery_id}. Associated tests are now uncategorized.")
            return cursor.rowcount > 0
        return False

    # --- Unchanged Profile and Config Methods ---
    def load_profiles(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f:
                    self.profiles = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.app.log_message(f"ERROR: Could not load profiles file: {e}")
                self.profiles = {}
        else:
            self.profiles = {}
        return self.profiles

    def save_profiles(self):
        try:
            with open(PROFILES_FILE, 'w') as f:
                json.dump(self.profiles, f, indent=4)
        except IOError as e:
            self.app.log_message(f"ERROR: Could not save profiles file: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save_config(self):
        config = {
            "geometry": self.app.root.geometry(),
            "last_port": self.app.selected_port_var.get(),
            "pass_fail_voltage": self.app.pass_fail_voltage_var.get(),
            "baseline_duration": self.app.baseline_duration_var.get(),
            "depassivation_duration": self.app.depassivation_duration_var.get(),
            "rest_duration": self.app.rest_duration_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            self.app.log_message(f"ERROR: Could not save config file: {e}")
