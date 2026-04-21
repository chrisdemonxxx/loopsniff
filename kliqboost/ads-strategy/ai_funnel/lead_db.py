"""Shared SQLite database for the AI funnel pipeline.

Both the qualification bot and the AI userbot read/write the same DB,
enabling seamless lead handoff:

  TG Ad → Channel → Bot qualifies → writes to DB → Userbot picks up → DMs lead

Tables:
  leads         — every user who interacts with the funnel
  conversations — full message history (bot + userbot + user)
  lead_memory   — extracted BANT signals, sales stage, preferences
  handoffs      — bot→userbot handoff queue
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent / "funnel_leads.db"


async def init_db(db_path: str | Path | None = None) -> None:
    """Create all tables if they don't exist."""
    path = str(db_path or DEFAULT_DB_PATH)

    async with aiosqlite.connect(path, timeout=30) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")

        # Core lead record
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT,
                first_name      TEXT DEFAULT '',
                language        TEXT DEFAULT 'en',
                source          TEXT DEFAULT 'tg_ad',
                status          TEXT DEFAULT 'new',
                joined_channel  INTEGER DEFAULT 0,
                bot_qualified   INTEGER DEFAULT 0,
                userbot_active  INTEGER DEFAULT 0,
                bant_score      INTEGER DEFAULT 0,
                bant_tier       TEXT DEFAULT 'cold',
                sales_stage     TEXT DEFAULT 'opener',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Full conversation log
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                direction   TEXT NOT NULL,
                source      TEXT NOT NULL DEFAULT 'bot',
                text        TEXT NOT NULL,
                bant_score  INTEGER DEFAULT 0,
                stage       TEXT DEFAULT 'opener',
                ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES leads(user_id)
            )
        """)

        # Extracted lead intelligence
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lead_memory (
                user_id             INTEGER PRIMARY KEY,
                platform_interest   TEXT DEFAULT '',
                niche               TEXT DEFAULT '',
                budget_range        TEXT DEFAULT '',
                timeline            TEXT DEFAULT '',
                pain_points         TEXT DEFAULT '',
                current_provider    TEXT DEFAULT '',
                ad_spend_monthly    TEXT DEFAULT '',
                notes               TEXT DEFAULT '',
                last_interaction    TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES leads(user_id)
            )
        """)

        # Bot → Userbot handoff queue
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS handoffs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                reason      TEXT DEFAULT 'qualified',
                bot_summary TEXT DEFAULT '',
                bant_score  INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                picked_at   TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES leads(user_id)
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_user
            ON conversations(user_id, ts DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_handoff_status
            ON handoffs(status, created_at)
        """)

        await conn.commit()

    log.info("Funnel DB initialised at %s", path)


# ═══════════════════════════════════════════════════════════════════════════
# Lead CRUD
# ═══════════════════════════════════════════════════════════════════════════

async def upsert_lead(
    db_path: str,
    user_id: int,
    username: str | None = None,
    first_name: str = "",
    language: str = "en",
    source: str = "tg_ad",
    **kwargs,
) -> None:
    """Insert or update a lead record."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        await conn.execute("""
            INSERT INTO leads (user_id, username, first_name, language, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = COALESCE(excluded.username, leads.username),
                first_name = COALESCE(excluded.first_name, leads.first_name),
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, username, first_name, language, source))

        for key, val in kwargs.items():
            if key in ("status", "joined_channel", "bot_qualified",
                       "userbot_active", "bant_score", "bant_tier", "sales_stage"):
                await conn.execute(
                    f"UPDATE leads SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (val, user_id),
                )

        await conn.commit()


async def get_lead(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a lead by user_id."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM leads WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_lead_by_username(db_path: str, username: str) -> Optional[Dict[str, Any]]:
    """Fetch a lead by TG username."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM leads WHERE username = ?", (username.lower(),)
        )
        row = await cur.fetchone()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════
# Conversations
# ═══════════════════════════════════════════════════════════════════════════

async def save_message(
    db_path: str,
    user_id: int,
    direction: str,
    text: str,
    source: str = "bot",
    bant_score: int = 0,
    stage: str = "opener",
) -> None:
    """Persist a single message."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        await conn.execute(
            "INSERT INTO conversations (user_id, direction, source, text, bant_score, stage) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, direction, source, text, bant_score, stage),
        )
        await conn.commit()


