"""AdFlux Media — Campaign Monitoring Dashboard (FastAPI)."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ── database path ───────────────────────────────────────────────────────────
# Same DB the outreach engine uses: outreach/data/outreach.db
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "outreach.db"
DB = str(_DB_PATH)

app = FastAPI(title="AdFlux Dashboard", version="2.0.0")


# ── WebSocket Connection Manager ───────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for c in stale:
            self.active_connections.remove(c)


ws_manager = ConnectionManager()


class AssignRequest(BaseModel):
    account_phone: str

# ── schema bootstrap ───────────────────────────────────────────────────────
# Create tables if the DB doesn't exist yet so the dashboard never crashes.

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
CREATE TABLE IF NOT EXISTS assignments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_username TEXT NOT NULL,
    account_phone TEXT NOT NULL,
    assigned_at   TEXT NOT NULL,
    assigned_by   TEXT DEFAULT 'admin',
    FOREIGN KEY (lead_username) REFERENCES leads(username),
    FOREIGN KEY (account_phone) REFERENCES accounts(phone)
);
"""


@app.on_event("startup")
async def _ensure_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB) as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()


# ── helpers ─────────────────────────────────────────────────────────────────

def _row_to_dict(cursor: aiosqlite.Cursor, row: tuple) -> dict:
    """Convert a sqlite Row to a plain dict."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


async def _fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def _fetch_one(sql: str, params: tuple = ()) -> dict | None:
    async with aiosqlite.connect(DB) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(sql, params)
        row = await cur.fetchone()
        return dict(row) if row else None


async def _fetch_scalar(sql: str, params: tuple = ()) -> int:
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute(sql, params)
        row = await cur.fetchone()
        return row[0] if row and row[0] is not None else 0


# ── API: /api/stats ─────────────────────────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    today = date.today().isoformat()
    total_accounts = await _fetch_scalar("SELECT COUNT(*) FROM accounts")
    active_accounts = await _fetch_scalar(
        "SELECT COUNT(*) FROM accounts WHERE status IN ('ready', 'active')"
    )
    banned_accounts = await _fetch_scalar(
        "SELECT COUNT(*) FROM accounts WHERE status = 'banned'"
    )
    total_leads = await _fetch_scalar("SELECT COUNT(*) FROM leads")
    hot_leads = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE status = 'hot'"
    )
    qualified_leads = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE status = 'qualified'"
    )
    total_messages_sent = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'outbound'"
    )
    total_replies = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'inbound'"
    )
    dms_today = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'outbound' AND sent_at LIKE ?",
        (f"{today}%",),
    )
    replies_today = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'inbound' AND sent_at LIKE ?",
        (f"{today}%",),
    )
    reply_rate = (
        round(total_replies / total_messages_sent * 100, 1)
        if total_messages_sent > 0
        else 0.0
    )
    converted = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE status IN ('qualified', 'hot')"
    )
    contacted = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE status != 'new'"
    )
    conversion_rate = (
        round(converted / contacted * 100, 1) if contacted > 0 else 0.0
    )
    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "banned_accounts": banned_accounts,
        "total_leads": total_leads,
        "hot_leads": hot_leads,
        "qualified_leads": qualified_leads,
        "total_messages_sent": total_messages_sent,
        "total_replies": total_replies,
        "dms_today": dms_today,
        "replies_today": replies_today,
        "reply_rate": reply_rate,
        "conversion_rate": conversion_rate,
    }


# ── API: /api/accounts ──────────────────────────────────────────────────────

@app.get("/api/accounts")
async def api_accounts():
    rows = await _fetch_all(
        """SELECT phone, status, dms_sent_today, total_dms_sent,
                  spam_reports, last_used, created_at, warmed_at
           FROM accounts ORDER BY last_used DESC"""
    )
    return rows


# ── API: /api/leads ─────────────────────────────────────────────────────────

@app.get("/api/leads")
async def api_leads(
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_score: int = Query(0),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if min_score > 0:
        clauses.append("bant_score >= ?")
        params.append(min_score)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    offset = (page - 1) * per_page
    total = await _fetch_scalar(f"SELECT COUNT(*) FROM leads{where}", tuple(params))
    rows = await _fetch_all(
        f"SELECT * FROM leads{where} ORDER BY bant_score DESC LIMIT ? OFFSET ?",
        tuple(params) + (per_page, offset),
    )
    return {"total": total, "page": page, "per_page": per_page, "leads": rows}


# ── API: /api/leads/search ─────────────────────────────────────────────────

@app.get("/api/leads/search")
async def api_lead_search(q: str = Query(..., min_length=1)):
    pattern = f"%{q}%"
    rows = await _fetch_all(
        """SELECT * FROM leads
           WHERE username LIKE ? OR notes LIKE ? OR source LIKE ?
           ORDER BY bant_score DESC LIMIT 50""",
        (pattern, pattern, pattern),
    )
    return {"query": q, "results": rows, "count": len(rows)}


# ── API: /api/leads/{username} ──────────────────────────────────────────────

@app.get("/api/leads/{username}")
async def api_lead_detail(username: str):
    lead = await _fetch_one("SELECT * FROM leads WHERE username = ?", (username,))
    if lead is None:
        return JSONResponse({"error": "Lead not found"}, status_code=404)
    messages = await _fetch_all(
        "SELECT * FROM messages WHERE lead_username = ? ORDER BY sent_at",
        (username,),
    )
    return {"lead": lead, "messages": messages}


# ── API: /api/messages ──────────────────────────────────────────────────────

@app.get("/api/messages")
async def api_messages(limit: int = Query(100, ge=1, le=500)):
    rows = await _fetch_all(
        "SELECT * FROM messages ORDER BY sent_at DESC LIMIT ?", (limit,)
    )
    return rows


# ── API: /api/warming ──────────────────────────────────────────────────────

@app.get("/api/warming")
async def api_warming():
    rows = await _fetch_all(
        """SELECT a.phone, a.status,
                  COALESCE(w.max_day, 0)   AS current_day,
                  14                        AS total_days,
                  COALESCE(w.total_groups, 0)   AS groups_joined,
                  COALESCE(w.total_msgs, 0)     AS messages_sent,
                  COALESCE(w.total_channels, 0) AS channels_read,
                  COALESCE(w.total_reactions, 0) AS reactions,
                  w.last_executed
           FROM accounts a
           LEFT JOIN (
               SELECT phone,
                      MAX(day)                    AS max_day,
                      SUM(groups_joined)           AS total_groups,
                      SUM(messages_sent)           AS total_msgs,
                      SUM(channels_read)           AS total_channels,
                      SUM(reactions)               AS total_reactions,
                      MAX(executed_at)             AS last_executed
               FROM warming_log GROUP BY phone
           ) w ON a.phone = w.phone
           ORDER BY w.max_day DESC"""
    )
    return rows


# ── API: /api/health ────────────────────────────────────────────────────────

@app.get("/api/health")
async def api_health():
    try:
        db_ok = True
        async with aiosqlite.connect(DB) as conn:
            await conn.execute("SELECT 1")
    except Exception:
        db_ok = False
    accounts_total = await _fetch_scalar("SELECT COUNT(*) FROM accounts")
    accounts_active = await _fetch_scalar(
        "SELECT COUNT(*) FROM accounts WHERE status IN ('ready', 'active')"
    )
    accounts_banned = await _fetch_scalar(
        "SELECT COUNT(*) FROM accounts WHERE status = 'banned'"
    )
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "db_path": DB,
        "accounts_total": accounts_total,
        "accounts_active": accounts_active,
        "accounts_banned": accounts_banned,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── WebSocket: /ws ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can also send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def notify_event(event_type: str, data: dict):
    """Broadcast a real-time event to all connected WebSocket clients."""
    await ws_manager.broadcast({
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── API: /api/funnel ───────────────────────────────────────────────────────

FUNNEL_STAGES = [
    {"name": "New", "db_status": "new", "color": "#6366f1"},
    {"name": "Contacted", "db_status": "contacted", "color": "#8b5cf6"},
    {"name": "Replied", "db_status": "replied", "color": "#a855f7"},
    {"name": "Engaged", "db_status": "engaged", "color": "#d946ef"},
    {"name": "Qualified", "db_status": "qualified", "color": "#ec4899"},
    {"name": "Hot", "db_status": "hot", "color": "#f43f5e"},
    {"name": "Payment Sent", "db_status": "payment_sent", "color": "#f97316"},
    {"name": "Converted", "db_status": "converted", "color": "#eab308"},
    {"name": "Onboarded", "db_status": "onboarded", "color": "#22c55e"},
]


@app.get("/api/funnel")
async def api_funnel():
    stages = []
    total = await _fetch_scalar("SELECT COUNT(*) FROM leads")
    for s in FUNNEL_STAGES:
        count = await _fetch_scalar(
            "SELECT COUNT(*) FROM leads WHERE status = ?", (s["db_status"],)
        )
        stages.append({"name": s["name"], "count": count, "color": s["color"]})

    conversion_rates = {}
    for i in range(1, len(stages)):
        prev = stages[i - 1]
        curr = stages[i]
        if prev["count"] > 0:
            conversion_rates[f"{prev['name']}_to_{curr['name']}"] = round(
                curr["count"] / prev["count"] * 100, 1
            )
        else:
            conversion_rates[f"{prev['name']}_to_{curr['name']}"] = 0.0

    return {"stages": stages, "conversion_rates": conversion_rates, "total": total}


# ── API: /leads/{username}/timeline ────────────────────────────────────────

@app.get("/api/leads/{username}/timeline")
async def api_lead_timeline(username: str):
    lead = await _fetch_one("SELECT * FROM leads WHERE username = ?", (username,))
    if lead is None:
        return JSONResponse({"error": "Lead not found"}, status_code=404)

    events = []

    # Messages (DMs sent + replies received)
    messages = await _fetch_all(
        "SELECT * FROM messages WHERE lead_username = ? ORDER BY sent_at",
        (username,),
    )
    for m in messages:
        evt_type = "dm_sent" if m["direction"] == "outbound" else "reply_received"
        events.append({
            "type": evt_type,
            "timestamp": m["sent_at"],
            "detail": {
                "text": m["text"][:200],
                "account_phone": m["account_phone"],
                "template_id": m.get("template_id"),
            },
        })

    # Contacted timestamp
    if lead.get("contacted_at"):
        events.append({
            "type": "contacted",
            "timestamp": lead["contacted_at"],
            "detail": {"contacted_by": lead.get("contacted_by")},
        })

    # Current stage + BANT score as latest state
    events.append({
        "type": "current_state",
        "timestamp": lead.get("contacted_at") or datetime.utcnow().isoformat(),
        "detail": {
            "stage": lead["status"],
            "bant_score": lead["bant_score"],
            "notes": lead.get("notes", ""),
        },
    })

    # Assignments
    assignments = await _fetch_all(
        "SELECT * FROM assignments WHERE lead_username = ? ORDER BY assigned_at",
        (username,),
    )
    for a in assignments:
        events.append({
            "type": "assigned",
            "timestamp": a["assigned_at"],
            "detail": {
                "account_phone": a["account_phone"],
                "assigned_by": a.get("assigned_by", "admin"),
            },
        })

    events.sort(key=lambda e: e["timestamp"] or "")
    return {"username": username, "timeline": events}


# ── API: Assignments ───────────────────────────────────────────────────────

@app.post("/api/leads/{username}/assign")
async def api_assign_lead(username: str, req: AssignRequest):
    lead = await _fetch_one("SELECT * FROM leads WHERE username = ?", (username,))
    if lead is None:
        return JSONResponse({"error": "Lead not found"}, status_code=404)
    account = await _fetch_one(
        "SELECT * FROM accounts WHERE phone = ?", (req.account_phone,)
    )
    if account is None:
        return JSONResponse({"error": "Account not found"}, status_code=404)

    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB) as conn:
        await conn.execute(
            """INSERT INTO assignments (lead_username, account_phone, assigned_at, assigned_by)
               VALUES (?, ?, ?, ?)""",
            (username, req.account_phone, now, "admin"),
        )
        await conn.execute(
            "UPDATE leads SET contacted_by = ? WHERE username = ?",
            (req.account_phone, username),
        )
        await conn.commit()

    await notify_event("lead_assigned", {
        "username": username,
        "account_phone": req.account_phone,
    })

    return {"status": "assigned", "lead": username, "account": req.account_phone}


@app.get("/api/assignments")
async def api_assignments():
    rows = await _fetch_all(
        """SELECT a.id, a.lead_username, a.account_phone, a.assigned_at,
                  a.assigned_by, l.status AS lead_status, l.bant_score
           FROM assignments a
           LEFT JOIN leads l ON a.lead_username = l.username
           ORDER BY a.assigned_at DESC"""
    )
    return rows


# ── API: /api/metrics ──────────────────────────────────────────────────────

@app.get("/api/metrics")
async def api_metrics():
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    month_ago = (date.today() - timedelta(days=30)).isoformat()

    total_leads = await _fetch_scalar("SELECT COUNT(*) FROM leads")
    contacted = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE status != 'new'"
    )
    total_msgs = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'outbound'"
    )
    total_replies = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'inbound'"
    )
    reply_rate = round(total_replies / total_msgs * 100, 1) if total_msgs > 0 else 0.0

    engaged = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE reply_count > 0"
    )
    engagement_rate = round(engaged / contacted * 100, 1) if contacted > 0 else 0.0

    converted = await _fetch_scalar(
        "SELECT COUNT(*) FROM leads WHERE status IN ('converted', 'onboarded', 'qualified', 'hot')"
    )
    conversion_rate = round(converted / contacted * 100, 1) if contacted > 0 else 0.0

    msgs_today = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'outbound' AND sent_at >= ?",
        (today,),
    )
    msgs_week = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'outbound' AND sent_at >= ?",
        (week_ago,),
    )
    msgs_month = await _fetch_scalar(
        "SELECT COUNT(*) FROM messages WHERE direction = 'outbound' AND sent_at >= ?",
        (month_ago,),
    )

    # Average response time (hours between last outbound and first inbound per lead)
    avg_resp = await _fetch_one(
        """SELECT AVG(
             (julianday(r.first_reply) - julianday(o.last_outbound)) * 24
           ) AS avg_hours
           FROM (
             SELECT lead_username, MAX(sent_at) AS last_outbound
             FROM messages WHERE direction = 'outbound'
             GROUP BY lead_username
           ) o
           JOIN (
             SELECT lead_username, MIN(sent_at) AS first_reply
             FROM messages WHERE direction = 'inbound'
             GROUP BY lead_username
           ) r ON o.lead_username = r.lead_username
           WHERE r.first_reply > o.last_outbound"""
    )
    avg_response_hours = round(avg_resp["avg_hours"], 1) if avg_resp and avg_resp["avg_hours"] else None

    # Top templates
    templates = await _fetch_all(
        """SELECT template_id, COUNT(*) AS sent,
                  SUM(CASE WHEN lead_username IN (
                    SELECT DISTINCT lead_username FROM messages WHERE direction = 'inbound'
                  ) THEN 1 ELSE 0 END) AS replied
           FROM messages
           WHERE direction = 'outbound' AND template_id IS NOT NULL
           GROUP BY template_id
           ORDER BY sent DESC LIMIT 10"""
    )
    top_templates = []
    for t in templates:
        rate = round(t["replied"] / t["sent"] * 100, 1) if t["sent"] > 0 else 0.0
        top_templates.append({
            "template_id": t["template_id"],
            "sent": t["sent"],
            "replied": t["replied"],
            "reply_rate": rate,
        })

    return {
        "total_leads": total_leads,
        "contacted": contacted,
        "reply_rate": reply_rate,
        "engagement_rate": engagement_rate,
        "conversion_rate": conversion_rate,
        "messages_sent_today": msgs_today,
        "messages_sent_week": msgs_week,
        "messages_sent_month": msgs_month,
        "avg_response_time_hours": avg_response_hours,
        "top_templates": top_templates,
    }


_HTML = """\
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AdFlux — Campaign Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  darkMode: 'class',
  theme: { extend: { colors: {
    brand:  '#10b981',
    bgDark: '#111827',
    card:   '#1f2937',
    card2:  '#374151',
  }}}
}
</script>
<style>
body { background: #111827; }
.loader { border:3px solid #374151; border-top:3px solid #10b981; border-radius:50%;
           width:24px; height:24px; animation:spin .8s linear infinite; display:inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
.bar { transition: width .6s ease; }
.live-dot { width:8px; height:8px; border-radius:50%; background:#10b981; display:inline-block;
            animation: pulse-dot 2s ease-in-out infinite; }
@keyframes pulse-dot { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
.ws-event { animation: slideIn 0.3s ease-out; }
@keyframes slideIn { from { opacity:0; transform:translateY(-10px); } to { opacity:1; transform:translateY(0); } }
</style>
</head>
<body class="bg-bgDark text-gray-200 min-h-screen">

<!-- NAV -->
<nav class="border-b border-gray-700 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-emerald-400 text-2xl font-bold tracking-tight">⚡ AdFlux</span>
      <span class="text-gray-400 text-sm hidden sm:inline">Campaign Dashboard</span>
    </div>
    <div class="flex items-center gap-3">
      <span class="live-dot" id="ws-dot" title="WebSocket"></span>
      <span id="ws-status" class="text-xs text-gray-500">connecting…</span>
      <span id="health-dot" class="w-2.5 h-2.5 rounded-full bg-gray-600"></span>
      <span id="clock" class="text-xs text-gray-500 font-mono"></span>
      <a href="/funnel" class="text-xs bg-purple-600 hover:bg-purple-500 px-3 py-1 rounded font-medium">📊 Funnel</a>
      <button onclick="refreshAll()" class="text-xs bg-emerald-600 hover:bg-emerald-500 px-3 py-1 rounded font-medium">↻ Refresh</button>
    </div>
  </div>
</nav>

<main class="max-w-7xl mx-auto px-4 py-6 space-y-6">

<!-- SEARCH BAR -->
<section class="flex gap-3">
  <div class="flex-1 relative">
    <input id="search-input" type="text" placeholder="Search leads by username, notes, source…"
           class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-emerald-500"
           onkeyup="if(event.key==='Enter')searchLeads()"/>
    <button onclick="searchLeads()" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white text-sm">🔍</button>
  </div>
</section>
<div id="search-results" class="hidden bg-card rounded-xl border border-gray-700 p-4">
  <div class="flex justify-between items-center mb-3">
    <h3 class="text-sm font-semibold text-gray-300">Search Results</h3>
    <button onclick="$('#search-results').classList.add('hidden')" class="text-xs text-gray-500 hover:text-white">✕ Close</button>
  </div>
  <div id="search-list" class="space-y-2 max-h-60 overflow-y-auto"></div>
</div>

<!-- SUMMARY CARDS -->
<section id="cards" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
  <div class="bg-card rounded-xl p-4 border border-gray-700">
    <p class="text-xs text-gray-400 uppercase tracking-wide">Total Leads</p>
    <p id="c-leads" class="text-2xl font-bold text-white mt-1">—</p>
  </div>
  <div class="bg-card rounded-xl p-4 border border-gray-700">
    <p class="text-xs text-gray-400 uppercase tracking-wide">Messages Sent</p>
    <p id="c-msgs" class="text-2xl font-bold text-white mt-1">—</p>
  </div>
  <div class="bg-card rounded-xl p-4 border border-gray-700">
    <p class="text-xs text-gray-400 uppercase tracking-wide">Replies</p>
    <p id="c-replies" class="text-2xl font-bold text-white mt-1">—</p>
    <p id="c-reply-rate" class="text-xs text-emerald-400 mt-0.5"></p>
  </div>
  <div class="bg-card rounded-xl p-4 border border-gray-700">
    <p class="text-xs text-gray-400 uppercase tracking-wide">Hot Leads 🔥</p>
    <p id="c-hot" class="text-2xl font-bold text-emerald-400 mt-1">—</p>
  </div>
  <div class="bg-card rounded-xl p-4 border border-gray-700">
    <p class="text-xs text-gray-400 uppercase tracking-wide">Engagement</p>
    <p id="c-engagement" class="text-2xl font-bold text-cyan-400 mt-1">—</p>
  </div>
  <div class="bg-card rounded-xl p-4 border border-gray-700">
    <p class="text-xs text-gray-400 uppercase tracking-wide">Accounts Active</p>
    <p id="c-active" class="text-2xl font-bold text-white mt-1">—</p>
    <p id="c-banned" class="text-xs text-red-400 mt-0.5"></p>
  </div>
</section>

<!-- METRICS ROW -->
<section class="grid grid-cols-2 md:grid-cols-4 gap-4">
  <div class="bg-gradient-to-br from-indigo-900/50 to-card rounded-xl p-4 border border-indigo-800/30">
    <p class="text-xs text-indigo-300 uppercase">Today</p>
    <p id="m-today" class="text-xl font-bold text-white mt-1">—</p>
    <p class="text-xs text-gray-500">messages sent</p>
  </div>
  <div class="bg-gradient-to-br from-purple-900/50 to-card rounded-xl p-4 border border-purple-800/30">
    <p class="text-xs text-purple-300 uppercase">This Week</p>
    <p id="m-week" class="text-xl font-bold text-white mt-1">—</p>
    <p class="text-xs text-gray-500">messages sent</p>
  </div>
  <div class="bg-gradient-to-br from-pink-900/50 to-card rounded-xl p-4 border border-pink-800/30">
    <p class="text-xs text-pink-300 uppercase">This Month</p>
    <p id="m-month" class="text-xl font-bold text-white mt-1">—</p>
    <p class="text-xs text-gray-500">messages sent</p>
  </div>
  <div class="bg-gradient-to-br from-emerald-900/50 to-card rounded-xl p-4 border border-emerald-800/30">
    <p class="text-xs text-emerald-300 uppercase">Avg Response</p>
    <p id="m-resp" class="text-xl font-bold text-white mt-1">—</p>
    <p class="text-xs text-gray-500">hours</p>
  </div>
</section>

<!-- THREE-COLUMN LAYOUT -->
<section class="grid lg:grid-cols-3 gap-6">

  <!-- MINI FUNNEL -->
  <div class="lg:col-span-1 bg-card rounded-xl border border-gray-700 p-5">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide">Lead Funnel</h2>
      <a href="/funnel" class="text-xs text-purple-400 hover:text-purple-300">Full view →</a>
    </div>
    <div id="funnel" class="space-y-2"></div>
  </div>

  <!-- LIVE ACTIVITY FEED -->
  <div class="lg:col-span-1 bg-card rounded-xl border border-gray-700 p-5">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide">
        <span class="live-dot mr-1"></span> Live Activity
      </h2>
      <span id="event-count" class="text-xs text-gray-500">0 events</span>
    </div>
    <ul id="live-feed" class="space-y-2 max-h-80 overflow-y-auto"></ul>
    <p id="live-empty" class="text-gray-500 text-sm text-center py-4">Waiting for events…</p>
  </div>

  <!-- ACCOUNT HEALTH TABLE -->
  <div class="lg:col-span-1 bg-card rounded-xl border border-gray-700 p-5 overflow-x-auto">
    <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4">Account Health</h2>
    <table class="w-full text-sm">
      <thead>
        <tr class="text-gray-500 text-xs uppercase">
          <th class="text-left py-2 px-1">Phone</th>
          <th class="text-left py-2 px-1">Status</th>
          <th class="text-right py-2 px-1">DMs</th>
          <th class="text-right py-2 px-1">Spam</th>
        </tr>
      </thead>
      <tbody id="acct-body" class="divide-y divide-gray-700/50"></tbody>
    </table>
    <p id="acct-empty" class="text-gray-500 text-sm text-center py-4 hidden">No accounts yet.</p>
  </div>

</section>

<!-- BOTTOM ROW -->
<section class="grid lg:grid-cols-2 gap-6">

  <!-- RECENT MESSAGES -->
  <div class="bg-card rounded-xl border border-gray-700 p-5">
    <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4">Recent Messages</h2>
    <ul id="activity" class="space-y-2 max-h-80 overflow-y-auto"></ul>
    <p id="activity-empty" class="text-gray-500 text-sm text-center py-4 hidden">No messages yet.</p>
  </div>

  <!-- TOP TEMPLATES -->
  <div class="bg-card rounded-xl border border-gray-700 p-5">
    <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4">Top Message Templates</h2>
    <div id="templates" class="space-y-2"></div>
    <p id="tpl-empty" class="text-gray-500 text-sm text-center py-4 hidden">No template data yet.</p>
  </div>

</section>

<!-- WARMING PROGRESS -->
<section class="bg-card rounded-xl border border-gray-700 p-5">
  <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4">Warming Progress</h2>
  <div id="warming" class="space-y-3"></div>
  <p id="warming-empty" class="text-gray-500 text-sm text-center py-4 hidden">No warming data yet.</p>
</section>

</main>

<footer class="text-center text-xs text-gray-600 py-6">AdFlux Media · Dashboard v2.0</footer>

<script>
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);

function fmtTs(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  return d.toLocaleString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
}

const STATUS_COLORS = {
  fresh:'bg-blue-500/20 text-blue-300',
  warming:'bg-yellow-500/20 text-yellow-300',
  ready:'bg-emerald-500/20 text-emerald-300',
  active:'bg-green-500/20 text-green-300',
  banned:'bg-red-500/20 text-red-300',
  resting:'bg-purple-500/20 text-purple-300',
};

const FUNNEL_STAGES = [
  {name:'New', color:'#6366f1'}, {name:'Contacted', color:'#8b5cf6'},
  {name:'Replied', color:'#a855f7'}, {name:'Engaged', color:'#d946ef'},
  {name:'Qualified', color:'#ec4899'}, {name:'Hot', color:'#f43f5e'},
  {name:'Payment Sent', color:'#f97316'}, {name:'Converted', color:'#eab308'},
  {name:'Onboarded', color:'#22c55e'},
];

// ── WebSocket ──
let ws = null;
let eventCount = 0;

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onopen = () => {
    $('#ws-status').textContent = 'live';
    $('#ws-dot').style.background = '#10b981';
  };
  ws.onclose = () => {
    $('#ws-status').textContent = 'reconnecting…';
    $('#ws-dot').style.background = '#ef4444';
    setTimeout(connectWS, 3000);
  };
  ws.onerror = () => { ws.close(); };
  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === 'pong') return;
      addLiveEvent(msg);
    } catch(e) {}
  };
}

