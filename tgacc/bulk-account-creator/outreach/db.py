"""SQLite persistence layer (async via aiosqlite)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional

import aiosqlite

from . import config
from .models import Account, Lead, Message

log = logging.getLogger(__name__)

DB = str(config.DB_PATH)

# ── helpers ─────────────────────────────────────────────────────────────────

def _ts(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_ts(val: str | None) -> datetime | None:
    if val is None:
        return None
    return datetime.fromisoformat(val)


# ── schema ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    phone         TEXT PRIMARY KEY,
    session_file  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'fresh',
    created_at    TEXT NOT NULL,
    warmed_at     TEXT,
    dms_sent_today  INTEGER NOT NULL DEFAULT 0,
    total_dms_sent  INTEGER NOT NULL DEFAULT 0,
    spam_reports    INTEGER NOT NULL DEFAULT 0,
    last_used     TEXT
);

CREATE TABLE IF NOT EXISTS leads (
    username      TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',
    language      TEXT NOT NULL DEFAULT 'en',
    niche         TEXT,
    budget_tier   TEXT,
    contacted_at  TEXT,
    contacted_by  TEXT,
    reply_count   INTEGER NOT NULL DEFAULT 0,
    bant_score    INTEGER NOT NULL DEFAULT 0,
    notes         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_username TEXT NOT NULL,
    account_phone TEXT NOT NULL,
    direction     TEXT NOT NULL,
    text          TEXT NOT NULL,
    sent_at       TEXT NOT NULL,
    template_id   TEXT,
    FOREIGN KEY (lead_username) REFERENCES leads(username),
    FOREIGN KEY (account_phone) REFERENCES accounts(phone)
);

CREATE TABLE IF NOT EXISTS warming_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    phone         TEXT NOT NULL,
    day           INTEGER NOT NULL,
    groups_joined INTEGER NOT NULL DEFAULT 0,
    messages_sent INTEGER NOT NULL DEFAULT 0,
    channels_read INTEGER NOT NULL DEFAULT 0,
    reactions     INTEGER NOT NULL DEFAULT 0,
    executed_at   TEXT NOT NULL,
    FOREIGN KEY (phone) REFERENCES accounts(phone)
);

CREATE TABLE IF NOT EXISTS lead_memory (
    username          TEXT PRIMARY KEY,
    platform_interest TEXT DEFAULT '',
    niche             TEXT DEFAULT '',
    budget_range      TEXT DEFAULT '',
    timeline          TEXT DEFAULT '',
    pain_points       TEXT DEFAULT '',
    objections        TEXT DEFAULT '',
    preferences       TEXT DEFAULT '',
    sales_stage       TEXT DEFAULT 'opener',
    session_summary   TEXT DEFAULT '',
    last_updated      TEXT NOT NULL,
    FOREIGN KEY (username) REFERENCES leads(username)
);

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


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()
    log.info("Database initialized at %s", DB)


# ── accounts ────────────────────────────────────────────────────────────────

async def add_account(acct: Account) -> None:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(
            """INSERT OR IGNORE INTO accounts
               (phone, session_file, status, created_at, warmed_at,
                dms_sent_today, total_dms_sent, spam_reports, last_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (acct.phone, acct.session_file, acct.status,
             _ts(acct.created_at), _ts(acct.warmed_at),
             acct.dms_sent_today, acct.total_dms_sent,
             acct.spam_reports, _ts(acct.last_used)),
        )
        await conn.commit()


async def get_accounts(status: Optional[str] = None) -> List[Account]:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        if status:
            cur = await conn.execute(
                "SELECT * FROM accounts WHERE status = ?", (status,)
            )
        else:
            cur = await conn.execute("SELECT * FROM accounts")
        rows = await cur.fetchall()
    return [
        Account(
            phone=r["phone"],
            session_file=r["session_file"],
            status=r["status"],
            created_at=_parse_ts(r["created_at"]),
            warmed_at=_parse_ts(r["warmed_at"]),
            dms_sent_today=r["dms_sent_today"],
            total_dms_sent=r["total_dms_sent"],
            spam_reports=r["spam_reports"],
            last_used=_parse_ts(r["last_used"]),
        )
        for r in rows
    ]


async def update_account(phone: str, **kwargs) -> None:
    if not kwargs:
        return
    cols = []
    vals = []
    for k, v in kwargs.items():
        cols.append(f"{k} = ?")
        if isinstance(v, datetime):
            vals.append(v.isoformat())
        else:
            vals.append(v)
    vals.append(phone)
    sql = f"UPDATE accounts SET {', '.join(cols)} WHERE phone = ?"
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(sql, vals)
        await conn.commit()


