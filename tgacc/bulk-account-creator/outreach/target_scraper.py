"""Scrape, import, and manage target users for Telegram outreach."""

from __future__ import annotations

import asyncio
import csv
import json
import secrets
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
from loguru import logger

from . import config

DB = str(config.DB_PATH)


# ── data model ──────────────────────────────────────────────────────────────


@dataclass
class ScrapedTarget:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    is_premium: bool
    last_seen: Optional[str]  # online, recently, within_week, within_month, long_time_ago, unknown
    source_group: str
    scraped_at: str
    access_hash: int = 0


# ── schema ──────────────────────────────────────────────────────────────────

_TARGETS_SCHEMA = """
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
"""


# ── scraper ─────────────────────────────────────────────────────────────────


class TargetScraper:
    """Extract and manage target users from Telegram groups."""

    def __init__(self, db_path: str = DB):
        self.db_path = db_path

    # ── database setup ─────────────────────────────────────────────────────

    async def init_db(self) -> None:
        """Create the targets table if it does not exist."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(_TARGETS_SCHEMA)
            await conn.commit()
        logger.info("Targets table initialised at {}", self.db_path)

    # ── scraping ───────────────────────────────────────────────────────────

    async def scrape_group(
        self,
        client,
        group_username: str,
        filters: dict | None = None,
    ) -> list[ScrapedTarget]:
        """Scrape members from a Telegram supergroup.

        Args:
            client: Connected TelegramClient (use a WARMED account).
            group_username: Group @username or invite link.
            filters: Optional filter dict – see defaults below.

        Returns:
            List of ScrapedTarget passing all filters.
        """
        from telethon.tl.functions.channels import GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsSearch

        filters = filters or {}
        filters.setdefault("active_only", True)
        filters.setdefault("active_days", 7)
        filters.setdefault("premium_only", False)
        filters.setdefault("exclude_bots", True)
        filters.setdefault("min_username", True)

        targets: list[ScrapedTarget] = []
        offset = 0
        limit = 200

        try:
            entity = await client.get_entity(group_username)
            logger.info("Scraping group: {} (ID: {})", group_username, entity.id)

            while True:
                participants = await client(
                    GetParticipantsRequest(
                        channel=entity,
                        filter=ChannelParticipantsSearch(""),
                        offset=offset,
                        limit=limit,
                        hash=0,
                    )
                )

                if not participants.users:
                    break

                for user in participants.users:
                    if filters["exclude_bots"] and user.bot:
                        continue
                    if filters["min_username"] and not user.username:
                        continue
                    if filters["premium_only"] and not getattr(user, "premium", False):
                        continue

                    last_seen = self._parse_last_seen(user.status)

                    if filters["active_only"] and last_seen in (
                        "long_time_ago",
                        "unknown",
                    ):
                        continue

                    targets.append(
                        ScrapedTarget(
                            user_id=user.id,
                            username=user.username,
                            first_name=user.first_name,
                            last_name=user.last_name,
                            phone=user.phone,
                            is_premium=getattr(user, "premium", False) or False,
                            last_seen=last_seen,
                            source_group=group_username,
                            scraped_at=datetime.utcnow().isoformat(),
                            access_hash=user.access_hash or 0,
                        )
                    )

                offset += len(participants.users)
                logger.info(
                    "Scraped {} members so far, {} passed filters", offset, len(targets)
                )

                if len(participants.users) < limit:
                    break

                # Unpredictable delay between pages: 2-5 s
                await asyncio.sleep(secrets.randbelow(4) + 2)

        except Exception as exc:
            logger.error("Scraping error for {}: {}", group_username, exc)

        logger.info(
            "Scraping complete: {} targets from {}", len(targets), group_username
        )
        return targets

    @staticmethod
    def _parse_last_seen(status) -> str:
        """Convert a Telethon UserStatus to a human-readable string."""
        from telethon.tl.types import (
            UserStatusOnline,
            UserStatusRecently,
            UserStatusLastWeek,
            UserStatusLastMonth,
            UserStatusEmpty,
            UserStatusOffline,
        )

        if status is None:
            return "unknown"
        if isinstance(status, UserStatusOnline):
            return "online"
        if isinstance(status, UserStatusRecently):
            return "recently"
        if isinstance(status, UserStatusLastWeek):
            return "within_week"
        if isinstance(status, UserStatusLastMonth):
            return "within_month"
        if isinstance(status, UserStatusEmpty):
            return "unknown"
        if isinstance(status, UserStatusOffline):
            if status.was_online:
                delta = datetime.utcnow() - status.was_online
                if delta.days <= 1:
                    return "recently"
                if delta.days <= 7:
                    return "within_week"
                if delta.days <= 30:
                    return "within_month"
            return "long_time_ago"
        return "unknown"

    async def scrape_multiple_groups(
        self,
        client,
        groups: list[str],
        filters: dict | None = None,
    ) -> list[ScrapedTarget]:
        """Scrape several groups sequentially with delays between them."""
        all_targets: list[ScrapedTarget] = []
        seen_ids: set[int] = set()

        for idx, group in enumerate(groups):
            targets = await self.scrape_group(client, group, filters)
            for t in targets:
                if t.user_id not in seen_ids:
                    seen_ids.add(t.user_id)
                    all_targets.append(t)

            logger.info(
                "Group {}/{} done – {} unique targets so far",
                idx + 1,
                len(groups),
                len(all_targets),
            )

            if idx < len(groups) - 1:
                delay = secrets.randbelow(31) + 30  # 30-60 s between groups
                logger.info("Waiting {}s before next group…", delay)
                await asyncio.sleep(delay)

        logger.info("Multi-group scrape complete: {} unique targets", len(all_targets))
        return all_targets

    # ── username resolution ────────────────────────────────────────────────

    async def resolve_usernames(
        self, client, usernames: list[str]
    ) -> list[ScrapedTarget]:
        """Resolve @usernames to User IDs via the Telegram API.

        Resolved users are cached in the DB so repeat lookups are free.
        Rate-limited to one resolve every 2-3 s.
        """
        from telethon.tl.functions.contacts import ResolveUsernameRequest

        resolved: list[ScrapedTarget] = []

        # Check which usernames are already cached
        cached_map: dict[str, ScrapedTarget] = {}
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            for uname in usernames:
                clean = uname.lstrip("@").lower()
                cur = await conn.execute(
                    "SELECT * FROM targets WHERE LOWER(username) = ?", (clean,)
                )
                row = await cur.fetchone()
                if row:
                    cached_map[clean] = self._row_to_target(row)

        for uname in usernames:
            clean = uname.lstrip("@").lower()
            if clean in cached_map:
                resolved.append(cached_map[clean])
                logger.debug("Cache hit for @{}", clean)
                continue

            try:
                result = await client(ResolveUsernameRequest(clean))
                if result.users:
                    user = result.users[0]
                    target = ScrapedTarget(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        phone=user.phone,
                        is_premium=getattr(user, "premium", False) or False,
                        last_seen=self._parse_last_seen(user.status),
                        source_group="resolve",
                        scraped_at=datetime.utcnow().isoformat(),
                        access_hash=user.access_hash or 0,
                    )
                    resolved.append(target)
                    logger.info("Resolved @{} → {}", clean, user.id)
                else:
                    logger.warning("No user found for @{}", clean)
            except Exception as exc:
                logger.error("Failed to resolve @{}: {}", clean, exc)

            await asyncio.sleep(secrets.randbelow(2) + 2)  # 2-3 s

        logger.info("Resolved {}/{} usernames", len(resolved), len(usernames))
        return resolved

    # ── CSV / JSON import ──────────────────────────────────────────────────

    async def import_from_csv(self, csv_path: str) -> list[ScrapedTarget]:
        """Import targets from a CSV file.

        Expected columns: username (required), source_group, first_name,
        last_name, user_id.  Extra columns are silently ignored.
        """
        path = Path(csv_path)
        if not path.exists():
            logger.error("CSV file not found: {}", csv_path)
            return []

        targets: list[ScrapedTarget] = []
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for i, row in enumerate(reader):
                username = (
                    row.get("username", row.get("tg_username", ""))
                    .strip()
                    .lstrip("@")
                )
                if not username:
                    logger.warning("Row {} missing username – skipped", i + 1)
                    continue

                targets.append(
                    ScrapedTarget(
                        user_id=int(row["user_id"]) if row.get("user_id") else 0,
                        username=username,
                        first_name=row.get("first_name"),
                        last_name=row.get("last_name"),
                        phone=row.get("phone"),
                        is_premium=row.get("is_premium", "").lower() in ("1", "true", "yes"),
                        last_seen=row.get("last_seen"),
                        source_group=row.get("source_group", row.get("source", "csv_import")),
                        scraped_at=datetime.utcnow().isoformat(),
                        access_hash=int(row.get("access_hash", 0) or 0),
                    )
                )

        logger.info("Imported {} targets from CSV {}", len(targets), csv_path)
        return targets

    async def import_from_json(self, json_path: str) -> list[ScrapedTarget]:
        """Import targets from a JSON file (array of objects)."""
        path = Path(json_path)
        if not path.exists():
            logger.error("JSON file not found: {}", json_path)
            return []

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

        if isinstance(data, dict):
            data = data.get("targets", data.get("users", [data]))

        targets: list[ScrapedTarget] = []
        for i, item in enumerate(data):
            username = str(
                item.get("username", item.get("tg_username", ""))
            ).strip().lstrip("@")
            if not username:
                logger.warning("Item {} missing username – skipped", i)
                continue

            targets.append(
                ScrapedTarget(
                    user_id=int(item.get("user_id", 0)),
                    username=username,
                    first_name=item.get("first_name"),
                    last_name=item.get("last_name"),
                    phone=item.get("phone"),
                    is_premium=bool(item.get("is_premium", False)),
                    last_seen=item.get("last_seen"),
                    source_group=item.get("source_group", item.get("source", "json_import")),
                    scraped_at=datetime.utcnow().isoformat(),
                    access_hash=int(item.get("access_hash", 0)),
                )
            )

        logger.info("Imported {} targets from JSON {}", len(targets), json_path)
        return targets

    # ── persistence ────────────────────────────────────────────────────────

    async def save_targets(self, targets: list[ScrapedTarget]) -> dict:
        """Save targets to DB with deduplication (by user_id).

        Returns: ``{inserted: int, duplicates: int, errors: int}``
        """
        inserted = 0
        duplicates = 0
        errors = 0

        async with aiosqlite.connect(self.db_path) as conn:
            for t in targets:
                try:
                    cur = await conn.execute(
                        """INSERT INTO targets
                           (user_id, username, first_name, last_name, phone,
                            is_premium, last_seen, source_group, access_hash,
                            scraped_at, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                           ON CONFLICT(user_id) DO UPDATE SET
                             username     = COALESCE(excluded.username, targets.username),
                             first_name   = COALESCE(excluded.first_name, targets.first_name),
                             last_name    = COALESCE(excluded.last_name, targets.last_name),
                             phone        = COALESCE(excluded.phone, targets.phone),
                             is_premium   = excluded.is_premium,
                             last_seen    = excluded.last_seen,
                             access_hash  = CASE WHEN excluded.access_hash != 0
                                                 THEN excluded.access_hash
                                                 ELSE targets.access_hash END,
                             scraped_at   = excluded.scraped_at
                        """,
                        (
                            t.user_id,
                            t.username,
                            t.first_name,
                            t.last_name,
                            t.phone,
                            int(t.is_premium),
                            t.last_seen,
                            t.source_group,
                            t.access_hash,
                            t.scraped_at,
                        ),
                    )
                    if cur.rowcount:
                        inserted += 1
                    else:
                        duplicates += 1
                except aiosqlite.IntegrityError:
                    duplicates += 1
                except Exception as exc:
                    errors += 1
                    logger.error("Error saving target {}: {}", t.user_id, exc)
            await conn.commit()

        result = {"inserted": inserted, "duplicates": duplicates, "errors": errors}
        logger.info("Save targets result: {}", result)
        return result

    # ── queries ─────────────────────────────────────────────────────────────

    async def get_pending_targets(self, limit: int = 100) -> list[ScrapedTarget]:
        """Return up to *limit* targets with ``status='pending'``."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM targets WHERE status = 'pending' ORDER BY scraped_at LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
        return [self._row_to_target(r) for r in rows]

    async def mark_messaged(self, user_id: int, account_phone: str) -> None:
        """Mark a target as messaged."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE targets SET status = 'messaged', messaged_at = ?, messaged_by = ? WHERE user_id = ?",
                (datetime.utcnow().isoformat(), account_phone, user_id),
            )
            await conn.commit()

    async def mark_replied(self, user_id: int) -> None:
        """Mark a target as replied."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE targets SET status = 'replied' WHERE user_id = ?",
                (user_id,),
            )
            await conn.commit()

    async def mark_skipped(self, user_id: int, reason: str = "") -> None:
        """Mark a target as skipped (privacy-restricted, deactivated, etc.)."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE targets SET status = 'skipped' WHERE user_id = ?",
                (user_id,),
            )
            await conn.commit()
        if reason:
            logger.info("Skipped target {}: {}", user_id, reason)

    # ── stats / maintenance ────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Return target counts grouped by status."""
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "SELECT status, COUNT(*) FROM targets GROUP BY status"
            )
            rows = await cur.fetchall()
            cur_total = await conn.execute("SELECT COUNT(*) FROM targets")
            total = (await cur_total.fetchone())[0]

        stats = {row[0]: row[1] for row in rows}
        stats["total"] = total
        return stats

    async def deduplicate(self) -> int:
        """Remove true duplicate rows (should not exist with PK, but cleans
        up any rows imported with ``user_id=0`` that share a username)."""
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                """DELETE FROM targets WHERE rowid NOT IN (
                       SELECT MIN(rowid) FROM targets GROUP BY user_id
                   )"""
            )
            removed = cur.rowcount
            await conn.commit()
        if removed:
            logger.info("Deduplication removed {} rows", removed)
        return removed

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_target(row) -> ScrapedTarget:
        return ScrapedTarget(
            user_id=row["user_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            is_premium=bool(row["is_premium"]),
            last_seen=row["last_seen"],
            source_group=row["source_group"],
            scraped_at=row["scraped_at"] or "",
            access_hash=row["access_hash"] or 0,
        )


# ── CLI demo ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _demo():
        scraper = TargetScraper()
        await scraper.init_db()

        stats = await scraper.get_stats()
        logger.info("Current target stats: {}", stats)

        # Example: import from CSV
        # targets = await scraper.import_from_csv("targets.csv")
        # result = await scraper.save_targets(targets)
        # logger.info("Import result: {}", result)

        # Example: scrape a group (requires a connected client)
        # from .session_manager import SessionManager
        # sm = SessionManager()
        # client = await sm.get_client("+1234567890")
        # targets = await scraper.scrape_group(client, "target_group")
        # result = await scraper.save_targets(targets)
        # await client.disconnect()

    asyncio.run(_demo())
