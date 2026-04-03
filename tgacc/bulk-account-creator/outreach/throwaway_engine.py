"""Throwaway execution engine for burn-and-churn Telegram outreach.

Implements the 5-phase protocol:
  Phase 1: Checkout session → bind proxy → connect client
  Phase 2: Micro-batch loop (1-5 messages per session)
  Phase 3: Burn session → disconnect
  Phase 4: Rotate proxy IP → stabilise
  Phase 5: Loop back to Phase 1
"""

from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiohttp
from loguru import logger
from telethon import TelegramClient


# ── Campaign configuration ──────────────────────────────────────────────────


@dataclass
class CampaignConfig:
    campaign_id: str
    niche: str = "crypto"
    daily_quota: int = 2000
    micro_batch_min: int = 1
    micro_batch_max: int = 5
    inter_message_delay_base: float = 25.0
    inter_message_delay_sigma: float = 8.0
    inter_session_delay_base: float = 10.0
    inter_session_delay_sigma: float = 3.0
    max_burn_rate: float = 0.8
    proxy_country: str = "US"
    message_language: str = "en"
    message_style: str = "casual"
    max_message_chars: int = 200
    pre_generate_count: int = 500
    spintax_template: str = ""
    auto_pause_on_high_burn: bool = True
    admin_chat_id: str = ""
    bot_token: str = ""


# ── Campaign statistics ─────────────────────────────────────────────────────


@dataclass
class CampaignStats:
    campaign_id: str = ""
    started_at: str = ""
    messages_sent: int = 0
    messages_failed: int = 0
    targets_skipped: int = 0
    sessions_used: int = 0
    sessions_burned: int = 0
    sessions_banned: int = 0
    proxy_rotations: int = 0
    errors: list = field(default_factory=list)
    is_paused: bool = False
    is_completed: bool = False
    completed_at: str = ""
    pause_reason: str = ""

    @property
    def burn_rate(self) -> float:
        if self.sessions_used == 0:
            return 0.0
        return self.sessions_burned / self.sessions_used

    @property
    def delivery_rate(self) -> float:
        total = self.messages_sent + self.messages_failed
        if total == 0:
            return 0.0
        return self.messages_sent / total

    def to_report(self) -> str:
        """Generate a human-readable campaign report."""
        duration = ""
        if self.started_at and self.completed_at:
            try:
                start = datetime.fromisoformat(self.started_at)
                end = datetime.fromisoformat(self.completed_at)
                delta = end - start
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes = remainder // 60
                duration = f"{hours}h {minutes}m"
            except (ValueError, TypeError):
                duration = "unknown"
        elif self.started_at:
            try:
                start = datetime.fromisoformat(self.started_at)
                delta = datetime.utcnow() - start
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes = remainder // 60
                duration = f"{hours}h {minutes}m (running)"
            except (ValueError, TypeError):
                duration = "unknown"

        status = "✅ Completed" if self.is_completed else (
            "⏸️ Paused" if self.is_paused else "🔄 Running"
        )

        lines = [
            f"📊 Campaign Report: {self.campaign_id}",
            "─" * 30,
            f"📌 Status: {status}",
            f"✅ Messages sent: {self.messages_sent}",
            f"❌ Messages failed: {self.messages_failed}",
            f"⏭️ Targets skipped: {self.targets_skipped}",
            f"📱 Sessions used: {self.sessions_used}",
            f"🔥 Sessions burned: {self.sessions_burned}",
            f"🚫 Sessions banned: {self.sessions_banned}",
            f"🔄 Proxy rotations: {self.proxy_rotations}",
            f"📈 Delivery rate: {self.delivery_rate:.1%}",
            f"🔥 Burn rate: {self.burn_rate:.1%}",
        ]
        if duration:
            lines.append(f"⏱️ Duration: {duration}")
        if self.pause_reason:
            lines.append(f"⚠️ Pause reason: {self.pause_reason}")
        if self.errors:
            lines.append(f"🐛 Errors: {len(self.errors)}")

        return "\n".join(lines)


# ── Throwaway engine ────────────────────────────────────────────────────────


