"""Import and validate leads from local CSV / SQLite data sources."""

from __future__ import annotations

import asyncio
import csv
import logging
import re
import sqlite3
from pathlib import Path
from typing import List

from . import db
from .models import Lead

log = logging.getLogger(__name__)


class LeadLoader:
    """Load leads from various scraped data files into the outreach DB."""

    DATA_SOURCES = {
        "bhw": Path("/home/cjs/blackhatworld/verified_active_tg_handles.csv"),
        "aw": Path(
            "/home/cjs/aw-attendee-data/FINAL_EXPORT_V5/verified_telegram_handles.csv"
        ),
        "hackforums": Path("/home/cjs/hackforums/hackforums.db"),
        "exploit": Path(
            "/home/cjs/exploit_forum_scrapper/user_db_output/"
            "deep_database_20260226_022321.csv"
        ),
    }

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_username(raw: str) -> str | None:
        """Normalise a Telegram handle to a bare username (no @, no URL)."""
        if not raw:
            return None
        raw = raw.strip()
        # Strip full URLs
        raw = re.sub(r"https?://(t\.me|telegram\.me)/", "", raw)
        raw = raw.lstrip("@").strip("/").strip()
        # Must match Telegram username rules: 5-32 chars, a-z 0-9 _
        if not raw or len(raw) < 5:
            return None
        if not re.match(r"^[A-Za-z0-9_]{5,32}$", raw):
            return None
        return raw.lower()

    @staticmethod
    def detect_language(username: str, context: str = "") -> str:
        """Heuristic language detection: Cyrillic chars → 'ru', else 'en'."""
        text = username + " " + context
        cyrillic = len(re.findall(r"[\u0400-\u04FF]", text))
        return "ru" if cyrillic > 2 else "en"

    @staticmethod
    def _find_tg_column(headers: List[str]) -> int | None:
        """Auto-detect which CSV column contains Telegram handles."""
        patterns = [
            r"telegram",
            r"tg_handle",
            r"tg_username",
            r"tg",
            r"handle",
            r"contact_value",
        ]
        for idx, h in enumerate(headers):
            for p in patterns:
                if re.search(p, h, re.IGNORECASE):
                    return idx
        return None

    # ── loaders ─────────────────────────────────────────────────────────────

    async def load_bhw(self) -> int:
        """Load BlackHatWorld verified TG handles (~2 371 leads)."""
        path = self.DATA_SOURCES["bhw"]
        if not path.exists():
            log.warning("BHW source not found: %s", path)
            return 0
        leads: list[Lead] = []
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            headers = next(reader, None)
            col = self._find_tg_column(headers) if headers else 0
            if col is None:
                col = 0
            for row in reader:
                if len(row) <= col:
                    continue
                uname = self._clean_username(row[col])
                if uname:
                    leads.append(
                        Lead(username=uname, source="bhw",
                             language=self.detect_language(uname))
                    )
        inserted = await db.add_leads_bulk(leads)
        log.info("BHW: loaded %d / %d leads", inserted, len(leads))
        return inserted

    async def load_aw(self) -> int:
        """Load Affiliate World conference TG handles (~1 586 leads)."""
        path = self.DATA_SOURCES["aw"]
        if not path.exists():
            log.warning("AW source not found: %s", path)
            return 0
        leads: list[Lead] = []
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            headers = next(reader, None)
            col = self._find_tg_column(headers) if headers else 0
            if col is None:
                col = 0
            for row in reader:
                if len(row) <= col:
                    continue
                uname = self._clean_username(row[col])
                if not uname:
                    continue
                niche = None
                # Try to pick up enrichment data if extra columns exist
                if headers and len(row) > 1:
                    for idx, h in enumerate(headers):
                        if re.search(r"niche|vertical|industry", h, re.IGNORECASE):
                            niche = row[idx].strip() if idx < len(row) else None
                leads.append(
                    Lead(username=uname, source="aw",
                         language=self.detect_language(uname),
                         niche=niche)
                )
        inserted = await db.add_leads_bulk(leads)
        log.info("AW: loaded %d / %d leads", inserted, len(leads))
        return inserted

    async def load_hackforums(self) -> int:
        """Load HackForums telegram contacts (~48 leads)."""
        path = self.DATA_SOURCES["hackforums"]
        if not path.exists():
            log.warning("HackForums source not found: %s", path)
            return 0
        leads: list[Lead] = []
        try:
            conn = sqlite3.connect(str(path))
            cur = conn.execute(
                "SELECT contact_value FROM contacts "
                "WHERE contact_type IN ('telegram_at', 'telegram_link')"
            )
            for (val,) in cur.fetchall():
                uname = self._clean_username(val)
                if uname:
                    leads.append(
                        Lead(username=uname, source="hackforums",
                             language=self.detect_language(uname))
                    )
            conn.close()
        except Exception as exc:
            log.error("Failed to read HackForums DB: %s", exc)
            return 0
        inserted = await db.add_leads_bulk(leads)
        log.info("HackForums: loaded %d / %d leads", inserted, len(leads))
        return inserted

    async def load_exploit(self) -> int:
        """Load exploit forum users with Telegram handles."""
        path = self.DATA_SOURCES["exploit"]
        if not path.exists():
            log.warning("Exploit source not found: %s", path)
            return 0
        leads: list[Lead] = []
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            headers = next(reader, None)
            col = self._find_tg_column(headers) if headers else 0
            if col is None:
                col = 0
            for row in reader:
                if len(row) <= col:
                    continue
                uname = self._clean_username(row[col])
                if uname:
                    leads.append(
                        Lead(username=uname, source="exploit",
                             language=self.detect_language(uname, row[col]))
                    )
        inserted = await db.add_leads_bulk(leads)
        log.info("Exploit: loaded %d / %d leads", inserted, len(leads))
        return inserted

    # ── orchestration ───────────────────────────────────────────────────────

    async def load_all(self) -> int:
        """Load leads from every configured source. Returns total inserted."""
        total = 0
        for name, loader in [
            ("bhw", self.load_bhw),
            ("aw", self.load_aw),
            ("hackforums", self.load_hackforums),
            ("exploit", self.load_exploit),
        ]:
            try:
                count = await loader()
                total += count
            except Exception as exc:
                log.error("Failed to load %s: %s", name, exc)
        log.info("Total leads loaded: %d", total)
        return total

    async def validate_leads(self, client=None) -> dict:
        """Validate lead usernames via Telegram API.

        If *client* is provided it is used directly; otherwise a session
        must already be available via SessionManager.
        Marks invalid leads as 'dead'.  Respects rate limits.
        """
        from .session_manager import SessionManager

        own_client = False
        if client is None:
            sm = SessionManager()
            phones = await sm.rotate_sessions()
            if not phones:
                log.warning("No sessions available for lead validation")
                return {"validated": 0, "dead": 0}
            client = await sm.get_client(phones[0])
            own_client = True

        leads = await db.get_leads(status="new")
        validated = 0
        dead = 0
        try:
            for lead in leads:
                try:
                    entity = await client.get_entity(lead.username)
                    validated += 1
                except ValueError:
                    await db.update_lead(lead.username, status="dead")
                    dead += 1
                except Exception:
                    pass  # transient error — skip
                await asyncio.sleep(2)  # rate limit
        finally:
            if own_client:
                await client.disconnect()

        result = {"validated": validated, "dead": dead}
        log.info("Lead validation: %s", result)
        return result

    async def get_stats(self) -> dict:
        """Return lead counts grouped by source and status."""
        import aiosqlite
        stats: dict = {}
        async with aiosqlite.connect(str(db.DB)) as conn:
            cur = await conn.execute(
                "SELECT source, status, COUNT(*) FROM leads GROUP BY source, status"
            )
            for source, status, cnt in await cur.fetchall():
                stats.setdefault(source, {})[status] = cnt
            cur = await conn.execute("SELECT COUNT(*) FROM leads")
            stats["_total"] = (await cur.fetchone())[0]
        return stats
