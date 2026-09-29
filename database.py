import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="database/license_plates.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_database()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_database(self):
        try:
            with self._get_connection() as conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS authorized_plates (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    plate_text TEXT UNIQUE,
                                    owner_name TEXT,
                                    is_active BOOLEAN DEFAULT 1,
                                    added_by TEXT DEFAULT 'ADMIN'
                                )''')

                conn.execute('''CREATE TABLE IF NOT EXISTS access_log (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                                    plate_text TEXT,
                                    access_type TEXT,
                                    image_path TEXT,
                                    action_by TEXT DEFAULT 'SYSTEM'
                                )''')

                conn.execute('''CREATE TABLE IF NOT EXISTS app_users (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    username TEXT UNIQUE,
                                    password TEXT,
                                    role TEXT,
                                    is_banned BOOLEAN DEFAULT 0
                                )''')

                conn.execute("INSERT OR IGNORE INTO app_users (username, password, role) VALUES ('admin', 'admin123', 'ADMIN')")
                conn.commit()
        except Exception as e:
            logger.error(f"Eroare initializare DB: {e}")

    def _clean_plate(self, text):
        if not text:
            return ""
        return text.upper().replace(" ", "").replace("-", "").strip()

    def add_plate(self, plate_text, owner_name, added_by="ADMIN"):
        clean_plate = self._clean_plate(plate_text)
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO authorized_plates (plate_text, owner_name, added_by) VALUES (?, ?, ?)",
                             (clean_plate, owner_name, added_by))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Eroare DB add: {e}")
            return False

    def update_plate(self, old_plate, new_plate, new_owner):
        old_p = self._clean_plate(old_plate)
        new_p = self._clean_plate(new_plate)
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE authorized_plates SET plate_text = ?, owner_name = ? WHERE plate_text = ?",
                             (new_p, new_owner, old_p))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Eroare DB update: {e}")
            return False

    def delete_plate(self, plate_text):
        clean_plate = self._clean_plate(plate_text)
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM authorized_plates WHERE plate_text = ?", (clean_plate,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Eroare DB delete: {e}")
            return False

    def get_all_plates(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT plate_text, owner_name, added_by FROM authorized_plates ORDER BY owner_name ASC")
                return [{"plate": row[0], "owner": row[1], "added_by": row[2]} for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Eroare DB get_all: {e}")
            return []

    def is_authorized(self, plate_text):
        clean_plate = self._clean_plate(plate_text)
        if not clean_plate: return False
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT owner_name FROM authorized_plates WHERE plate_text = ? AND is_active = 1", (clean_plate,))
                return cursor.fetchone() is not None
        except Exception as e:
            return False

    def is_user_banned(self, username):
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT is_banned FROM app_users WHERE username = ?", (username.strip(),))
                res = cursor.fetchone()
                return True if (res and res[0] == 1) else False
        except:
            return False

    def toggle_user_ban(self, username, ban_status):
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE app_users SET is_banned = ? WHERE username = ?", (int(ban_status), username.strip()))
                conn.commit()
            return True
        except:
            return False

    def log_access(self, plate_text, access_type, image_path=None, action_by="SYSTEM"):
        clean_plate = self._clean_plate(plate_text) if plate_text else "MANUAL_TRIGGER"
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT INTO access_log (plate_text, access_type, image_path, action_by) VALUES (?, ?, ?, ?)",
                             (clean_plate, access_type, image_path, action_by))
                conn.commit()
        except Exception as e:
            logger.error(f"Eroare DB log: {e}")

    def get_logs(self, limit=10000):
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT timestamp, plate_text, access_type, image_path, action_by FROM access_log ORDER BY id DESC LIMIT ?", (limit,))
                return [{"time": row[0], "plate": row[1], "status": row[2], "image_path": row[3], "action_by": row[4]} for row in cursor.fetchall()]
        except Exception as e:
            return []

    def get_all_users(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT username, role, is_banned FROM app_users ORDER BY username ASC")
                return [{"username": row[0], "role": row[1], "is_banned": row[2]} for row in cursor.fetchall()]
        except Exception as e:
            return []

    def add_user(self, username, password, role="USER"):
        if not username or not password: return False
        role = "ADMIN" if role.strip().upper() == "ADMIN" else "USER"
        try:
            with self._get_connection() as conn:
                conn.execute("INSERT OR REPLACE INTO app_users (username, password, role, is_banned) VALUES (?, ?, ?, 0)",
                             (username.strip(), password.strip(), role))
                conn.commit()
            return True
        except Exception as e:
            return False

    def delete_user(self, username):
        clean_username = username.strip()
        if clean_username.lower() == 'admin': return False
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM app_users WHERE username = ?", (clean_username,))
                conn.commit()
            return True
        except Exception as e:
            return False

    def verify_login(self, username, password):
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT role, is_banned FROM app_users WHERE username = ? AND password = ?", (username.strip(), password.strip()))
                result = cursor.fetchone()
                if result:
                    if result[1] == 1:
                        return "BANNED"
                    return result[0]
                return None
        except Exception as e:
            return None