class ThrowawayEngine:
    """Core execution engine for throwaway/burn-and-churn Telegram outreach.

    Implements the 5-phase protocol:
    checkout → micro-batch → burn → rotate → repeat.
    """

    def __init__(self, config: CampaignConfig):
        self.config = config
        self.stats = CampaignStats(campaign_id=config.campaign_id)

        # Sub-modules (initialised in setup())
        self.session_pool = None       # SessionPool
        self.proxy_router = None       # ProxyRouter
        self.anti_ban = None           # AntiBanEngine
        self.message_engine = None     # MessageEngine
        self.target_scraper = None     # TargetScraper

        self._running = False
        self._paused = False

    # ── setup ───────────────────────────────────────────────────────────────

    async def setup(self):
        """Initialise all sub-modules. Called once before campaign starts."""
        from outreach.session_pool import SessionPool
        from core.proxy_router import ProxyRouter
        from outreach.anti_ban import AntiBanEngine
        from outreach.message_engine import MessageEngine
        from outreach.target_scraper import TargetScraper

        logger.info("=== Setting up campaign: {} ===", self.config.campaign_id)

        # 1. Initialise components
        self.session_pool = SessionPool()
        await self.session_pool.init_db()

        self.proxy_router = ProxyRouter.from_config()

        self.anti_ban = AntiBanEngine({
            "min_batch": self.config.micro_batch_min,
            "max_batch": self.config.micro_batch_max,
        })
        self.anti_ban.initialize()

        self.message_engine = MessageEngine()
        await self.message_engine.init_db()

        self.target_scraper = TargetScraper()
        await self.target_scraper.init_db()

        # 2. Import new sessions
        import_result = await self.session_pool.import_sessions()
        logger.info("Session import: {}", import_result)

        # 3. Wake rested sessions
        woken = await self.session_pool.wake_rested()
        if woken:
            logger.info("Woke {} rested sessions", woken)

        # 4. Pre-generate messages if pool is low
        pool_stats = await self.message_engine.get_pool_stats(
            self.config.campaign_id,
        )
        remaining = pool_stats.get("remaining", 0)

        if remaining < 50:
            logger.info("Message pool low ({}), pre-generating...", remaining)
            await self.message_engine.pre_generate_llm_batch(
                self.config.campaign_id,
                self.config.niche,
                self.config.pre_generate_count,
                style=self.config.message_style,
                max_chars=self.config.max_message_chars,
                language=self.config.message_language,
            )

        await self.message_engine.load_pool(self.config.campaign_id)

        # 5. Log initial state
        session_stats = await self.session_pool.get_stats()
        target_stats = await self.target_scraper.get_stats()
        pool_stats = await self.message_engine.get_pool_stats(
            self.config.campaign_id,
        )

        logger.info("Sessions: {}", session_stats)
        logger.info("Targets: {}", target_stats)
        logger.info("Messages: {}", pool_stats)

        self.stats.started_at = datetime.utcnow().isoformat()

    # ── main loop ───────────────────────────────────────────────────────────

    async def run(self):
        """Main campaign execution loop.

        Runs until: sessions exhausted, targets exhausted,
        daily quota reached, or paused.
        """
        self._running = True
        logger.info("=== Campaign {} STARTED ===", self.config.campaign_id)

        try:
            while self._running and not self._paused:
                # Check stopping conditions
                if self.stats.messages_sent >= self.config.daily_quota:
                    logger.info("Daily quota reached ({})", self.config.daily_quota)
                    self.stats.is_completed = True
                    break

                if not await self.session_pool.has_fresh():
                    logger.warning("No fresh sessions available — campaign complete")
                    self.stats.is_completed = True
                    break

                # Check burn rate after a few sessions
                if (
                    self.config.auto_pause_on_high_burn
                    and self.stats.sessions_used >= 5
                    and self.stats.burn_rate > self.config.max_burn_rate
                ):
                    msg = (
                        f"High burn rate ({self.stats.burn_rate:.0%}) — "
                        f"pausing campaign"
                    )
                    logger.warning(msg)
                    self._paused = True
                    self.stats.is_paused = True
                    self.stats.pause_reason = (
                        f"Burn rate {self.stats.burn_rate:.0%} "
                        f"> {self.config.max_burn_rate:.0%}"
                    )
                    await self._notify_admin(
                        f"⚠️ Campaign paused: burn rate {self.stats.burn_rate:.0%}"
                    )
                    break

                # Execute one full session cycle (phases 1-5)
                await self._execute_session_cycle()

        except KeyboardInterrupt:
            logger.info("Campaign interrupted by user")
        except Exception as e:
            logger.error("Campaign fatal error: {}", e)
            self.stats.errors.append(str(e))
        finally:
            self._running = False
            self.stats.completed_at = datetime.utcnow().isoformat()

            report = self.stats.to_report()
            logger.info("\n{}", report)
            await self._notify_admin(report)

    # ── session cycle (phases 1-5) ──────────────────────────────────────────

    async def _execute_session_cycle(self):
        """Execute one full session lifecycle.

        Phase 1: Checkout session → bind proxy → connect
        Phase 2: Micro-batch loop (send 1-5 messages)
        Phase 3: Burn session → disconnect
        Phase 4: Rotate proxy IP
        Phase 5: Inter-session delay
        """
        # ── Phase 1: Checkout ────────────────────────────────────────────
        session = await self.session_pool.checkout()
        if not session:
            self._running = False
            return

        self.stats.sessions_used += 1
        logger.info(
            "[Session {}] Checked out: {}",
            self.stats.sessions_used, session.phone,
        )

        # Get API credentials from pool (fallback to session's own)
        api_entry = self.anti_ban.get_api_credentials()
        api_id = api_entry.api_id if api_entry else session.api_id
        api_hash = api_entry.api_hash if api_entry else session.api_hash

        # Bind API entry for tracking
        if api_entry:
            self.anti_ban.api_pool.bind_session(api_entry.api_id)

        # Get proxy for this session
        try:
            proxy_config = await self.proxy_router.get_proxy_for_session(
                session.phone,
                country=self.config.proxy_country,
            )
        except Exception as e:
            logger.error("Proxy error for {}: {}", session.phone, e)
            await self.session_pool.rest(session.session_path, 300)
            return

        # Generate device fingerprint
        device = self.anti_ban.get_device_profile(self.config.proxy_country)

        # Create Telethon client
        client = TelegramClient(
            session.session_path,
            api_id,
            api_hash,
            proxy=proxy_config.to_telethon_proxy(),
            device_model=session.device_model or device.device_model,
            system_version=session.system_version or device.system_version,
            app_version=session.app_version or device.app_version,
            lang_code=session.lang_code or device.lang_code,
            system_lang_code=device.system_lang_code,
        )

        burn_reason = None

        try:
            await client.connect()

            # Validate session is still alive
            me = await client.get_me()
            if not me:
                logger.warning(
                    "Session {} invalid (get_me() returned None)",
                    session.phone,
                )
                await self.session_pool.ban(session.session_path, "invalid_session")
                self.stats.sessions_banned += 1
                return

            logger.info("Connected as: {} (@{})", me.first_name, me.username)

            # ── Phase 2: Micro-batch loop ────────────────────────────────
            batch_size = self.anti_ban.get_batch_size()
            logger.info("Micro-batch size: {}", batch_size)

            for msg_num in range(batch_size):
                if self.stats.messages_sent >= self.config.daily_quota:
                    break

                # Get next target
                targets = await self.target_scraper.get_pending_targets(limit=1)
                if not targets:
                    logger.warning("No pending targets — campaign complete")
                    self._running = False
                    break

                target = targets[0]

                # Get unique message
                message = await self.message_engine.get_unique_message(
                    self.config.campaign_id,
                )
                if not message:
                    logger.warning("Message pool exhausted")
                    # Attempt spintax fallback
                    if self.config.spintax_template:
                        await self.message_engine.pre_generate_spintax_batch(
                            self.config.campaign_id,
                            self.config.spintax_template,
                            100,
                        )
                        await self.message_engine.load_pool(
                            self.config.campaign_id,
                        )
                        message = await self.message_engine.get_unique_message(
                            self.config.campaign_id,
                        )

                    if not message:
                        self._running = False
                        break

                # Resolve target entity (by username if user_id is placeholder)
                try:
                    if target.user_id < 0 and target.username:
                        target_entity = await client.get_input_entity(target.username)
                    else:
                        target_entity = await client.get_input_entity(target.user_id)
                except Exception as e:
                    action = self.anti_ban.handle_error(e)
                    if action.should_skip_target:
                        await self.target_scraper.mark_skipped(
                            target.user_id, str(e),
                        )
                        self.stats.targets_skipped += 1
                        continue
                    elif action.should_burn:
                        burn_reason = action.burn_reason.value
                        break
                    elif action.should_retry and action.retry_after:
                        await asyncio.sleep(action.retry_after)
                        continue
                    else:
                        continue

                # Phase 2a: Typing simulation
                await self.anti_ban.pre_message_delay(
                    message.text, client, target_entity,
                )

                # Phase 2b: Send message
                try:
                    await client.send_message(target_entity, message.text)

                    self.stats.messages_sent += 1
                    self.message_engine.mark_sent(message.hash)
                    await self.session_pool.increment_messages(
                        session.session_path,
                    )
                    await self.target_scraper.mark_messaged(
                        target.user_id, session.phone,
                    )

                    logger.info(
                        "[{}/{}] Sent to @{} via {} ({}/{})",
                        self.stats.messages_sent,
                        self.config.daily_quota,
                        target.username or target.user_id,
                        session.phone,
                        msg_num + 1,
                        batch_size,
                    )

                except Exception as e:
                    action = self.anti_ban.handle_error(e)

                    if action.should_burn:
                        burn_reason = action.burn_reason.value
                        if action.should_quarantine_api and api_entry:
                            self.anti_ban.api_pool.quarantine(
                                api_entry.api_id, action.burn_reason.value,
                            )
                        if action.alert_admin:
                            await self._notify_admin(action.alert_message)
                        self.stats.messages_failed += 1
                        break

                    elif action.should_rest:
                        await self.session_pool.rest(
                            session.session_path, action.rest_seconds,
                        )
                        self.stats.messages_failed += 1
                        return  # Don't burn, just rest

                    elif action.should_retry and action.retry_after:
                        await asyncio.sleep(action.retry_after)
                        continue

                    elif action.should_skip_target:
                        await self.target_scraper.mark_skipped(
                            target.user_id, str(e),
                        )
                        self.stats.targets_skipped += 1
                        continue

                    else:
                        self.stats.messages_failed += 1
                        continue

                # Phase 2c: Post-message delay (except last in batch)
                if msg_num < batch_size - 1:
                    await self.anti_ban.post_message_delay()

        except Exception as e:
            error_name = type(e).__name__
            logger.error("Session cycle error: {}: {}", error_name, e)

            action = self.anti_ban.handle_error(e)
            if action.should_burn:
                burn_reason = action.burn_reason.value
            if action.alert_admin:
                await self._notify_admin(action.alert_message)

            self.stats.errors.append(f"{error_name}: {e}")

        finally:
            # ── Phase 3: Disconnect + burn ───────────────────────────────
            try:
                await client.disconnect()
            except Exception:
                pass

            if burn_reason:
                await self.session_pool.burn(session.session_path, burn_reason)
                self.stats.sessions_burned += 1
                logger.warning(
                    "Session {} BURNED: {}", session.phone, burn_reason,
                )
            else:
                # Throwaway model: burn even after successful batch
                await self.session_pool.burn(
                    session.session_path, "batch_complete",
                )
                self.stats.sessions_burned += 1
                logger.info(
                    "Session {} retired (batch complete)", session.phone,
                )

            # Unbind API entry
            if api_entry:
                self.anti_ban.api_pool.unbind_session(api_entry.api_id)

            # ── Phase 4: Rotate proxy IP + stabilise ─────────────────────
            try:
                await self.proxy_router.rotate_and_rebind(session.phone)
                self.stats.proxy_rotations += 1
                # IP stabilisation: 12s base + random 0-3s jitter
                # Research report: "wait 12s + random(0,3) after rotation"
                stab_delay = 12.0 + secrets.randbelow(4)
                logger.info("IP stabilisation delay: {:.1f}s", stab_delay)
                await asyncio.sleep(stab_delay)
            except Exception as e:
                logger.warning("Proxy rotation failed: {}", e)

            # ── Phase 5: Inter-session Gaussian delay ────────────────────
            await self.anti_ban.post_session_delay()

            # Progress log every 5 sessions
            if self.stats.sessions_used % 5 == 0:
                logger.info(
                    "--- Progress: {} sent, {} burned, "
                    "burn rate: {:.0%}, delivery: {:.0%} ---",
                    self.stats.messages_sent,
                    self.stats.sessions_burned,
                    self.stats.burn_rate,
                    self.stats.delivery_rate,
                )

    # ── controls ────────────────────────────────────────────────────────────

    async def pause(self):
        """Pause the campaign."""
        self._paused = True
        self.stats.is_paused = True
        self.stats.pause_reason = "manual_pause"
        logger.info("Campaign paused")

    async def resume(self):
        """Resume a paused campaign."""
        self._paused = False
        self.stats.is_paused = False
        self.stats.pause_reason = ""
        logger.info("Campaign resumed")
        await self.run()

    async def stop(self):
        """Stop the campaign."""
        self._running = False
        logger.info("Campaign stopped")

    # ── admin notification ──────────────────────────────────────────────────

    async def _notify_admin(self, message: str):
        """Send notification to admin via Telegram Bot API."""
        if not self.config.bot_token or not self.config.admin_chat_id:
            return

        try:
            url = (
                f"https://api.telegram.org/bot{self.config.bot_token}"
                f"/sendMessage"
            )
            async with aiohttp.ClientSession() as http:
                await http.post(
                    url,
                    json={
                        "chat_id": self.config.admin_chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                )
        except Exception as e:
            logger.warning("Admin notification failed: {}", e)
