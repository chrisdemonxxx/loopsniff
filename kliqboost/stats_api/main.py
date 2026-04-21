"""
Kliqboost Stats API — Lightweight dashboard backend.
Reads from bot + autoresponder SQLite databases and serves JSON to the admin panel.
"""
import os, time, sqlite3
from pathlib import Path
from contextlib import contextmanager
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Config ───────────────────────────────────────────────────────────
API_KEY = os.getenv("STATS_API_KEY", "kliq-stats-2026-xK9m")
BASE = Path(__file__).resolve().parent.parent

BOT_DATA_DB    = str(BASE / "bot" / "bot_data.db")
BOT_MSGS_DB    = str(BASE / "bot" / "data" / "conversations.db")
BRIDGE_DB      = str(BASE / "bridge" / "deal_rooms.db")
AUTORESPONDER_DB = str(BASE / "userbot" / "sessions" / "conversations.db")

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(title="Kliqboost Stats API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _auth(key: str | None):
    if key != API_KEY:
        raise HTTPException(401, "Invalid API key")

@contextmanager
def _db(path: str):
    if not Path(path).exists():
        raise HTTPException(503, f"Database not found: {Path(path).name}")
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Dashboard overview ───────────────────────────────────────────────
@app.get("/stats")
def dashboard_stats(x_api_key: str = Header(None)):
    _auth(x_api_key)
    stats = {}

    # Bot conversations
    try:
        with _db(BOT_MSGS_DB) as conn:
            stats["bot_total_messages"] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            stats["bot_unique_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            stats["bot_messages_today"] = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE ts >= ?",
                (time.time() - 86400,)
            ).fetchone()[0]
    except Exception:
        stats["bot_total_messages"] = 0
        stats["bot_unique_users"] = 0
        stats["bot_messages_today"] = 0

    # Autoresponder conversations
    try:
        with _db(AUTORESPONDER_DB) as conn:
            stats["autoresponder_total"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            stats["autoresponder_unique_users"] = conn.execute(
                "SELECT COUNT(DISTINCT username) FROM conversations"
            ).fetchone()[0]
    except Exception:
        stats["autoresponder_total"] = 0
        stats["autoresponder_unique_users"] = 0

    # Deal rooms
    try:
        with _db(BRIDGE_DB) as conn:
            stats["deal_rooms_total"] = conn.execute("SELECT COUNT(*) FROM pending_deal_rooms").fetchone()[0]
            stats["deal_rooms_done"] = conn.execute(
                "SELECT COUNT(*) FROM pending_deal_rooms WHERE status = 'done'"
            ).fetchone()[0]
            stats["deal_rooms_pending"] = conn.execute(
                "SELECT COUNT(*) FROM pending_deal_rooms WHERE status = 'pending'"
            ).fetchone()[0]
            stats["deal_rooms_failed"] = conn.execute(
                "SELECT COUNT(*) FROM pending_deal_rooms WHERE status = 'failed'"
            ).fetchone()[0]
    except Exception:
        stats["deal_rooms_total"] = 0
        stats["deal_rooms_done"] = 0
        stats["deal_rooms_pending"] = 0
        stats["deal_rooms_failed"] = 0

    # BANT lead scores from bot
    try:
        with _db(BOT_DATA_DB) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "leads" in tables:
                stats["leads_total"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
                stats["leads_hot"] = conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE bant_score >= 75"
                ).fetchone()[0]
                stats["leads_warm"] = conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE bant_score >= 50 AND bant_score < 75"
                ).fetchone()[0]
            else:
                stats["leads_total"] = stats.get("bot_unique_users", 0)
                stats["leads_hot"] = stats["deal_rooms_total"]
                stats["leads_warm"] = 0
    except Exception:
        stats["leads_total"] = 0
        stats["leads_hot"] = 0
        stats["leads_warm"] = 0

    return {"status": "ok", "data": stats}


# ── Recent conversations ────────────────────────────────────────────
@app.get("/conversations")
def recent_conversations(
    limit: int = Query(50, ge=1, le=200),
    source: str = Query("all"),  # "bot", "autoresponder", "all"
    x_api_key: str = Header(None),
):
    _auth(x_api_key)
    results = []

    if source in ("bot", "all"):
        try:
            with _db(BOT_MSGS_DB) as conn:
                rows = conn.execute("""
                    SELECT u.user_id, u.username, u.first_name, u.msg_count,
                           u.first_seen, u.last_seen,
                           (SELECT text FROM messages m WHERE m.user_id = u.user_id
                            ORDER BY ts DESC LIMIT 1) as last_message
                    FROM users u ORDER BY u.last_seen DESC LIMIT ?
                """, (limit,)).fetchall()
                for r in rows:
                    results.append({
                        "source": "bot",
                        "user_id": r["user_id"],
                        "username": r["username"],
                        "name": r["first_name"],
                        "message_count": r["msg_count"],
                        "last_message": r["last_message"],
                        "first_seen": r["first_seen"],
                        "last_seen": r["last_seen"],
                    })
        except Exception:
            pass

    if source in ("autoresponder", "all"):
        try:
            with _db(AUTORESPONDER_DB) as conn:
                rows = conn.execute("""
                    SELECT username,
                           MAX(bant_score) as bant_score,
                           MAX(stage) as stage,
                           COUNT(*) as msg_count,
                           MAX(timestamp) as last_ts,
                           MIN(timestamp) as first_ts
                    FROM conversations
                    GROUP BY username
                    ORDER BY last_ts DESC LIMIT ?
                """, (limit,)).fetchall()
                for r in rows:
                    results.append({
                        "source": "autoresponder",
                        "username": r["username"],
                        "bant_score": r["bant_score"],
                        "stage": r["stage"],
                        "message_count": r["msg_count"],
                        "first_seen": r["first_ts"],
                        "last_seen": r["last_ts"],
                    })
        except Exception:
            pass

    results.sort(key=lambda x: x.get("last_seen", 0) or 0, reverse=True)
    return {"status": "ok", "count": len(results), "data": results[:limit]}


# ── Lead pipeline ────────────────────────────────────────────────────
@app.get("/leads")
def lead_pipeline(x_api_key: str = Header(None)):
    _auth(x_api_key)
    leads = []

    try:
        with _db(AUTORESPONDER_DB) as conn:
            rows = conn.execute("""
                SELECT username,
                       MAX(bant_score) as bant_score,
                       MAX(stage) as stage,
                       COUNT(*) as msg_count,
                       MAX(timestamp) as last_seen
                FROM conversations
                GROUP BY username
                HAVING bant_score > 0
                ORDER BY bant_score DESC
            """).fetchall()
            for r in rows:
                score = r["bant_score"] or 0
                tier = "hot" if score >= 75 else "warm" if score >= 50 else "cool" if score >= 25 else "cold"
                leads.append({
                    "username": r["username"],
                    "bant_score": score,
                    "tier": tier,
                    "stage": r["stage"],
                    "messages": r["msg_count"],
                    "last_seen": r["last_seen"],
                })
    except Exception:
        pass

    return {"status": "ok", "count": len(leads), "data": leads}


# ── Deal rooms ───────────────────────────────────────────────────────
@app.get("/deal-rooms")
def deal_rooms(x_api_key: str = Header(None)):
    _auth(x_api_key)
    rooms = []

    try:
        with _db(BRIDGE_DB) as conn:
            rows = conn.execute(
                "SELECT * FROM pending_deal_rooms ORDER BY id DESC"
            ).fetchall()
            for r in rows:
                rooms.append({
                    "id": r["id"],
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
    except Exception:
        pass

    return {"status": "ok", "count": len(rooms), "data": rooms}


# ── Chat history for a user ──────────────────────────────────────────
@app.get("/chat/{user_id}")
def chat_history(user_id: int, x_api_key: str = Header(None)):
    _auth(x_api_key)
    messages = []

    # Bot messages
    try:
        with _db(BOT_MSGS_DB) as conn:
            rows = conn.execute(
                "SELECT direction, text, ts FROM messages WHERE user_id = ? ORDER BY ts",
                (user_id,)
            ).fetchall()
            for r in rows:
                messages.append({
                    "source": "bot",
                    "direction": r["direction"],
                    "text": r["text"],
                    "timestamp": r["ts"],
                })
    except Exception:
        pass

    # Bot AI conversation (role-based)
    try:
        with _db(BOT_DATA_DB) as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE user_id = ? ORDER BY timestamp",
                (user_id,)
            ).fetchall()
            for r in rows:
                messages.append({
                    "source": "bot_ai",
                    "direction": "in" if r["role"] == "user" else "out",
                    "text": r["content"],
                    "timestamp": r["timestamp"],
                })
    except Exception:
        pass

    messages.sort(key=lambda x: x.get("timestamp", 0) or 0)
    return {"status": "ok", "count": len(messages), "data": messages}


# ── Health check ─────────────────────────────────────────────────────
@app.get("/health")
def health():
    dbs = {}
    for name, path in [
        ("bot_data", BOT_DATA_DB),
        ("bot_messages", BOT_MSGS_DB),
        ("bridge", BRIDGE_DB),
        ("autoresponder", AUTORESPONDER_DB),
    ]:
        dbs[name] = Path(path).exists()
    return {
        "status": "ok",
        "databases": dbs,
        "uptime": time.time(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099)