function addLiveEvent(msg) {
  const feed = $('#live-feed');
  $('#live-empty').classList.add('hidden');
  eventCount++;
  $('#event-count').textContent = eventCount + ' events';

  const icons = {
    reply_received: '📥', stage_change: '🔄', bant_update: '📊',
    lead_contacted: '📤', lead_assigned: '🔗',
  };
  const icon = icons[msg.type] || '⚡';
  const detail = msg.data ? JSON.stringify(msg.data).slice(0, 100) : '';

  const li = document.createElement('li');
  li.className = 'ws-event flex items-start gap-2 text-xs bg-gray-800/50 rounded-lg p-2';
  li.innerHTML = `<span>${icon}</span>
    <div class="min-w-0">
      <span class="text-emerald-400 font-medium">${msg.type}</span>
      <span class="text-gray-500 ml-1">${fmtTs(msg.timestamp)}</span>
      <p class="text-gray-400 truncate">${detail}</p>
    </div>`;
  feed.insertBefore(li, feed.firstChild);

  // Keep max 20 events
  while (feed.children.length > 20) feed.removeChild(feed.lastChild);
}

connectWS();
// Ping to keep alive
setInterval(() => { if (ws && ws.readyState === 1) ws.send('ping'); }, 30000);

// ── Data loaders ──

