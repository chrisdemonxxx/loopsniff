"""Session pool manager for burn-and-churn Telegram outreach.

Manages the lifecycle of hundreds of disposable Telethon .session files:
FRESH → ACTIVE → BURNED/BANNED, with optional RESTING cooldowns.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import asyncio
import aiosqlite
from loguru import logger


class SessionState(Enum):
    FRESH = "fresh"
    ACTIVE = "active"
    RESTING = "resting"
    BURNED = "burned"
    BANNED = "banned"
    ARCHIVED = "archived"


@dataclass
class SessionInfo:
    session_path: str
    phone: str
    state: SessionState
    api_id: int
    api_hash: str
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    proxy_binding: str
    messages_sent: int
    last_used: Optional[str]
    created_at: str
    burned_at: Optional[str]
    burn_reason: Optional[str]


def _row_to_session_info(row: aiosqlite.Row) -> SessionInfo:
    return SessionInfo(
        session_path=row["session_path"],
        phone=row["phone"] or "",
        state=SessionState(row["state"]),
        api_id=row["api_id"] or 0,
        api_hash=row["api_hash"] or "",
        device_model=row["device_model"] or "",
        system_version=row["system_version"] or "",
        app_version=row["app_version"] or "",
        lang_code=row["lang_code"] or "en",
        proxy_binding=row["proxy_binding"] or "",
        messages_sent=row["messages_sent"] or 0,
        last_used=row["last_used"],
        created_at=row["created_at"] or "",
        burned_at=row["burned_at"],
        burn_reason=row["burn_reason"],
    )


_SESSION_POOL_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_pool (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_path    TEXT UNIQUE NOT NULL,
    phone           TEXT,
    state           TEXT DEFAULT 'fresh',
    api_id          INTEGER,
    api_hash        TEXT,
    device_model    TEXT DEFAULT '',
    system_version  TEXT DEFAULT '',
    app_version     TEXT DEFAULT '',
    lang_code       TEXT DEFAULT 'en',
    proxy_binding   TEXT DEFAULT '',
    messages_sent   INTEGER DEFAULT 0,
    batch_messages  INTEGER DEFAULT 0,
    last_used       TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    burned_at       TEXT,
    burn_reason     TEXT,
    rest_until      TEXT
);
"""


