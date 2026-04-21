"""SQLite-backed conversation logger for @kliqboost_bot."""

import os
import time
from pathlib import Path
from typing import Optional

import aiosqlite

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "conversations.db"


async def _get_db() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    db = await _get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                first_seen REAL NOT NULL,
                last_seen  REAL NOT NULL,
                msg_count  INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                username  TEXT,
                direction TEXT NOT NULL CHECK(direction IN ('in','out')),
                text      TEXT,
                ts        REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, ts);
            CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);
        """)
        await db.commit()
    finally:
        await db.close()


async def log_message(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    direction: str,
    text: Optional[str],
) -> None:
    now = time.time()
    db = await _get_db()
    try:
        await db.execute(
            """INSERT INTO users (user_id, username, first_name, first_seen, last_seen, msg_count)
               VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(user_id) DO UPDATE SET
                 username   = COALESCE(excluded.username, users.username),
                 first_name = COALESCE(excluded.first_name, users.first_name),
                 last_seen  = excluded.last_seen,
                 msg_count  = msg_count + 1""",
            (user_id, username, first_name, now, now),
        )
        await db.execute(
            "INSERT INTO messages (user_id, username, direction, text, ts) VALUES (?,?,?,?,?)",
            (user_id, username, direction, text, now),
        )
        await db.commit()
    finally:
        await db.close()


async def get_recent_conversations(limit: int = 20) -> list[dict]:
    db = await _get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT u.user_id, u.username, u.first_name, u.last_seen, u.msg_count,
                      (SELECT m.text FROM messages m WHERE m.user_id = u.user_id ORDER BY m.ts DESC LIMIT 1) AS last_msg
               FROM users u
               ORDER BY u.last_seen DESC
               LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_user_history(
    user_id: int, limit: int = 20, offset: int = 0
) -> list[dict]:
    db = await _get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT direction, text, ts FROM messages
               WHERE user_id = ?
               ORDER BY ts DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_user_by_username(username: str) -> Optional[dict]:
    clean = username.lstrip("@").lower()
    db = await _get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT * FROM users WHERE LOWER(username) = ? LIMIT 1", (clean,)
        )
        return dict(row[0]) if row else None
    finally:
        await db.close()


async def get_all_user_ids() -> list[int]:
    db = await _get_db()
    try:
        rows = await db.execute_fetchall("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]
    finally:
        await db.close()


async def get_user_count() -> int:
    db = await _get_db()
    try:
        rows = await db.execute_fetchall("SELECT COUNT(*) AS cnt FROM users")
        return rows[0]["cnt"]
    finally:
        await db.close()


async def search_messages(query: str, limit: int = 20) -> list[dict]:
    db = await _get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT m.user_id, m.username, m.direction, m.text, m.ts
               FROM messages m
               WHERE m.text LIKE ?
               ORDER BY m.ts DESC
               LIMIT ?""",
            (f"%{query}%", limit),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()
