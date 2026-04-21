#!/usr/bin/env python3
"""
Sync local bot SQLite data → Render API (PostgreSQL).
Runs every 60s via systemd timer or cron.
"""
import os, sys, time, sqlite3, json, logging
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sync")

BASE = Path(__file__).resolve().parent.parent
BOT_DATA_DB    = str(BASE / "bot" / "bot_data.db")
BOT_MSGS_DB    = str(BASE / "bot" / "data" / "conversations.db")
BRIDGE_DB      = str(BASE / "bridge" / "deal_rooms.db")
AR_DB          = str(BASE / "userbot" / "sessions" / "conversations.db")

API_URL = os.getenv("KLIQBOOST_API_URL", "https://kliqboost-api.onrender.com")
SYNC_KEY = os.getenv("STATS_SYNC_KEY", "kliq-stats-2026-xK9m")

HEADERS = {"X-Sync-Key": SYNC_KEY, "Content-Type": "application/json"}

_csrf_token: str | None = None

def _get_headers():
    """Get headers with CSRF token if needed."""
    global _csrf_token
    h = dict(HEADERS)
    if _csrf_token:
        h["X-CSRF-Token"] = _csrf_token
    return h

def _refresh_csrf():
    """Fetch a CSRF token from the API."""
    global _csrf_token
    try:
        r = httpx.get(f"{API_URL}/health", timeout=15)
        for cookie_name in ("csrf_token",):
            if cookie_name in r.cookies:
                _csrf_token = r.cookies[cookie_name]
                log.info("CSRF token refreshed")
                return
    except Exception:
        pass


def _db(path):
    if not Path(path).exists():
        return None
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def sync_conversations():
    """Merge bot + autoresponder conversations into a single list."""
    items = []

    # Bot conversations
    conn = _db(BOT_MSGS_DB)
    if conn:
        rows = conn.execute("""
            SELECT u.user_id, u.username, u.first_name, u.msg_count,
                   u.first_seen, u.last_seen,
                   (SELECT text FROM messages m WHERE m.user_id = u.user_id
                    ORDER BY ts DESC LIMIT 1) as last_message
            FROM users u
        """).fetchall()
        for r in rows:
            items.append({
                "user_id": r["user_id"],
                "username": r["username"],
                "first_name": r["first_name"],
                "message_count": r["msg_count"],
                "last_message": (r["last_message"] or "")[:500],
                "source": "bot",
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
            })
        conn.close()

    # Autoresponder conversations with BANT
    conn = _db(AR_DB)
    if conn:
        rows = conn.execute("""
            SELECT username,
                   MAX(bant_score) as bant_score,
                   MAX(stage) as stage,
                   COUNT(*) as msg_count,
                   MIN(ts) as first_ts,
                   MAX(ts) as last_ts
            FROM conversations
            GROUP BY username
        """).fetchall()
        for r in rows:
            score = r["bant_score"] or 0
            tier = "hot" if score >= 75 else "warm" if score >= 50 else "cool" if score >= 25 else "cold"
            # Convert text timestamps to epoch floats
            first_ts = r["first_ts"]
            last_ts = r["last_ts"]
            if isinstance(first_ts, str):
                from datetime import datetime as _dt
                try: first_ts = _dt.fromisoformat(first_ts).timestamp()
                except Exception: first_ts = None
            if isinstance(last_ts, str):
                from datetime import datetime as _dt
                try: last_ts = _dt.fromisoformat(last_ts).timestamp()
                except Exception: last_ts = None
            items.append({
                "user_id": hash(r["username"]) & 0x7FFFFFFFFFFFFFFF,
                "username": r["username"],
                "message_count": r["msg_count"],
                "bant_score": score,
                "bant_tier": tier,
                "stage": r["stage"] or "intro",
                "source": "autoresponder",
                "first_seen": first_ts,
                "last_seen": last_ts,
            })
        conn.close()

    if items:
        resp = httpx.post(f"{API_URL}/bot-stats/sync/conversations", json=items,
                          headers=_get_headers(), timeout=30)
        log.info("Conversations sync: %d items → %s", len(items), resp.status_code)
    return len(items)