async function loadStats() {
  try {
    const s = await (await fetch('/api/stats')).json();
    $('#c-leads').textContent   = s.total_leads.toLocaleString();
    $('#c-msgs').textContent    = s.total_messages_sent.toLocaleString();
    $('#c-replies').textContent = s.total_replies.toLocaleString();
    $('#c-reply-rate').textContent = s.reply_rate + '% reply rate';
    $('#c-hot').textContent     = s.hot_leads.toLocaleString();
    $('#c-active').textContent  = s.active_accounts.toLocaleString();
    $('#c-banned').textContent  = s.banned_accounts > 0 ? s.banned_accounts + ' banned' : '';
  } catch(e) { console.error('stats', e); }
}

async function loadMetrics() {
  try {
    const m = await (await fetch('/api/metrics')).json();
    $('#m-today').textContent = m.messages_sent_today.toLocaleString();
    $('#m-week').textContent  = m.messages_sent_week.toLocaleString();
    $('#m-month').textContent = m.messages_sent_month.toLocaleString();
    $('#m-resp').textContent  = m.avg_response_time_hours != null ? m.avg_response_time_hours + 'h' : 'N/A';
    $('#c-engagement').textContent = m.engagement_rate + '%';
  } catch(e) { console.error('metrics', e); }
}

