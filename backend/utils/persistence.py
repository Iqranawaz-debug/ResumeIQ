"""Optional SQLite persistence for per-user working data.

Disabled unless RESUMEIQ_DB_PATH is set: by default ResumeIQ keeps working data
in memory only. When enabled, each user's extracted resume, latest analysis,
history, version snapshots and recruiter workspaces are stored as one JSON
document, written on change and reloaded at startup. Uploaded file bytes and
sessions are never stored. Entries older than the retention period are dropped
on load, and deleting data removes the row.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._db() as db:
                db.execute('CREATE TABLE IF NOT EXISTS user_data ('
                           'username TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL NOT NULL)')

    @property
    def enabled(self):
        return self.path is not None

    @contextmanager
    def _db(self):
        # sqlite3's own context manager commits but does not close the connection.
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_user(self, username, data):
        if not self.enabled:
            return
        if not any(data.values()):
            return self.delete_user(username)
        payload = json.dumps(data, default=list)
        with self._db() as db:
            db.execute('INSERT INTO user_data (username, payload, updated_at) VALUES (?, ?, ?) '
                       'ON CONFLICT(username) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at',
                       (username, payload, time.time()))

    def delete_user(self, username):
        if self.enabled:
            with self._db() as db:
                db.execute('DELETE FROM user_data WHERE username = ?', (username,))

    def load_all(self, max_age_seconds):
        """Return {username: (data, seconds_since_update)} and drop expired rows."""
        if not self.enabled:
            return {}
        now = time.time()
        with self._db() as db:
            db.execute('DELETE FROM user_data WHERE updated_at < ?', (now - max_age_seconds,))
            rows = db.execute('SELECT username, payload, updated_at FROM user_data').fetchall()
        result = {}
        for username, payload, updated_at in rows:
            try:
                result[username] = (json.loads(payload), max(0.0, now - updated_at))
            except json.JSONDecodeError:
                continue  # A damaged row is skipped, never fatal.
        return result


def from_environment():
    return Store(os.environ.get('RESUMEIQ_DB_PATH', '').strip() or None)
