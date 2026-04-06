"""Order manager — SQLite-backed order tracking for the Kliqboost bot.

DB location: bridge/orders.db (shared between bot + autoresponder)
Order code format: KLQ-YYYYMMDD-XXXX (daily sequential)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

ORDERS_DB = Path("/home/cjs/kliqboost/bridge/orders.db")

# ── Order statuses ───────────────────────────────────────────────────────
STATUS_PENDING = "pending_payment"
STATUS_SUBMITTED = "payment_submitted"
STATUS_VERIFIED = "payment_verified"
STATUS_PROCESSING = "processing"
STATUS_DELIVERED = "delivered"
STATUS_CANCELLED = "cancelled"
STATUS_ADMIN_REVIEW = "admin_review"


def _conn() -> sqlite3.Connection:
    ORDERS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ORDERS_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            platform TEXT,
            niche TEXT,
            amount_usd REAL DEFAULT 0,
            crypto_amount REAL DEFAULT 0,
            crypto_currency TEXT,
            tx_hash TEXT,
            wallet_address TEXT,
            status TEXT DEFAULT 'pending_payment',
            admin_confirmed INTEGER DEFAULT 0,
            created_at REAL,
            paid_at REAL,
            verified_at REAL,
            delivered_at REAL,
            notes TEXT
        )
    """)
    conn.commit()
    return conn


def _generate_order_code(conn: sqlite3.Connection) -> str:
    """Generate KLQ-YYYYMMDD-XXXX code, sequential within the day."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"KLQ-{today}-"
    row = conn.execute(
        "SELECT order_code FROM orders WHERE order_code LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    if row:
        last_seq = int(row["order_code"].split("-")[-1])
        seq = last_seq + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def create_order(
    user_id: int,
    username: str = "",
    full_name: str = "",
    platform: str = "",
    niche: str = "",
    amount_usd: float = 0,
) -> dict:
    """Create a new order and return it as a dict."""
    conn = _conn()
    code = _generate_order_code(conn)
    now = time.time()
    conn.execute(
        """INSERT INTO orders
           (order_code, user_id, username, full_name, platform, niche, amount_usd, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, user_id, username, full_name, platform, niche, amount_usd, STATUS_PENDING, now),
    )
    conn.commit()
    order = dict(conn.execute("SELECT * FROM orders WHERE order_code = ?", (code,)).fetchone())
    conn.close()
    log.info("Order created: %s for uid=%d amount=$%.2f", code, user_id, amount_usd)
    return order


def update_payment(
    order_code: str,
    crypto_currency: str,
    crypto_amount: float,
    wallet_address: str,
) -> None:
    """Record which payment method the user chose."""
    conn = _conn()
    conn.execute(
        """UPDATE orders SET crypto_currency = ?, crypto_amount = ?,
           wallet_address = ?, status = ? WHERE order_code = ?""",
        (crypto_currency, crypto_amount, wallet_address, STATUS_PENDING, order_code),
    )
    conn.commit()
    conn.close()


def submit_tx_hash(order_code: str, tx_hash: str) -> None:
    """User submitted a transaction hash — mark as submitted."""
    conn = _conn()
    conn.execute(
        "UPDATE orders SET tx_hash = ?, status = ?, paid_at = ? WHERE order_code = ?",
        (tx_hash, STATUS_SUBMITTED, time.time(), order_code),
    )
    conn.commit()
    conn.close()
    log.info("TX hash submitted for %s: %s", order_code, tx_hash[:20])


def confirm_payment(
    order_code: str,
    crypto_amount: float = 0,
    amount_usd: float = 0,
) -> None:
    """Mark payment as verified (on-chain confirmed)."""
    conn = _conn()
    updates = ["status = ?", "verified_at = ?"]
    params: list = [STATUS_VERIFIED, time.time()]
    if crypto_amount > 0:
        updates.append("crypto_amount = ?")
        params.append(crypto_amount)
    if amount_usd > 0:
        updates.append("amount_usd = ?")
        params.append(amount_usd)
    params.append(order_code)
    conn.execute(f"UPDATE orders SET {', '.join(updates)} WHERE order_code = ?", params)
    conn.commit()
    conn.close()
    log.info("Payment verified for %s", order_code)


def set_admin_review(order_code: str) -> None:
    """Mark order as needing admin confirmation (> threshold)."""
    conn = _conn()
    conn.execute(
        "UPDATE orders SET status = ? WHERE order_code = ?",
        (STATUS_ADMIN_REVIEW, order_code),
    )
    conn.commit()
    conn.close()


def admin_confirm(order_code: str, confirmed: bool) -> None:
    """Admin confirms or rejects a large order."""
    conn = _conn()
    if confirmed:
        conn.execute(
            "UPDATE orders SET admin_confirmed = 1, status = ? WHERE order_code = ?",
            (STATUS_VERIFIED, order_code),
        )
    else:
        conn.execute(
            "UPDATE orders SET admin_confirmed = 0, status = ? WHERE order_code = ?",
            (STATUS_CANCELLED, order_code),
        )
    conn.commit()
    conn.close()


def mark_processing(order_code: str) -> None:
    conn = _conn()
    conn.execute("UPDATE orders SET status = ? WHERE order_code = ?", (STATUS_PROCESSING, order_code))
    conn.commit()
    conn.close()


def mark_delivered(order_code: str) -> None:
    conn = _conn()
    conn.execute(
        "UPDATE orders SET status = ?, delivered_at = ? WHERE order_code = ?",
        (STATUS_DELIVERED, time.time(), order_code),
    )
    conn.commit()
    conn.close()


def get_order(order_code: str) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_order_by_id(order_id: int) -> dict | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id: int, limit: int = 10) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_verifications() -> list[dict]:
    """Get orders awaiting tx verification (for auto-recheck loop)."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE status = ? AND tx_hash IS NOT NULL",
        (STATUS_SUBMITTED,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_order(user_id: int) -> dict | None:
    """Get the user's most recent non-terminal order."""
    conn = _conn()
    row = conn.execute(
        """SELECT * FROM orders WHERE user_id = ? AND status NOT IN (?, ?, ?)
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, STATUS_DELIVERED, STATUS_CANCELLED, STATUS_VERIFIED),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