async function loadAccounts() {
  try {
    const rows = await (await fetch('/api/accounts')).json();
    const body = $('#acct-body');
    body.innerHTML = '';
    if (!rows.length) { $('#acct-empty').classList.remove('hidden'); return; }
    $('#acct-empty').classList.add('hidden');
    rows.forEach(r => {
      const cls = STATUS_COLORS[r.status] || 'bg-gray-600/20 text-gray-300';
      body.insertAdjacentHTML('beforeend', `
        <tr class="hover:bg-gray-800/40">
          <td class="py-2 px-1 font-mono text-xs">${r.phone}</td>
          <td class="py-2 px-1"><span class="px-2 py-0.5 rounded-full text-xs font-medium ${cls}">${r.status}</span></td>
          <td class="py-2 px-1 text-right">${r.total_dms_sent}</td>
          <td class="py-2 px-1 text-right ${r.spam_reports > 0 ? 'text-red-400' : ''}">${r.spam_reports}</td>
        </tr>`);
    });
  } catch(e) { console.error('accounts', e); }
}

async function loadFunnel() {
  try {
    const data = await (await fetch('/api/funnel')).json();
    const container = $('#funnel');
    container.innerHTML = '';
    const maxCount = Math.max(...data.stages.map(s => s.count), 1);
    data.stages.forEach(s => {
      const pct = (s.count / maxCount * 100) || 0.5;
      container.insertAdjacentHTML('beforeend', `
        <div>
          <div class="flex justify-between text-xs mb-0.5">
            <span>${s.name}</span>
            <span class="text-gray-400">${s.count.toLocaleString()}</span>
          </div>
          <div class="w-full bg-gray-700 rounded-full h-2">
            <div class="bar h-2 rounded-full" style="width:${Math.max(pct, 0.5)}%; background:${s.color}"></div>
          </div>
        </div>`);
    });
  } catch(e) { console.error('funnel', e); }
}

