"""SQLite persistence for bot conversation history and user preferences."""

import sqlite3
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("BOT_DB_PATH", "bot_data.db")

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS conversations (user_id INTEGER, role TEXT, content TEXT, timestamp REAL DEFAULT (strftime('%s','now')))")
    conn.execute("CREATE TABLE IF NOT EXISTS user_prefs (user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'en', data TEXT DEFAULT '{}')")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
    conn.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at)")
    conn.execute("CREATE TABLE IF NOT EXISTS user_visits (user_id INTEGER NOT NULL, visit_date TEXT NOT NULL, PRIMARY KEY (user_id, visit_date))")
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

def get_message_count(user_id: int) -> int:
    """Return total number of messages exchanged with this user."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else 0


def clear_history(user_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))


# ── Lead persistence ─────────────────────────────────────────────────────


def save_lead(user_id: int, lead_data: dict):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO leads (user_id, data, created_at) VALUES (?, ?, ?)",
            (user_id, json.dumps(lead_data), datetime.now().isoformat()),
        )


def get_leads(user_id: int = None, limit: int = 50) -> list:
    with _get_conn() as conn:
        if user_id:
            rows = conn.execute(
                "SELECT data, created_at FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data, created_at FROM leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [{"data": json.loads(r[0]), "created_at": r[1]} for r in rows]


def get_leads_count() -> int:
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM leads").fetchone()
    return row[0] if row else 0


def get_leads_today_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()
    return row[0] if row else 0


# ── User visit persistence ───────────────────────────────────────────────


def record_user_visit(user_id: int):
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_visits (user_id, visit_date) VALUES (?, ?)",
            (user_id, datetime.now().strftime("%Y-%m-%d")),
        )


def get_total_users() -> int:
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_visits").fetchone()
    return row[0] if row else 0


def get_today_users() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_visits WHERE visit_date = ?",
            (today,),
        ).fetchone()
    return row[0] if row else 0