def sync_deal_rooms():
    conn = _db(BRIDGE_DB)
    if not conn:
        return 0
    rows = conn.execute("SELECT * FROM pending_deal_rooms").fetchall()
    items = []
    for r in rows:
        items.append({
            "user_id": r["user_id"],
            "username": r["username"],
            "full_name": r["full_name"],
            "bant_score": r["bant_score"],
            "platform": r["platform"],
            "niche": r["niche"],
            "budget": r["budget"],
            "timeline": r["timeline"],
            "status": r["status"],
            "invite_link": r["invite_link"],
            "created_at": r["created_at"],
            "completed_at": r["completed_at"],
        })
    conn.close()
    if items:
        resp = httpx.post(f"{API_URL}/bot-stats/sync/deal-rooms", json=items,
                          headers=_get_headers(), timeout=30)
        log.info("Deal rooms sync: %d items → %s", len(items), resp.status_code)
    return len(items)


def sync_stats_snapshot():
    """Push an aggregate stats snapshot."""
    stats = {}

    conn = _db(BOT_MSGS_DB)
    if conn:
        stats["bot_total_messages"] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        stats["bot_unique_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats["bot_messages_today"] = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE ts >= ?", (time.time() - 86400,)
        ).fetchone()[0]
        conn.close()
    else:
        stats["bot_total_messages"] = 0
        stats["bot_unique_users"] = 0
        stats["bot_messages_today"] = 0

    conn = _db(AR_DB)
    if conn:
        stats["autoresponder_total"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        stats["autoresponder_unique_users"] = conn.execute(
            "SELECT COUNT(DISTINCT username) FROM conversations"
        ).fetchone()[0]
        conn.close()
    else:
        stats["autoresponder_total"] = 0
        stats["autoresponder_unique_users"] = 0

    conn = _db(BRIDGE_DB)
    if conn:
        stats["deal_rooms_total"] = conn.execute("SELECT COUNT(*) FROM pending_deal_rooms").fetchone()[0]
        stats["deal_rooms_done"] = conn.execute(
            "SELECT COUNT(*) FROM pending_deal_rooms WHERE status='done'"
        ).fetchone()[0]
        stats["deal_rooms_pending"] = conn.execute(
            "SELECT COUNT(*) FROM pending_deal_rooms WHERE status='pending'"
        ).fetchone()[0]
        conn.close()
    else:
        stats["deal_rooms_total"] = 0
        stats["deal_rooms_done"] = 0
        stats["deal_rooms_pending"] = 0

    stats["leads_total"] = stats["bot_unique_users"] + stats["autoresponder_unique_users"]
    stats["leads_hot"] = stats["deal_rooms_total"]
    stats["leads_warm"] = 0

    resp = httpx.post(f"{API_URL}/bot-stats/sync/stats", json=stats,
                      headers=_get_headers(), timeout=30)
    log.info("Stats snapshot → %s", resp.status_code)


def main():
    log.info("Starting sync cycle → %s", API_URL)
    try:
        r = httpx.get(f"{API_URL}/health", timeout=10)
        if r.status_code != 200:
            log.error("API health check failed: %s", r.status_code)
            return
        # Grab CSRF token from health response cookie
        if "csrf_token" in r.cookies:
            global _csrf_token
            _csrf_token = r.cookies["csrf_token"]
    except Exception as e:
        log.error("API unreachable: %s", e)
        return

    sync_conversations()
    sync_deal_rooms()
    sync_stats_snapshot()
    log.info("Sync complete ✓")


if __name__ == "__main__":
    if "--loop" in sys.argv:
        interval = int(os.getenv("SYNC_INTERVAL", "60"))
        log.info("Running in loop mode (every %ds)", interval)
        while True:
            try:
                main()
            except Exception as e:
                log.error("Sync error: %s", e)
            time.sleep(interval)
    else:
        main()