async function loadActivity() {
  try {
    const rows = await (await fetch('/api/messages?limit=20')).json();
    const ul = $('#activity');
    ul.innerHTML = '';
    if (!rows.length) { $('#activity-empty').classList.remove('hidden'); return; }
    $('#activity-empty').classList.add('hidden');
    rows.forEach(m => {
      const icon = m.direction === 'outbound' ? '📤' : '📥';
      const color = m.direction === 'outbound' ? 'text-blue-400' : 'text-emerald-400';
      const preview = m.text.length > 80 ? m.text.slice(0, 80) + '…' : m.text;
      ul.insertAdjacentHTML('beforeend', `
        <li class="flex items-start gap-2 text-xs">
          <span>${icon}</span>
          <div class="min-w-0">
            <span class="${color} font-medium">@${m.lead_username}</span>
            <span class="text-gray-500 ml-1">${fmtTs(m.sent_at)}</span>
            <p class="text-gray-400 truncate">${preview}</p>
          </div>
        </li>`);
    });
  } catch(e) { console.error('activity', e); }
}

async function loadTemplates() {
  try {
    const rows = await (await fetch('/api/messages?limit=500')).json();
    const container = $('#templates');
    container.innerHTML = '';
    const outbound = rows.filter(m => m.direction === 'outbound' && m.template_id);
    if (!outbound.length) { $('#tpl-empty').classList.remove('hidden'); return; }
    $('#tpl-empty').classList.add('hidden');
    const tplMap = {};
    outbound.forEach(m => {
      if (!tplMap[m.template_id]) tplMap[m.template_id] = {sent:0, replied:0};
      tplMap[m.template_id].sent++;
    });
    const inbound = rows.filter(m => m.direction === 'inbound');
    const repliedLeads = new Set(inbound.map(m => m.lead_username));
    outbound.forEach(m => {
      if (repliedLeads.has(m.lead_username) && tplMap[m.template_id])
        tplMap[m.template_id].replied++;
    });
    const sorted = Object.entries(tplMap).sort((a,b) => b[1].sent - a[1].sent).slice(0, 10);
    sorted.forEach(([id, d]) => {
      const rate = d.sent > 0 ? (d.replied / d.sent * 100).toFixed(1) : 0;
      container.insertAdjacentHTML('beforeend', `
        <div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-3 py-2">
          <span class="font-mono text-xs text-gray-300">${id}</span>
          <div class="flex gap-4 text-xs">
            <span class="text-gray-400">${d.sent} sent</span>
            <span class="text-emerald-400">${rate}% reply</span>
          </div>
        </div>`);
    });
  } catch(e) { console.error('templates', e); }
}

