"""Per-channel conversation memory (SQLite, async-safe)."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = os.getenv("CORE_MEMORY_DB", "./core_memory.db")
_LOCK = asyncio.Lock()


def _ensure_schema():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                user_id TEXT,
                username TEXT,
                direction TEXT NOT NULL CHECK(direction IN ('in','out')),
                text TEXT,
                bant_score INTEGER,
                stage TEXT,
                prompt_version TEXT,
                ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_turns_conv
                ON turns(channel, conversation_id, ts);
            CREATE INDEX IF NOT EXISTS idx_turns_user ON turns(user_id, ts DESC);

            CREATE TABLE IF NOT EXISTS lead_state (
                channel TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                user_id TEXT,
                username TEXT,
                stage TEXT NOT NULL DEFAULT 'opener',
                bant_score INTEGER DEFAULT 0,
                bant_tier TEXT DEFAULT 'cold',
                last_seen REAL NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (channel, conversation_id)
            );
            """
        )
        c.commit()


_ensure_schema()


@contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    try:
        yield c
        c.commit()
    finally:
        c.close()


async def load_history(channel: str, conversation_id: str, limit: int = 20) -> list[dict]:
    async with _LOCK:
        def _run():
            with _conn() as c:
                cur = c.execute(
                    "SELECT direction, text FROM turns WHERE channel=? AND conversation_id=? "
                    "ORDER BY ts DESC LIMIT ?",
                    (channel, conversation_id, limit),
                )
                rows = cur.fetchall()
            out = []
            for direction, text in reversed(rows):
                role = "assistant" if direction == "out" else "user"
                out.append({"role": role, "content": text or ""})
            return out
        return await asyncio.to_thread(_run)


async def save_turn(
    channel: str,
    conversation_id: str,
    user_id: str,
    username: str | None,
    inbound: str,
    outbound: str,
    bant_score: int,
    bant_tier: str,
    stage: str,
    prompt_version: str,
) -> None:
    async with _LOCK:
        def _run():
            ts = time.time()
            with _conn() as c:
                c.execute(
                    "INSERT INTO turns(channel,conversation_id,user_id,username,direction,text,"
                    "bant_score,stage,prompt_version,ts) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (channel, conversation_id, user_id, username, "in", inbound,
                     bant_score, stage, prompt_version, ts),
                )
                c.execute(
                    "INSERT INTO turns(channel,conversation_id,user_id,username,direction,text,"
                    "bant_score,stage,prompt_version,ts) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (channel, conversation_id, user_id, username, "out", outbound,
                     bant_score, stage, prompt_version, ts + 0.001),
                )
                c.execute(
                    """INSERT INTO lead_state(channel,conversation_id,user_id,username,
                       stage,bant_score,bant_tier,last_seen,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(channel,conversation_id) DO UPDATE SET
                       stage=excluded.stage, bant_score=excluded.bant_score,
                       bant_tier=excluded.bant_tier, last_seen=excluded.last_seen,
                       username=COALESCE(excluded.username, lead_state.username),
                       user_id=COALESCE(excluded.user_id, lead_state.user_id)""",
                    (channel, conversation_id, user_id, username,
                     stage, bant_score, bant_tier, ts, ts),
                )
        await asyncio.to_thread(_run)


async def get_lead_state(channel: str, conversation_id: str) -> dict:
    async with _LOCK:
        def _run():
            with _conn() as c:
                cur = c.execute(
                    "SELECT stage,bant_score,bant_tier,last_seen FROM lead_state "
                    "WHERE channel=? AND conversation_id=?",
                    (channel, conversation_id),
                )
                row = cur.fetchone()
            if not row:
                return {"stage": "opener", "bant_score": 0, "bant_tier": "cold", "last_seen": 0}
            return {"stage": row[0], "bant_score": row[1] or 0,
                    "bant_tier": row[2] or "cold", "last_seen": row[3] or 0}
        return await asyncio.to_thread(_run)


async def message_count(channel: str, conversation_id: str) -> int:
    async with _LOCK:
        def _run():
            with _conn() as c:
                cur = c.execute(
                    "SELECT COUNT(*) FROM turns WHERE channel=? AND conversation_id=?",
                    (channel, conversation_id),
                )
                return cur.fetchone()[0]
        return await asyncio.to_thread(_run)
