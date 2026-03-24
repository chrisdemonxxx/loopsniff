"""Orchestrates syncing outreach leads to Google Sheets and Notion."""

from __future__ import annotations

import os
import sqlite3
import time

from .config import OUTREACH_DB_PATH
from .sheets_sync import SheetsSync
from .notion_sync import NotionSync


class CRMSync:
    """Coordinate syncing between the outreach SQLite DB, Google Sheets, and Notion."""

    def __init__(self) -> None:
        self.sheets = SheetsSync()
        self.notion = NotionSync()
        self._db_path = os.path.realpath(OUTREACH_DB_PATH)

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _read_leads(self) -> list[dict]:
        """Read all leads from the outreach SQLite database, enriched with
        message counts and last-contact timestamps."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM leads").fetchall()
            leads: list[dict] = []
            for r in rows:
                lead = dict(r)
                # Derive messages_sent / last_contact from messages table
                try:
                    msg_stats = conn.execute(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE direction = 'outbound') AS msgs_sent,
                            MAX(CASE WHEN direction = 'outbound' THEN sent_at END) AS last_out,
                            MAX(sent_at) AS last_any
                        FROM messages
                        WHERE lead_username = ?
                        """,
                        (lead["username"],),
                    ).fetchone()
                    if msg_stats:
                        lead["messages_sent"] = msg_stats["msgs_sent"] or 0
                        lead["last_contact"] = msg_stats["last_out"] or msg_stats["last_any"] or ""
                except Exception:
                    lead["messages_sent"] = 0
                    lead["last_contact"] = ""
                # Map DB fields to CRM fields
                lead.setdefault("first_contact", lead.get("contacted_at", ""))
                lead.setdefault("replies", lead.get("reply_count", 0))
                lead.setdefault("budget", lead.get("budget_tier", ""))
                leads.append(lead)
            return leads
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Sync operations
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Configure both destinations (create sheet, setup Notion DB)."""
        print("[CRM] Setting up Google Sheet …")
        try:
            self.sheets.ensure_sheet()
            print("[CRM] Google Sheet ready.")
        except Exception as exc:
            print(f"[CRM] Google Sheets setup failed: {exc}")

        print("[CRM] Setting up Notion database properties …")
        self.notion.setup_database()
        print("[CRM] Notion database ready.")

    def sync_from_db(self) -> None:
        """One-time sync: read outreach DB and push to both destinations."""
        print("[CRM] Reading leads from outreach DB …")
        leads = self._read_leads()
        print(f"[CRM] Found {len(leads)} lead(s).")

        if not leads:
            print("[CRM] No leads to sync.")
            return

        print("[CRM] Syncing to Google Sheets …")
        try:
            sheet_count = self.sheets.sync_all(leads)
            print(f"[CRM] Synced {sheet_count} lead(s) to Sheets.")
        except Exception as exc:
            print(f"[CRM] Sheets sync failed: {exc}")

        print("[CRM] Syncing to Notion …")
        notion_count = self.notion.sync_all(leads)
        print(f"[CRM] Synced {notion_count} lead(s) to Notion.")

    def sync_single_lead(self, username: str, data: dict | None = None) -> None:
        """Real-time sync of a single lead to both destinations."""
        if data is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT * FROM leads WHERE username = ?", (username,)
                ).fetchone()
                if not row:
                    print(f"[CRM] Lead '{username}' not found in DB.")
                    return
                data = dict(row)
                data.setdefault("first_contact", data.get("contacted_at", ""))
                data.setdefault("replies", data.get("reply_count", 0))
                data.setdefault("budget", data.get("budget_tier", ""))
            finally:
                conn.close()

        print(f"[CRM] Syncing lead '{username}' …")
        try:
            self.sheets.sync_lead(data)
        except Exception as exc:
            print(f"[CRM] Sheets sync failed for '{username}': {exc}")
        self.notion.sync_lead(data)
        print(f"[CRM] Lead '{username}' synced.")

    def run_continuous(self, interval: int = 300) -> None:
        """Sync every *interval* seconds (default 5 min). Runs forever."""
        print(f"[CRM] Starting continuous sync (every {interval}s). Ctrl+C to stop.")
        while True:
            try:
                self.sync_from_db()
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"[CRM] Sync error: {exc}")
            time.sleep(interval)