async function loadWarming() {
  try {
    const rows = await (await fetch('/api/warming')).json();
    const container = $('#warming');
    container.innerHTML = '';
    const warmingRows = rows.filter(r => r.current_day > 0 || r.status === 'warming');
    if (!warmingRows.length) { $('#warming-empty').classList.remove('hidden'); return; }
    $('#warming-empty').classList.add('hidden');
    warmingRows.forEach(r => {
      const pct = Math.min((r.current_day / r.total_days) * 100, 100);
      const done = r.current_day >= r.total_days;
      container.insertAdjacentHTML('beforeend', `
        <div class="bg-gray-800/50 rounded-lg p-3">
          <div class="flex justify-between text-xs mb-1">
            <span class="font-mono text-gray-300">${r.phone}</span>
            <span class="${done ? 'text-emerald-400' : 'text-yellow-400'}">${done ? '✓ Complete' : 'Day ' + r.current_day + '/14'}</span>
          </div>
          <div class="w-full bg-gray-700 rounded-full h-2 mb-1">
            <div class="bar ${done ? 'bg-emerald-500' : 'bg-yellow-500'} h-2 rounded-full" style="width:${pct}%"></div>
          </div>
          <div class="flex gap-3 text-xs text-gray-500">
            <span>Groups: ${r.groups_joined}</span>
            <span>Msgs: ${r.messages_sent}</span>
            <span>Read: ${r.channels_read}</span>
            <span>Reacts: ${r.reactions}</span>
          </div>
        </div>`);
    });
  } catch(e) { console.error('warming', e); }
}

