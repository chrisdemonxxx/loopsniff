"""Campaign monitoring dashboard for throwaway TG outreach.

FastAPI app serving a real-time HTML dashboard and JSON APIs for session pool,
message pool, target pool, and burn-log statistics.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

app = FastAPI(title="TG Throwaway Outreach Dashboard")

DB_PATH = str(Path(__file__).resolve().parent / "data" / "outreach.db")

# ---------------------------------------------------------------------------
# Ensure tables exist so the dashboard never crashes on a fresh DB
# ---------------------------------------------------------------------------

_BOOTSTRAP = """
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

CREATE TABLE IF NOT EXISTS targets (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    last_name     TEXT,
    phone         TEXT,
    is_premium    INTEGER DEFAULT 0,
    last_seen     TEXT,
    source_group  TEXT,
    access_hash   INTEGER DEFAULT 0,
    scraped_at    TEXT,
    status        TEXT DEFAULT 'pending',
    messaged_at   TEXT,
    messaged_by   TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_pool (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id    TEXT    NOT NULL,
    text           TEXT    NOT NULL,
    hash           TEXT    UNIQUE NOT NULL,
    source         TEXT    DEFAULT 'llm',
    used           INTEGER DEFAULT 0,
    used_at        TEXT,
    target_user_id INTEGER,
    session_phone  TEXT,
    created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
);
"""


@app.on_event("startup")
async def _bootstrap_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_BOOTSTRAP)
        await db.commit()
    logger.info("Dashboard DB bootstrap complete: {}", DB_PATH)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TG Throwaway Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;padding:24px}
h1{font-size:1.6rem;margin-bottom:20px;color:#58a6ff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-bottom:24px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px}
.card h2{font-size:1rem;color:#8b949e;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
.stat-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #21262d}
.stat-row:last-child{border-bottom:none}
.label{color:#8b949e}
.val{font-weight:600;font-variant-numeric:tabular-nums}
.green{color:#3fb950}.blue{color:#58a6ff}.yellow{color:#d29922}.red{color:#f85149}.gray{color:#8b949e}
.total{color:#c9d1d9;font-size:1.1rem}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:.85rem}
th{text-align:left;color:#8b949e;padding:6px 8px;border-bottom:1px solid #30363d}
td{padding:6px 8px;border-bottom:1px solid #21262d}
.ts{font-size:.8rem;color:#8b949e;margin-top:16px;text-align:right}
#status{font-size:.75rem;color:#3fb950;float:right}
</style>
</head>
<body>
<h1>📡 TG Throwaway Outreach <span id="status">● live</span></h1>

<div class="grid">
  <!-- Sessions card -->
  <div class="card">
    <h2>📱 Session Pool</h2>
    <div id="sessions-stats">Loading…</div>
  </div>
  <!-- Targets card -->
  <div class="card">
    <h2>🎯 Targets</h2>
    <div id="targets-stats">Loading…</div>
  </div>
  <!-- Messages card -->
  <div class="card">
    <h2>💬 Message Pools</h2>
    <div id="messages-stats">Loading…</div>
  </div>
</div>

<!-- Burn log -->
<div class="card" style="margin-bottom:24px">
  <h2>🔥 Recent Burns</h2>
  <div id="burn-log">Loading…</div>
</div>

<div class="ts" id="updated"></div>

<script>
function sr(label,val,cls){return `<div class="stat-row"><span class="label">${label}</span><span class="val ${cls}">${val}</span></div>`}
function renderSessions(s){
  return sr('Fresh',s.fresh,'green')+sr('Active',s.active,'blue')+sr('Resting',s.resting,'yellow')+sr('Burned',s.burned,'red')+sr('Banned',s.banned,'red')+sr('Total',s.total,'total');
}
function renderTargets(t){
  return sr('Pending',t.pending,'green')+sr('Messaged',t.messaged,'blue')+sr('Replied',t.replied,'green')+sr('Skipped',t.skipped,'yellow')+sr('Failed',t.failed,'red')+sr('Total',t.total,'total');
}
function renderMessages(pools){
  if(!pools||pools.length===0) return '<span class="gray">No message pools yet</span>';
  let h='<table><tr><th>Campaign</th><th>Total</th><th>Remaining</th><th>Used</th></tr>';
  pools.forEach(p=>{h+=`<tr><td>${p.campaign_id}</td><td>${p.total}</td><td class="green">${p.remaining}</td><td class="gray">${p.used}</td></tr>`});
  return h+'</table>';
}
async function refresh(){
  try{
    const r=await fetch('/api/stats');
    const d=await r.json();
    document.getElementById('sessions-stats').innerHTML=renderSessions(d.sessions);
    document.getElementById('targets-stats').innerHTML=renderTargets(d.targets);
    document.getElementById('messages-stats').innerHTML=renderMessages(d.messages);
    document.getElementById('updated').textContent='Updated: '+new Date(d.timestamp+'Z').toLocaleString();
    document.getElementById('status').style.color='#3fb950';
    document.getElementById('status').textContent='● live';
  }catch(e){
    document.getElementById('status').style.color='#f85149';
    document.getElementById('status').textContent='● offline';
  }
}
async function loadBurns(){
  try{
    const r=await fetch('/api/burn-log');
    const rows=await r.json();
    if(!rows.length){document.getElementById('burn-log').innerHTML='<span class="gray">No burns yet</span>';return}
    let h='<table><tr><th>Phone</th><th>Reason</th><th>Msgs Sent</th><th>Burned At</th></tr>';
    rows.forEach(b=>{h+=`<tr><td>${b.phone||'—'}</td><td class="red">${b.burn_reason||'—'}</td><td>${b.messages_sent||0}</td><td class="gray">${b.burned_at||'—'}</td></tr>`});
    document.getElementById('burn-log').innerHTML=h+'</table>';
  }catch(e){}
}
refresh();loadBurns();
setInterval(refresh,10000);
setInterval(loadBurns,30000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Main dashboard with campaign overview."""
    return _HTML


# ---------------------------------------------------------------------------
# JSON APIs
# ---------------------------------------------------------------------------


@app.get("/api/stats")
async def api_stats():
    """Aggregated stats for the dashboard."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Session pool stats
        sessions: dict[str, int] = {}
        for state in ("fresh", "active", "resting", "burned", "banned"):
            cur = await db.execute(
                "SELECT COUNT(*) AS c FROM session_pool WHERE state = ?", (state,)
            )
            row = await cur.fetchone()
            sessions[state] = row[0] if row else 0
        sessions["total"] = sum(sessions.values())

        # Message pool stats (per campaign)
        cur = await db.execute(
            """SELECT campaign_id,
                      COUNT(*) AS total,
                      SUM(CASE WHEN used = 0 THEN 1 ELSE 0 END) AS remaining,
                      SUM(CASE WHEN used = 1 THEN 1 ELSE 0 END) AS used
               FROM message_pool
               GROUP BY campaign_id"""
        )
        message_pools = [dict(row) for row in await cur.fetchall()]

        # Target stats
        target_stats: dict[str, int] = {}
        for status in ("pending", "messaged", "skipped", "replied", "failed"):
            cur = await db.execute(
                "SELECT COUNT(*) AS c FROM targets WHERE status = ?", (status,)
            )
            row = await cur.fetchone()
            target_stats[status] = row[0] if row else 0
        target_stats["total"] = sum(target_stats.values())

    return JSONResponse(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "sessions": sessions,
            "messages": message_pools,
            "targets": target_stats,
        }
    )


@app.get("/api/sessions")
async def api_sessions():
    """List all sessions with their status."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT phone, state, messages_sent, batch_messages,
                      device_model, last_used, burned_at, burn_reason
               FROM session_pool ORDER BY created_at DESC"""
        )
        rows = await cur.fetchall()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/burn-log")
async def api_burn_log():
    """Recent session burns with reasons."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT phone, burn_reason, burned_at, messages_sent
               FROM session_pool
               WHERE state IN ('burned', 'banned')
               ORDER BY burned_at DESC LIMIT 50"""
        )
        rows = await cur.fetchall()
    return JSONResponse([dict(r) for r in rows])