class SessionPool:
    """Manages the lifecycle of hundreds of Telethon .session files."""

    def __init__(
        self,
        db_path: str = "outreach/data/outreach.db",
        sessions_dir: str = "sessions/telethon",
        profiles_path: str = "outreach/data/device_profiles.json",
    ):
        self.db_path = db_path
        self.sessions_dir = sessions_dir
        self.profiles_path = profiles_path
        self._checkout_lock = asyncio.Lock()

    # ── DB helpers ──────────────────────────────────────────────────────────

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.db_path)

    def _load_device_profiles(self) -> dict:
        if os.path.exists(self.profiles_path):
            with open(self.profiles_path) as f:
                return json.load(f)
        return {}

    def _phone_from_path(self, session_path: str) -> str:
        """Extract a phone/identifier from a .session filename."""
        name = Path(session_path).stem
        if name.startswith("tg_"):
            return name[3:]
        return name

    # ── init ────────────────────────────────────────────────────────────────

    async def init_db(self) -> None:
        """Create session_pool table if not exists."""
        async with self._connect() as conn:
            await conn.executescript(_SESSION_POOL_SCHEMA)
            await conn.commit()
        logger.info("session_pool table initialized at {}", self.db_path)

    # ── import ──────────────────────────────────────────────────────────────

    async def import_sessions(self, directory: str | None = None) -> dict:
        """Scan directory for .session files not yet in the pool.

        Auto-register them as FRESH. Load device profile from
        device_profiles.json if available.

        Returns: {imported: int, skipped: int, errors: int}
        """
        scan_dir = directory or self.sessions_dir
        profiles = self._load_device_profiles()
        results = {"imported": 0, "skipped": 0, "errors": 0}

        session_files = sorted(Path(scan_dir).glob("*.session"))
        if not session_files:
            logger.warning("No .session files found in {}", scan_dir)
            return results

        async with self._connect() as conn:
            for sf in session_files:
                session_path = str(sf.resolve())
                phone = self._phone_from_path(session_path)

                # Check if already registered
                cur = await conn.execute(
                    "SELECT id FROM session_pool WHERE session_path = ?",
                    (session_path,),
                )
                if await cur.fetchone():
                    results["skipped"] += 1
                    continue

                # Look up device profile by filename stem or phone
                profile = profiles.get(sf.stem) or profiles.get(f"tg_{phone}") or {}

                try:
                    await conn.execute(
                        """INSERT INTO session_pool
                           (session_path, phone, state, api_id, api_hash,
                            device_model, system_version, app_version,
                            lang_code)
                           VALUES (?, ?, 'fresh', ?, ?, ?, ?, ?, ?)""",
                        (
                            session_path,
                            phone,
                            profile.get("api_id"),
                            profile.get("api_hash", ""),
                            profile.get("device_model", ""),
                            profile.get("system_version", ""),
                            profile.get("app_version", ""),
                            profile.get("lang_code", "en"),
                        ),
                    )
                    results["imported"] += 1
                except Exception as exc:
                    logger.error("Failed to import {}: {}", sf.name, exc)
                    results["errors"] += 1

            await conn.commit()

        logger.info(
            "Import complete: {} imported, {} skipped, {} errors",
            results["imported"],
            results["skipped"],
            results["errors"],
        )
        return results

    # ── checkout / return ───────────────────────────────────────────────────

    async def checkout(self) -> Optional[SessionInfo]:
        """Get the next available FRESH session (FIFO — oldest first).

        Atomically transitions state: FRESH → ACTIVE.
        Returns None if no fresh sessions available.
        """
        async with self._checkout_lock:
            async with self._connect() as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(
                    """SELECT * FROM session_pool
                       WHERE state = 'fresh'
                       ORDER BY created_at ASC
                       LIMIT 1""",
                )
                row = await cur.fetchone()
                if row is None:
                    return None

                now = datetime.utcnow().isoformat()
                await conn.execute(
                    """UPDATE session_pool
                       SET state = 'active', last_used = ?, batch_messages = 0
                       WHERE id = ?""",
                    (now, row["id"]),
                )
                await conn.commit()

                logger.info("Checked out session: {}", row["session_path"])
                return _row_to_session_info(row)

    async def return_session(
        self, session_path: str, messages_sent: int = 0
    ) -> None:
        """Return a session after use without burning.

        State: ACTIVE → FRESH (ready for reuse).
        Updates messages_sent count.
        """
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            await conn.execute(
                """UPDATE session_pool
                   SET state = 'fresh',
                       messages_sent = messages_sent + ?,
                       batch_messages = 0,
                       last_used = ?
                   WHERE session_path = ? AND state = 'active'""",
                (messages_sent, now, session_path),
            )
            await conn.commit()
        logger.debug("Returned session {} (+{} msgs)", session_path, messages_sent)

    # ── burn / ban / rest ───────────────────────────────────────────────────

    async def burn(self, session_path: str, reason: str = "batch_limit_reached") -> None:
        """Mark session as burned. State: ACTIVE → BURNED.

        Records burn_reason and burned_at timestamp. Moves .session file
        to a burned/ subdirectory.
        """
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            await conn.execute(
                """UPDATE session_pool
                   SET state = 'burned', burned_at = ?, burn_reason = ?
                   WHERE session_path = ?""",
                (now, reason, session_path),
            )
            await conn.commit()

        # Move file to burned/ subdirectory
        src = Path(session_path)
        if src.exists():
            burned_dir = Path(self.sessions_dir) / "burned"
            burned_dir.mkdir(parents=True, exist_ok=True)
            dst = burned_dir / src.name
            try:
                shutil.move(str(src), str(dst))
                logger.info("Burned session {} → {} ({})", src.name, dst, reason)
            except OSError as exc:
                logger.warning("Could not move burned session {}: {}", src.name, exc)
        else:
            logger.info("Burned session {} (file missing, reason: {})", session_path, reason)

    async def ban(self, session_path: str, reason: str = "AUTH_KEY_UNREGISTERED") -> None:
        """Mark session as permanently banned. State: any → BANNED."""
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            await conn.execute(
                """UPDATE session_pool
                   SET state = 'banned', burned_at = ?, burn_reason = ?
                   WHERE session_path = ?""",
                (now, reason, session_path),
            )
            await conn.commit()
        logger.warning("Banned session: {} ({})", session_path, reason)

    async def rest(self, session_path: str, rest_seconds: int = 3600) -> None:
        """Put session in cooldown. State: ACTIVE → RESTING.

        Sets rest_until timestamp.
        """
        rest_until = (datetime.utcnow() + timedelta(seconds=rest_seconds)).isoformat()
        async with self._connect() as conn:
            await conn.execute(
                """UPDATE session_pool
                   SET state = 'resting', rest_until = ?
                   WHERE session_path = ? AND state = 'active'""",
                (rest_until, session_path),
            )
            await conn.commit()
        logger.info(
            "Session {} resting until {} ({} s)",
            session_path,
            rest_until,
            rest_seconds,
        )

    async def wake_rested(self) -> int:
        """Check for RESTING sessions past their rest_until time.

        Transition: RESTING → FRESH (available again).
        Returns count of woken sessions.
        """
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            cur = await conn.execute(
                """UPDATE session_pool
                   SET state = 'fresh', rest_until = NULL, batch_messages = 0
                   WHERE state = 'resting' AND rest_until <= ?""",
                (now,),
            )
            await conn.commit()
            woken = cur.rowcount

        if woken:
            logger.info("Woke {} rested sessions", woken)
        return woken

    # ── queries ─────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Return pool statistics by state."""
        async with self._connect() as conn:
            cur = await conn.execute(
                """SELECT state, COUNT(*) as cnt
                   FROM session_pool
                   GROUP BY state""",
            )
            rows = await cur.fetchall()

        stats = {s.value: 0 for s in SessionState}
        total = 0
        for state_val, cnt in rows:
            stats[state_val] = cnt
            total += cnt
        stats["total"] = total
        return stats

    async def get_sessions_by_state(self, state: SessionState) -> list[SessionInfo]:
        """Get all sessions in a given state."""
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM session_pool WHERE state = ? ORDER BY created_at ASC",
                (state.value,),
            )
            rows = await cur.fetchall()
        return [_row_to_session_info(r) for r in rows]

    async def has_fresh(self) -> bool:
        """Check if any FRESH sessions are available."""
        async with self._connect() as conn:
            cur = await conn.execute(
                "SELECT 1 FROM session_pool WHERE state = 'fresh' LIMIT 1",
            )
            return await cur.fetchone() is not None

    async def fresh_count(self) -> int:
        """Count of FRESH sessions."""
        async with self._connect() as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) FROM session_pool WHERE state = 'fresh'",
            )
            row = await cur.fetchone()
        return row[0] if row else 0

    # ── mutations ───────────────────────────────────────────────────────────

    async def bind_proxy(self, session_path: str, proxy_config: str) -> None:
        """Bind a proxy configuration (JSON string) to a session."""
        async with self._connect() as conn:
            await conn.execute(
                "UPDATE session_pool SET proxy_binding = ? WHERE session_path = ?",
                (proxy_config, session_path),
            )
            await conn.commit()

    async def bind_api_id(self, session_path: str, api_id: int, api_hash: str) -> None:
        """Bind an API ID/hash pair to a session."""
        async with self._connect() as conn:
            await conn.execute(
                "UPDATE session_pool SET api_id = ?, api_hash = ? WHERE session_path = ?",
                (api_id, api_hash, session_path),
            )
            await conn.commit()

    async def increment_messages(self, session_path: str, count: int = 1) -> None:
        """Increment messages_sent and batch_messages counters."""
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            await conn.execute(
                """UPDATE session_pool
                   SET messages_sent = messages_sent + ?,
                       batch_messages = batch_messages + ?,
                       last_used = ?
                   WHERE session_path = ?""",
                (count, count, now, session_path),
            )
            await conn.commit()

    async def reset_batch_counter(self, session_path: str) -> None:
        """Reset batch_messages to 0 (for new micro-batch)."""
        async with self._connect() as conn:
            await conn.execute(
                "UPDATE session_pool SET batch_messages = 0 WHERE session_path = ?",
                (session_path,),
            )
            await conn.commit()