async function loadHealth() {
  try {
    const h = await (await fetch('/api/health')).json();
    const dot = $('#health-dot');
    dot.className = 'w-2.5 h-2.5 rounded-full ' + (h.status === 'healthy' ? 'bg-emerald-400' : 'bg-red-400');
  } catch(e) { $('#health-dot').className = 'w-2.5 h-2.5 rounded-full bg-red-400'; }
}

async function searchLeads() {
  const q = $('#search-input').value.trim();
  if (!q) return;
  try {
    const data = await (await fetch('/api/leads/search?q=' + encodeURIComponent(q))).json();
    const list = $('#search-list');
    list.innerHTML = '';
    $('#search-results').classList.remove('hidden');
    if (!data.results.length) { list.innerHTML = '<p class="text-gray-500 text-sm">No results found.</p>'; return; }
    data.results.forEach(r => {
      list.insertAdjacentHTML('beforeend', `
        <div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-3 py-2">
          <div>
            <span class="text-emerald-400 font-mono text-sm">@${r.username}</span>
            <span class="text-xs text-gray-500 ml-2">${r.source}</span>
          </div>
          <div class="flex gap-3 text-xs">
            <span class="text-gray-400">${r.status}</span>
            <span class="text-yellow-400">BANT: ${r.bant_score}</span>
          </div>
        </div>`);
    });
  } catch(e) { console.error('search', e); }
}

