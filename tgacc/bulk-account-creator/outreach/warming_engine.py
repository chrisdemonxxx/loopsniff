"""14-day account warming automation.

Gradually increases activity so Telegram's anti-spam heuristics treat the
account as organic before we start outreach.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import List

from telethon import functions, types
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
)

from . import config, db
from .session_manager import SessionManager

log = logging.getLogger(__name__)


class WarmingEngine:
    """Automate the 14-day warming schedule for fresh accounts."""

    # (join_groups, send_messages, read_channels, react_to_posts)
    WARMING_SCHEDULE = {
        1:  (2,  3,  5,  5),
        2:  (2,  5,  8,  8),
        3:  (3,  5,  10, 10),
        4:  (3,  8,  12, 12),
        5:  (3,  10, 15, 15),
        6:  (4,  10, 18, 18),
        7:  (4,  12, 20, 20),
        8:  (4,  12, 22, 22),
        9:  (5,  13, 23, 23),
        10: (5,  15, 25, 25),
        11: (5,  16, 27, 27),
        12: (5,  17, 28, 28),
        13: (5,  18, 29, 29),
        14: (5,  20, 30, 30),
    }

    WARMING_GROUPS = [
        # Fallback list — search API is preferred
        "durov", "telegram", "TelegramTips", "designinspiration",
        "gamers_chat",
    ]

    # Topics to search for when discovering groups to join
    SEARCH_TOPICS = [
        # Traffic & media buying niche
        "traffic arbitrage", "media buying", "affiliate marketing",
        "CPA network", "ad accounts", "Facebook ads",
        "Google ads", "TikTok ads", "native ads",
        "blackhat marketing", "cloaking", "antidetect browser",
        "traffic source", "ad spy tools", "landing pages",
        "push notifications ads", "popunder traffic",
        # General interest (organic look)
        "crypto trading", "ecommerce", "tech news",
        "programming", "finance", "stocks",
        "gaming", "design", "photography", "fitness",
        "travel", "startup", "AI", "social media",
    ]

    CASUAL_MESSAGES = [
        "Thanks for sharing! 🙌",
        "Great insight, appreciate it.",
        "Interesting perspective 👍",
        "Good point!",
        "Very helpful, thanks!",
        "Learned something new today.",
        "Love this community 🔥",
        "Solid advice right here.",
        "This is exactly what I was looking for.",
        "Appreciate the detailed breakdown!",
        "Facts 💯",
        "Bookmarking this for later.",
    ]

    REACTION_EMOJIS = ["👍", "🔥", "❤️", "👏", "💯", "🤝", "⚡"]

    def __init__(self) -> None:
        self.sm = SessionManager()

    # ── helpers ─────────────────────────────────────────────────────────────

    def _get_plan(self, day: int) -> tuple:
        """Look up the warming plan for *day*, interpolating if needed."""
        if day in self.WARMING_SCHEDULE:
            return self.WARMING_SCHEDULE[day]
        # Interpolate: use the plan for the nearest defined day ≤ current day
        defined = sorted(self.WARMING_SCHEDULE.keys())
        best = defined[0]
        for d in defined:
            if d <= day:
                best = d
        return self.WARMING_SCHEDULE[best]

    # ── core warming activities ─────────────────────────────────────────────

    async def _check_connection(self, client) -> bool:
        """Quick health check — is the client still connected and responsive?"""
        try:
            me = await asyncio.wait_for(client.get_me(), timeout=10)
            return me is not None
        except Exception as exc:
            log.warning("Connection health check failed: %s", exc)
            return False

    async def _join_groups(self, client, count: int) -> int:
        """Join up to *count* public groups by searching Telegram."""
        joined = 0
        topics = random.sample(
            self.SEARCH_TOPICS, min(count + 4, len(self.SEARCH_TOPICS))
        )
        for topic in topics:
            if joined >= count:
                break
            try:
                result = await client(functions.contacts.SearchRequest(
                    q=topic, limit=5
                ))
                for chat in result.chats:
                    if joined >= count:
                        break
                    if getattr(chat, 'left', True) is False:
                        continue  # already a member
                    try:
                        await client(functions.channels.JoinChannelRequest(chat))
                        joined += 1
                        title = getattr(chat, 'title', '?')
                        log.info("Joined '%s' (via search: %s)", title, topic)
                        await asyncio.sleep(random.uniform(10, 30))
                    except FloodWaitError as e:
                        log.warning("FloodWait %ds joining — sleeping", e.seconds)
                        await asyncio.sleep(e.seconds + 5)
                    except Exception as exc:
                        log.info("Could not join chat from search '%s': %s", topic, exc)
                await asyncio.sleep(random.uniform(3, 8))
            except FloodWaitError as e:
                log.warning("FloodWait %ds on search — sleeping", e.seconds)
                await asyncio.sleep(e.seconds + 5)
            except Exception as exc:
                log.info("Search for '%s' failed: %s", topic, exc)
        return joined

    async def _send_casual_messages(self, client, count: int) -> int:
        """Send casual messages in joined groups."""
        sent = 0
        try:
            dialogs = await client.get_dialogs(limit=30)
            groups = [d for d in dialogs if d.is_group or d.is_channel]
        except Exception:
            groups = []

        random.shuffle(groups)
        for dialog in groups[:count]:
            try:
                msg = random.choice(self.CASUAL_MESSAGES)
                await client.send_message(dialog.entity, msg)
                sent += 1
                log.info("Sent warming msg in %s", dialog.name)
                await asyncio.sleep(random.uniform(15, 60))
            except (ChatWriteForbiddenError, UserBannedInChannelError):
                continue
            except FloodWaitError as e:
                log.warning("FloodWait %ds sending messages — sleeping", e.seconds)
                await asyncio.sleep(e.seconds + 5)
            except Exception as exc:
                log.info("Could not message in %s: %s", dialog.name, exc)
        return sent

    async def _read_channels(self, client, count: int) -> int:
        """Scroll through / mark-as-read channel messages."""
        read = 0
        try:
            dialogs = await client.get_dialogs(limit=50)
            channels = [d for d in dialogs if d.is_channel]
        except Exception:
            channels = []

        random.shuffle(channels)
        for dialog in channels[:count]:
            try:
                async for _ in client.iter_messages(dialog.entity, limit=10):
                    pass  # just iterate to simulate reading
                await client.send_read_acknowledge(dialog.entity)
                read += 1
                await asyncio.sleep(random.uniform(3, 10))
            except Exception:
                continue
        return read

    async def _react_to_posts(self, client, count: int) -> int:
        """React to recent posts with random emojis."""
        reacted = 0
        try:
            dialogs = await client.get_dialogs(limit=40)
            candidates = [d for d in dialogs if d.is_channel or d.is_group]
        except Exception:
            candidates = []

        random.shuffle(candidates)
        for dialog in candidates:
            if reacted >= count:
                break
            try:
                msgs = await client.get_messages(dialog.entity, limit=5)
                for m in msgs:
                    if reacted >= count:
                        break
                    emoji = random.choice(self.REACTION_EMOJIS)
                    try:
                        await client(
                            functions.messages.SendReactionRequest(
                                peer=dialog.entity,
                                msg_id=m.id,
                                reaction=[types.ReactionEmoji(emoticon=emoji)],
                            )
                        )
                        reacted += 1
                        await asyncio.sleep(random.uniform(5, 15))
                    except Exception:
                        continue
            except Exception:
                continue
        return reacted

    # ── orchestration ───────────────────────────────────────────────────────

    async def warm_account(self, phone: str, day: int, client=None) -> dict:
        """Execute all warming activities for *phone* on *day*.

        If *client* is provided (already-connected TelegramClient), uses it
        directly without disconnecting.  Otherwise opens a new connection.
        """
        plan = self._get_plan(day)
        join_target, msg_target, read_target, react_target = plan
        log.info(
            "Warming %s day %d — plan: join=%d msg=%d read=%d react=%d",
            phone, day, *plan,
        )

        own_client = client is None
        if own_client:
            client = await self.sm.get_client(phone)

        # Health check before starting
        if not await self._check_connection(client):
            log.warning("Skipping warmup for %s — connection not healthy", phone)
            if own_client:
                await client.disconnect()
            return {
                "phone": phone, "day": day,
                "groups_joined": 0, "messages_sent": 0,
                "channels_read": 0, "reactions": 0,
                "skipped": "connection_unhealthy",
            }

        try:
            groups_joined = await self._join_groups(client, join_target)
            messages_sent = await self._send_casual_messages(client, msg_target)
            channels_read = await self._read_channels(client, read_target)
            reactions = await self._react_to_posts(client, react_target)
        finally:
            if own_client:
                await client.disconnect()

        await db.log_warming(phone, day, groups_joined, messages_sent,
                             channels_read, reactions)

        total = groups_joined + messages_sent + channels_read + reactions
        result = {
            "phone": phone,
            "day": day,
            "groups_joined": groups_joined,
            "messages_sent": messages_sent,
            "channels_read": channels_read,
            "reactions": reactions,
        }
        if total == 0:
            result["skipped"] = "zero_activity"
        log.info("Warming result for %s: %s", phone, result)
        return result

    async def run_daily_warming(self) -> List[dict]:
        """Run warming for every account with status='warming'."""
        accounts = await db.get_accounts(status="warming")
        results = []
        for acct in accounts:
            last_day = await db.get_warming_day(acct.phone)
            next_day = last_day + 1
            if next_day > config.WARMING_DAYS:
                await self.check_warming_complete()
                continue
            try:
                result = await self.warm_account(acct.phone, next_day)
                results.append(result)
            except Exception as exc:
                log.error("Warming failed for %s: %s", acct.phone, exc)
                results.append({"phone": acct.phone, "error": str(exc)})
            # Stagger accounts so they don't hit the API simultaneously
            await asyncio.sleep(random.uniform(30, 120))
        return results

    async def check_warming_complete(self) -> List[str]:
        """Promote accounts that have completed the full warming cycle."""
        accounts = await db.get_accounts(status="warming")
        promoted: List[str] = []
        for acct in accounts:
            last_day = await db.get_warming_day(acct.phone)
            if last_day >= config.WARMING_DAYS:
                await db.update_account(
                    acct.phone,
                    status="ready",
                    warmed_at=datetime.utcnow(),
                )
                promoted.append(acct.phone)
                log.info("Account %s promoted to 'ready' after %d days warming",
                         acct.phone, last_day)
        return promoted


# ── module-level entry points (for cron / CLI) ─────────────────────────────

async def run_daily_warming() -> List[dict]:
    """Module-level wrapper for cron: init DB, run warming for all accounts."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await db.init_db()
    engine = WarmingEngine()
    results = await engine.run_daily_warming()
    log.info("Daily warming complete — %d accounts processed", len(results))
    succeeded = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    log.info("Success: %d, Failed: %d", len(succeeded), len(failed))
    for f in failed:
        log.error("  %s: %s", f["phone"], f["error"])
    return results