async def load_history(
    db_path: str, user_id: int, limit: int = 20
) -> List[Dict[str, str]]:
    """Load recent messages for LLM context."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT direction, text, source FROM conversations "
            "WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()

    messages = []
    for row in reversed(rows):
        role = "user" if row["direction"] == "inbound" else "assistant"
        messages.append({"role": role, "content": row["text"]})
    return messages


# ═══════════════════════════════════════════════════════════════════════════
# Lead Memory
# ═══════════════════════════════════════════════════════════════════════════

async def save_lead_memory(db_path: str, user_id: int, data: Dict[str, Any]) -> None:
    """Upsert extracted lead intelligence."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        await conn.execute("""
            INSERT INTO lead_memory
                (user_id, platform_interest, niche, budget_range, timeline,
                 pain_points, current_provider, ad_spend_monthly, notes,
                 last_interaction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                platform_interest = excluded.platform_interest,
                niche = excluded.niche,
                budget_range = excluded.budget_range,
                timeline = excluded.timeline,
                pain_points = excluded.pain_points,
                current_provider = excluded.current_provider,
                ad_spend_monthly = excluded.ad_spend_monthly,
                notes = excluded.notes,
                last_interaction = excluded.last_interaction
        """, (
            user_id,
            data.get("platform_interest", ""),
            data.get("niche", ""),
            data.get("budget_range", ""),
            data.get("timeline", ""),
            data.get("pain_points", ""),
            data.get("current_provider", ""),
            data.get("ad_spend_monthly", ""),
            data.get("notes", ""),
            datetime.utcnow().isoformat(),
        ))
        await conn.commit()


async def get_lead_memory(db_path: str, user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM lead_memory WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════
# Handoff Queue
# ═══════════════════════════════════════════════════════════════════════════

async def create_handoff(
    db_path: str,
    user_id: int,
    reason: str = "qualified",
    bot_summary: str = "",
    bant_score: int = 0,
) -> int:
    """Queue a lead for userbot handoff. Returns handoff ID."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        cur = await conn.execute(
            "INSERT INTO handoffs (user_id, reason, bot_summary, bant_score) "
            "VALUES (?, ?, ?, ?)",
            (user_id, reason, bot_summary, bant_score),
        )
        await conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_pending_handoffs(db_path: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch unprocessed handoffs for the userbot to pick up."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("""
            SELECT h.*, l.username, l.first_name, l.language
            FROM handoffs h
            JOIN leads l ON h.user_id = l.user_id
            WHERE h.status = 'pending'
            ORDER BY h.created_at ASC
            LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def mark_handoff_picked(db_path: str, handoff_id: int) -> None:
    """Mark a handoff as picked up by the userbot."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        await conn.execute(
            "UPDATE handoffs SET status = 'picked', picked_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (handoff_id,),
        )
        await conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════════

async def get_funnel_stats(db_path: str) -> Dict[str, Any]:
    """Get funnel performance metrics."""
    async with aiosqlite.connect(db_path, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row

        total = (await (await conn.execute("SELECT COUNT(*) as c FROM leads")).fetchone())["c"]
        channel = (await (await conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE joined_channel = 1"
        )).fetchone())["c"]
        qualified = (await (await conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE bot_qualified = 1"
        )).fetchone())["c"]
        active_dm = (await (await conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE userbot_active = 1"
        )).fetchone())["c"]
        hot = (await (await conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE bant_tier = 'hot'"
        )).fetchone())["c"]

        # Tier breakdown
        tiers = {}
        cur = await conn.execute(
            "SELECT bant_tier, COUNT(*) as c FROM leads GROUP BY bant_tier"
        )
        async for row in cur:
            tiers[row["bant_tier"]] = row["c"]

    return {
        "total_leads": total,
        "joined_channel": channel,
        "bot_qualified": qualified,
        "active_dm": active_dm,
        "hot_leads": hot,
        "tier_breakdown": tiers,
        "channel_rate": f"{(channel / total * 100):.1f}%" if total else "0%",
        "qualification_rate": f"{(qualified / total * 100):.1f}%" if total else "0%",
        "dm_rate": f"{(active_dm / total * 100):.1f}%" if total else "0%",
    }