function updateClock() {
  $('#clock').textContent = new Date().toLocaleTimeString('en-US', {hour12:false});
}

async function refreshAll() {
  await Promise.all([loadStats(), loadMetrics(), loadAccounts(), loadFunnel(), loadActivity(), loadTemplates(), loadWarming(), loadHealth()]);
}

updateClock();
setInterval(updateClock, 1000);
refreshAll();
setInterval(refreshAll, 30000);
</script>
</body>
</html>
"""


# ── Funnel Page HTML ───────────────────────────────────────────────────────

_FUNNEL_HTML = """\
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AdFlux — Funnel Visualization</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
tailwind.config = { darkMode: 'class', theme: { extend: { colors: { bgDark: '#111827', card: '#1f2937' }}}}
</script>
<style>body { background: #111827; }</style>
</head>
<body class="bg-bgDark text-gray-200 min-h-screen">
<nav class="border-b border-gray-700 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
  <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <a href="/" class="text-emerald-400 text-xl font-bold">⚡ AdFlux</a>
      <span class="text-gray-400 text-sm">/ Funnel</span>
    </div>
    <a href="/" class="text-xs bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded font-medium">← Dashboard</a>
  </div>
</nav>
<main class="max-w-5xl mx-auto px-4 py-8 space-y-8">
  <div class="bg-card rounded-xl border border-gray-700 p-6">
    <h2 class="text-lg font-bold text-white mb-6">9-Stage Lead Funnel</h2>
    <canvas id="funnelChart" height="400"></canvas>
  </div>
  <div class="grid md:grid-cols-2 gap-6">
    <div class="bg-card rounded-xl border border-gray-700 p-5">
      <h3 class="text-sm font-semibold text-gray-300 uppercase mb-4">Stage Breakdown</h3>
      <div id="stage-cards" class="space-y-3"></div>
    </div>
    <div class="bg-card rounded-xl border border-gray-700 p-5">
      <h3 class="text-sm font-semibold text-gray-300 uppercase mb-4">Conversion Rates</h3>
      <div id="conv-rates" class="space-y-3"></div>
    </div>
  </div>
</main>
<script>
async function loadFunnel() {
  const data = await (await fetch('/api/funnel')).json();
  const labels = data.stages.map(s => s.name);
  const counts = data.stages.map(s => s.count);
  const colors = data.stages.map(s => s.color);

  const ctx = document.getElementById('funnelChart').getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Leads',
        data: counts,
        backgroundColor: colors.map(c => c + 'cc'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 6,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1f2937',
          titleColor: '#e5e7eb',
          bodyColor: '#9ca3af',
          borderColor: '#374151',
          borderWidth: 1,
        }
      },
      scales: {
        x: {
          grid: { color: '#374151' },
          ticks: { color: '#9ca3af' },
        },
        y: {
          grid: { display: false },
          ticks: { color: '#e5e7eb', font: { size: 13, weight: 'bold' } },
        }
      }
    }
  });

  // Stage cards
  const cards = document.getElementById('stage-cards');
  const total = data.total || 1;
  data.stages.forEach(s => {
    const pct = (s.count / total * 100).toFixed(1);
    cards.insertAdjacentHTML('beforeend', `
      <div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-3">
        <div class="flex items-center gap-3">
          <span class="w-3 h-3 rounded-full" style="background:${s.color}"></span>
          <span class="text-sm font-medium text-white">${s.name}</span>
        </div>
        <div class="text-right">
          <span class="text-lg font-bold text-white">${s.count.toLocaleString()}</span>
          <span class="text-xs text-gray-500 ml-1">(${pct}%)</span>
        </div>
      </div>`);
  });

  // Conversion rates
  const conv = document.getElementById('conv-rates');
  Object.entries(data.conversion_rates).forEach(([key, rate]) => {
    const [from, to] = key.split('_to_');
    const barColor = rate > 50 ? '#22c55e' : rate > 20 ? '#eab308' : rate > 0 ? '#f97316' : '#6b7280';
    conv.insertAdjacentHTML('beforeend', `
      <div class="bg-gray-800/50 rounded-lg px-4 py-3">
        <div class="flex justify-between text-xs mb-1">
          <span class="text-gray-400">${from} → ${to}</span>
          <span class="font-bold" style="color:${barColor}">${rate}%</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-1.5">
          <div class="h-1.5 rounded-full" style="width:${Math.max(rate, 0.5)}%; background:${barColor}"></div>
        </div>
      </div>`);
  });
}
loadFunnel();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _HTML


@app.get("/funnel", response_class=HTMLResponse)
async def funnel_page():
    return _FUNNEL_HTML


# ── Uvicorn runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
