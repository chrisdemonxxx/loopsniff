"""SQLite persistence for bot conversation history and user preferences."""

import sqlite3
import json
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("BOT_DB_PATH", "bot_data.db")

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS conversations (user_id INTEGER, role TEXT, content TEXT, timestamp REAL DEFAULT (strftime('%s','now')))")
    conn.execute("CREATE TABLE IF NOT EXISTS user_prefs (user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'en', data TEXT DEFAULT '{}')")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
    return conn

def save_message(user_id: int, role: str, content: str):
    with _get_conn() as conn:
        conn.execute("INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))

def get_history(user_id: int, limit: int = 20) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE user_id = ? ORDER BY timestamp DESC, rowid DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def set_language(user_id: int, lang: str):
    with _get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO user_prefs (user_id, language) VALUES (?, ?)", (user_id, lang))

def get_language(user_id: int) -> str:
    with _get_conn() as conn:
        row = conn.execute("SELECT language FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
    return row[0] if row else "en"

def clear_history(user_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
