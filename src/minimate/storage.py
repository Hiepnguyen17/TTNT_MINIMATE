"""Local SQLite storage. Callers own transaction boundaries."""
import sqlite3
from pathlib import Path


class Storage:
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY CHECK(id=1),
                state TEXT NOT NULL, duration_seconds INTEGER,
                started_at TEXT, ends_at TEXT);
            INSERT OR IGNORE INTO sessions(id,state) VALUES(1,'idle');
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL,
                input_text TEXT NOT NULL, intent TEXT NOT NULL,
                confidence REAL, action TEXT NOT NULL, response_text TEXT NOT NULL,
                device_state TEXT NOT NULL, session_state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY, content TEXT NOT NULL,
                due_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'saved');
        """)

    def session(self):
        return dict(self.connection.execute("SELECT * FROM sessions WHERE id=1").fetchone())

    def set_session(self, state, duration=None, started=None, ends=None):
        self.connection.execute(
            "UPDATE sessions SET state=?,duration_seconds=?,started_at=?,ends_at=? WHERE id=1",
            (state, duration, started, ends))

    def add_command(self, text, response, now):
        self.connection.execute(
            "INSERT INTO commands(created_at,input_text,intent,confidence,action,response_text,device_state,session_state) VALUES(?,?,?,?,?,?,?,?)",
            (now, text, response['intent'], response['confidence'], response['action'],
             response['text'], response['device_state'], response['session_state']))

    def last_response(self):
        row = self.connection.execute("SELECT response_text FROM commands ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def add_reminder(self, content, due_at):
        self.connection.execute("INSERT INTO reminders(content,due_at) VALUES(?,?)", (content, due_at))

    def reminders(self):
        return [dict(row) for row in self.connection.execute("SELECT * FROM reminders ORDER BY due_at,id")]

    def close(self):
        self.connection.close()
