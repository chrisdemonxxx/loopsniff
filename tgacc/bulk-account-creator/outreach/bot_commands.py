"""Campaign control commands for TG bot integration.

These functions can be called from the admin bot handler.

Commands:
  /campaign start <campaign_id> <niche> — Start a throwaway campaign
  /campaign status — Show current campaign status
  /campaign pause — Pause running campaign
  /campaign resume — Resume paused campaign
  /campaign stop — Stop running campaign
  /pool status — Show session pool stats
  /pool import — Trigger session import
  /targets stats — Show target statistics
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from loguru import logger


class CampaignBotCommands:
    """Bot command handlers for campaign management."""

    def __init__(self) -> None:
        self._engine = None  # ThrowawayEngine instance
        self._engine_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Router
    # ------------------------------------------------------------------

    async def handle_command(self, command: str, args: list[str]) -> str:
        """Route a command and return the response text.

        Args:
            command: The command name (e.g. "campaign", "pool", "targets").
            args: Arguments after the command.

        Returns:
            Response text to send back to admin.
        """
        handlers = {
            "campaign": self._handle_campaign,
            "pool": self._handle_pool,
            "targets": self._handle_targets,
        }
        handler = handlers.get(command)
        if handler is None:
            return "❓ Unknown command. Available: /campaign, /pool, /targets"
        return await handler(args)

    # ------------------------------------------------------------------
    # /campaign
    # ------------------------------------------------------------------

    async def _handle_campaign(self, args: list[str]) -> str:
        if not args:
            return self._campaign_help()

        action = args[0].lower()
        dispatch = {
            "start": self._start_campaign,
            "status": self._campaign_status,
            "pause": self._pause_campaign,
            "resume": self._resume_campaign,
            "stop": self._stop_campaign,
        }
        handler = dispatch.get(action)
        if handler is None:
            return self._campaign_help()

        if action == "start":
            if len(args) < 3:
                return "Usage: /campaign start <campaign_id> <niche>"
            return await handler(args[1], args[2])
        return await handler()

    async def _start_campaign(self, campaign_id: str, niche: str) -> str:
        """Start a new throwaway campaign in background."""
        if self._engine and self._engine._running:
            return "⚠️ A campaign is already running. Stop it first with /campaign stop"

        from outreach.throwaway_engine import ThrowawayEngine, CampaignConfig

        config = CampaignConfig(
            campaign_id=campaign_id,
            niche=niche,
            admin_chat_id=os.getenv("ADMIN_CHAT_ID", ""),
            bot_token=os.getenv("BOT_TOKEN", ""),
        )

        self._engine = ThrowawayEngine(config)
        await self._engine.setup()

        self._engine_task = asyncio.create_task(
            self._engine.run(), name=f"campaign-{campaign_id}"
        )

        pool_stats = await self._engine.session_pool.get_stats()
        return (
            f"🚀 Campaign '{campaign_id}' started!\n"
            f"📋 Niche: {niche}\n"
            f"📱 Sessions available: {pool_stats.get('fresh', 0)}\n"
            f"🎯 Daily quota: {config.daily_quota}\n\n"
            f"Use /campaign status for live updates"
        )

    async def _campaign_status(self) -> str:
        if not self._engine:
            return "ℹ️ No campaign running."
        return self._engine.stats.to_report()

    async def _pause_campaign(self) -> str:
        if not self._engine or not self._engine._running:
            return "ℹ️ No campaign running."
        await self._engine.pause()
        return "⏸️ Campaign paused. Use /campaign resume to continue."

    async def _resume_campaign(self) -> str:
        if not self._engine:
            return "ℹ️ No campaign to resume."
        self._engine_task = asyncio.create_task(
            self._engine.resume(), name="campaign-resume"
        )
        return "▶️ Campaign resumed!"

    async def _stop_campaign(self) -> str:
        if not self._engine:
            return "ℹ️ No campaign running."
        await self._engine.stop()
        report = self._engine.stats.to_report()
        self._engine = None
        self._engine_task = None
        return f"🛑 Campaign stopped.\n\n{report}"

    # ------------------------------------------------------------------
    # /pool
    # ------------------------------------------------------------------

    async def _handle_pool(self, args: list[str]) -> str:
        if not args or args[0] == "status":
            return await self._pool_status()
        if args[0] == "import":
            return await self._pool_import()
        return "Usage: /pool status | /pool import"

    async def _pool_status(self) -> str:
        from outreach.session_pool import SessionPool

        pool = SessionPool()
        await pool.init_db()
        stats = await pool.get_stats()

        return (
            f"📱 Session Pool Status\n"
            f"{'─' * 25}\n"
            f"🟢 Fresh: {stats.get('fresh', 0)}\n"
            f"🔵 Active: {stats.get('active', 0)}\n"
            f"🟡 Resting: {stats.get('resting', 0)}\n"
            f"🔴 Burned: {stats.get('burned', 0)}\n"
            f"⛔ Banned: {stats.get('banned', 0)}\n"
            f"{'─' * 25}\n"
            f"📊 Total: {stats.get('total', 0)}"
        )

    async def _pool_import(self) -> str:
        from outreach.session_pool import SessionPool

        pool = SessionPool()
        await pool.init_db()
        result = await pool.import_sessions()
        return f"📥 Import result:\n{json.dumps(result, indent=2)}"

    # ------------------------------------------------------------------
    # /targets
    # ------------------------------------------------------------------

    async def _handle_targets(self, args: list[str]) -> str:
        if not args or args[0] == "stats":
            return await self._targets_stats()
        return "Usage: /targets stats"

    async def _targets_stats(self) -> str:
        from outreach.target_scraper import TargetScraper

        scraper = TargetScraper()
        await scraper.init_db()
        stats = await scraper.get_stats()

        return (
            f"🎯 Target Pool Status\n"
            f"{'─' * 25}\n"
            f"⏳ Pending: {stats.get('pending', 0)}\n"
            f"✅ Messaged: {stats.get('messaged', 0)}\n"
            f"↩️ Replied: {stats.get('replied', 0)}\n"
            f"⏭️ Skipped: {stats.get('skipped', 0)}\n"
            f"❌ Failed: {stats.get('failed', 0)}\n"
            f"{'─' * 25}\n"
            f"📊 Total: {stats.get('total', 0)}"
        )

    # ------------------------------------------------------------------
    # Help text
    # ------------------------------------------------------------------

    @staticmethod
    def _campaign_help() -> str:
        return (
            "📋 Campaign Commands\n"
            "─────────────────\n"
            "/campaign start <id> <niche> — Start campaign\n"
            "/campaign status — Current stats\n"
            "/campaign pause — Pause campaign\n"
            "/campaign resume — Resume campaign\n"
            "/campaign stop — Stop campaign"
        )
