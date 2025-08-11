import json
import os
import sqlite3
from datetime import datetime

PROFILES_FILE = "profiles.json"
CONFIG_FILE = "config.json"
DB_FILE = "depassivation_history.db"

class DataHandler:
    def __init__(self, app):
        self.app = app
        self.profiles = {}
        self.current_test_id = None
        self._init_database()

    def _init_database(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    duration REAL NOT NULL,
                    pass_fail_voltage REAL NOT NULL,
                    min_voltage REAL,
                    result TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    voltage REAL NOT NULL,
                    current REAL NOT NULL,
                    FOREIGN KEY (test_id) REFERENCES tests (id)
                )
            """)
            conn.commit()
        except sqlite3.Error as e:
            self.app.log_message(f"ERROR: Database error: {e}")
        finally:
            if conn:
                conn.close()

    def create_new_test(self, duration, pass_fail_voltage):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO tests (timestamp, duration, pass_fail_voltage)
                VALUES (?, ?, ?)
            """, (timestamp, duration, pass_fail_voltage))
            self.current_test_id = cursor.lastrowid
            conn.commit()
            self.app.log_message(f"INFO: Started new test with ID: {self.current_test_id}")
            return self.current_test_id
        except sqlite3.Error as e:
            self.app.log_message(f"ERROR: Could not create new test in database: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def log_data_point(self, timestamp_ms, voltage, current):
        if self.current_test_id is None:
            return
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO data_points (test_id, timestamp_ms, voltage, current)
                VALUES (?, ?, ?, ?)
            """, (self.current_test_id, timestamp_ms, voltage, current))
            conn.commit()
        except sqlite3.Error as e:
            self.app.log_message(f"ERROR: Could not log data point to database: {e}")
        finally:
            if conn:
                conn.close()

    def update_test_result(self, min_voltage, result):
        if self.current_test_id is None:
            return
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tests
                SET min_voltage = ?, result = ?
                WHERE id = ?
            """, (min_voltage, result, self.current_test_id))
            conn.commit()
        except sqlite3.Error as e:
            self.app.log_message(f"ERROR: Could not update test result in database: {e}")
        finally:
            if conn:
                conn.close()

    def get_test_data(self, test_id):
        if test_id is None:
            return []
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp_ms, voltage, current FROM data_points
                WHERE test_id = ?
                ORDER BY timestamp_ms ASC
            """, (test_id,))
            data = cursor.fetchall()
            # Convert from (timestamp_ms, V, A) to (timestamp_s, V, A) for CSV
            return [(ts / 1000.0, v, c) for ts, v, c in data]
        except sqlite3.Error as e:
            self.app.log_message(f"ERROR: Could not fetch test data from database: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def load_profiles(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f:
                    self.profiles = json.load(f)
                    self.app.log_message(f"INFO: Loaded {len(self.profiles)} profiles from {PROFILES_FILE}")
            except (json.JSONDecodeError, IOError) as e:
                self.app.log_message(f"ERROR: Could not load profiles file: {e}")
                self.profiles = {}
        else:
            self.profiles = {}
            self.app.log_message(f"INFO: No profiles file found. Starting with empty profiles.")
        return self.profiles

    def save_profiles(self):
        try:
            with open(PROFILES_FILE, 'w') as f:
                json.dump(self.profiles, f, indent=4)
            self.app.log_message("INFO: Profiles saved successfully.")
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
            "duration": self.app.duration_var.get(),
            "pass_fail_voltage": self.app.pass_fail_voltage_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            self.app.log_message(f"ERROR: Could not save config file: {e}")