async def reset_daily_dm_counts() -> None:
    """Reset dms_sent_today for all accounts (call once per day)."""
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute("UPDATE accounts SET dms_sent_today = 0")
        await conn.commit()


async def get_account_for_outreach() -> Optional[Account]:
    """Return the next available account for sending DMs.

    Picks an account with status in ('ready', 'active'),
    dms_sent_today below the safe limit, ordered by least-recently-used.
    """
    limit = config.ULTRA_SAFE_DM_LIMIT
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            """SELECT * FROM accounts
               WHERE status IN ('ready', 'active')
                 AND dms_sent_today < ?
               ORDER BY last_used ASC NULLS FIRST
               LIMIT 1""",
            (limit,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return Account(
        phone=row["phone"],
        session_file=row["session_file"],
        status=row["status"],
        created_at=_parse_ts(row["created_at"]),
        warmed_at=_parse_ts(row["warmed_at"]),
        dms_sent_today=row["dms_sent_today"],
        total_dms_sent=row["total_dms_sent"],
        spam_reports=row["spam_reports"],
        last_used=_parse_ts(row["last_used"]),
    )


# ── leads ───────────────────────────────────────────────────────────────────

async def add_lead(lead: Lead) -> None:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(
            """INSERT OR IGNORE INTO leads
               (username, source, status, language, niche, budget_tier,
                contacted_at, contacted_by, reply_count, bant_score, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lead.username, lead.source, lead.status, lead.language,
             lead.niche, lead.budget_tier, _ts(lead.contacted_at),
             lead.contacted_by, lead.reply_count, lead.bant_score,
             lead.notes),
        )
        await conn.commit()


async def add_leads_bulk(leads: List[Lead]) -> int:
    """Insert many leads at once. Returns count of newly inserted rows."""
    async with aiosqlite.connect(DB, timeout=30) as conn:
        inserted = 0
        for lead in leads:
            cur = await conn.execute(
                """INSERT OR IGNORE INTO leads
                   (username, source, status, language, niche, budget_tier,
                    contacted_at, contacted_by, reply_count, bant_score, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (lead.username, lead.source, lead.status, lead.language,
                 lead.niche, lead.budget_tier, _ts(lead.contacted_at),
                 lead.contacted_by, lead.reply_count, lead.bant_score,
                 lead.notes),
            )
            inserted += cur.rowcount
        await conn.commit()
    return inserted


async def get_leads(status: Optional[str] = None, limit: int = 0) -> List[Lead]:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        sql = "SELECT * FROM leads"
        params: list = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
    return [
        Lead(
            username=r["username"],
            source=r["source"],
            status=r["status"],
            language=r["language"],
            niche=r["niche"],
            budget_tier=r["budget_tier"],
            contacted_at=_parse_ts(r["contacted_at"]),
            contacted_by=r["contacted_by"],
            reply_count=r["reply_count"],
            bant_score=r["bant_score"],
            notes=r["notes"],
        )
        for r in rows
    ]


async def update_lead(username: str, **kwargs) -> None:
    if not kwargs:
        return
    cols = []
    vals = []
    for k, v in kwargs.items():
        cols.append(f"{k} = ?")
        if isinstance(v, datetime):
            vals.append(v.isoformat())
        else:
            vals.append(v)
    vals.append(username)
    sql = f"UPDATE leads SET {', '.join(cols)} WHERE username = ?"
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(sql, vals)
        await conn.commit()


async def get_lead_by_username(username: str) -> Optional[Lead]:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM leads WHERE username = ?", (username,))
        r = await cur.fetchone()
    if r is None:
        return None
    return Lead(
        username=r["username"],
        source=r["source"],
        status=r["status"],
        language=r["language"],
        niche=r["niche"],
        budget_tier=r["budget_tier"],
        contacted_at=_parse_ts(r["contacted_at"]),
        contacted_by=r["contacted_by"],
        reply_count=r["reply_count"],
        bant_score=r["bant_score"],
        notes=r["notes"],
    )


# ── messages ────────────────────────────────────────────────────────────────

async def add_message(msg: Message) -> None:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(
            """INSERT INTO messages
               (lead_username, account_phone, direction, text, sent_at, template_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (msg.lead_username, msg.account_phone, msg.direction,
             msg.text, _ts(msg.sent_at), msg.template_id),
        )
        await conn.commit()


async def get_messages(lead_username: Optional[str] = None) -> List[Message]:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        if lead_username:
            cur = await conn.execute(
                "SELECT * FROM messages WHERE lead_username = ? ORDER BY sent_at",
                (lead_username,),
            )
        else:
            cur = await conn.execute("SELECT * FROM messages ORDER BY sent_at")
        rows = await cur.fetchall()
    return [
        Message(
            lead_username=r["lead_username"],
            account_phone=r["account_phone"],
            direction=r["direction"],
            text=r["text"],
            sent_at=_parse_ts(r["sent_at"]),
            template_id=r["template_id"],
        )
        for r in rows
    ]


async def get_last_outbound(lead_username: str) -> Optional[Message]:
    """Get the most recent outbound message sent to a lead."""
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            """SELECT * FROM messages
               WHERE lead_username = ? AND direction = 'outbound'
               ORDER BY sent_at DESC LIMIT 1""",
            (lead_username,),
        )
        r = await cur.fetchone()
    if r is None:
        return None
    return Message(
        lead_username=r["lead_username"],
        account_phone=r["account_phone"],
        direction=r["direction"],
        text=r["text"],
        sent_at=_parse_ts(r["sent_at"]),
        template_id=r["template_id"],
    )


# ── warming log ─────────────────────────────────────────────────────────────

async def log_warming(phone: str, day: int, groups: int, msgs: int,
                      channels: int, reactions: int) -> None:
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(
            """INSERT INTO warming_log
               (phone, day, groups_joined, messages_sent, channels_read,
                reactions, executed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (phone, day, groups, msgs, channels, reactions,
             datetime.utcnow().isoformat()),
        )
        await conn.commit()


async def get_warming_day(phone: str) -> int:
    """Return the last completed warming day for an account (0 if none)."""
    async with aiosqlite.connect(DB, timeout=30) as conn:
        cur = await conn.execute(
            "SELECT MAX(day) FROM warming_log WHERE phone = ?", (phone,)
        )
        row = await cur.fetchone()
    return row[0] if row and row[0] else 0


# ── stats ───────────────────────────────────────────────────────────────────

async def get_daily_stats() -> dict:
    """Return aggregate stats for today."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB, timeout=30) as conn:
        cur = await conn.execute(
            """SELECT COUNT(*) FROM messages
               WHERE direction = 'outbound' AND sent_at LIKE ?""",
            (f"{today}%",),
        )
        dms_sent = (await cur.fetchone())[0]

        cur = await conn.execute(
            """SELECT COUNT(*) FROM messages
               WHERE direction = 'inbound' AND sent_at LIKE ?""",
            (f"{today}%",),
        )
        replies = (await cur.fetchone())[0]

        cur = await conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'qualified'"
        )
        qualified = (await cur.fetchone())[0]

        cur = await conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'hot'"
        )
        hot = (await cur.fetchone())[0]

        cur = await conn.execute("SELECT COUNT(*) FROM leads")
        total_leads = (await cur.fetchone())[0]

        cur = await conn.execute("SELECT COUNT(*) FROM accounts")
        total_accounts = (await cur.fetchone())[0]

        cur = await conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE status = 'banned'"
        )
        banned = (await cur.fetchone())[0]

    return {
        "dms_sent_today": dms_sent,
        "replies_today": replies,
        "leads_qualified": qualified,
        "leads_hot": hot,
        "total_leads": total_leads,
        "total_accounts": total_accounts,
        "accounts_banned": banned,
    }


# ── persistent lead memory ──────────────────────────────────────────────────

async def get_lead_memory(username: str) -> Optional[dict]:
    """Load persistent memory for a lead."""
    async with aiosqlite.connect(DB, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM lead_memory WHERE username = ?", (username,)
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return dict(row)


async def save_lead_memory(username: str, memory: dict) -> None:
    """Upsert persistent memory for a lead."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB, timeout=30) as conn:
        await conn.execute(
            """INSERT INTO lead_memory
               (username, platform_interest, niche, budget_range, timeline,
                pain_points, objections, preferences, sales_stage,
                session_summary, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(username) DO UPDATE SET
                 platform_interest = excluded.platform_interest,
                 niche = excluded.niche,
                 budget_range = excluded.budget_range,
                 timeline = excluded.timeline,
                 pain_points = excluded.pain_points,
                 objections = excluded.objections,
                 preferences = excluded.preferences,
                 sales_stage = excluded.sales_stage,
                 session_summary = excluded.session_summary,
                 last_updated = excluded.last_updated""",
            (
                username,
                memory.get("platform_interest", ""),
                memory.get("niche", ""),
                memory.get("budget_range", ""),
                memory.get("timeline", ""),
                memory.get("pain_points", ""),
                memory.get("objections", ""),
                memory.get("preferences", ""),
                memory.get("sales_stage", "opener"),
                memory.get("session_summary", ""),
                now,
            ),
        )
        await conn.commit()
