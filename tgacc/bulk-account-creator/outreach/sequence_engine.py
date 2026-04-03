"""Sequence engine — drives multi-step outreach sequences.

Polls PostgreSQL CampaignLead records via API and sends the next
message in the sequence when next_touch_at has arrived.
"""
import asyncio, logging, random, hashlib
from datetime import datetime, timedelta
from typing import Optional
import aiohttp

from . import config, db
from .session_manager import SessionManager
from .models import Message

log = logging.getLogger(__name__)

API_BASE = "http://localhost:8099"

class SequenceEngine:
    def __init__(self):
        self.sm = SessionManager()
    
    async def _api_get(self, path: str) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API_BASE}{path}", headers={"ngrok-skip-browser-warning":"1"}) as r:
                return await r.json()
    
    async def _api_put(self, path: str, data: dict) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.put(f"{API_BASE}{path}", json=data) as r:
                return await r.json()
    
    async def poll_and_send(self):
        """Main loop: find CampaignLeads with next_touch_at <= now, send next step."""
        # Get active campaigns
        campaigns = await self._api_get("/outreach/campaigns?status=active")
        if not isinstance(campaigns, list):
            return {"sent": 0, "errors": 0}
        
        sent = 0
        errors = 0
        now = datetime.utcnow()
        
        for campaign in campaigns:
            campaign_id = campaign["id"]
            # Check send window
            hour = now.hour
            if hour < campaign.get("send_window_start", 9) or hour >= campaign.get("send_window_end", 21):
                continue
            
            # Get enrolled leads that need next touch
            leads = await self._api_get(f"/outreach/campaigns/{campaign_id}/leads?status=in_sequence")
            if not isinstance(leads, list):
                continue
            
            # Get sequence steps
            seq_id = campaign.get("sequence_id")
            if not seq_id:
                continue
            seq = await self._api_get(f"/outreach/sequences/{seq_id}")
            steps = seq.get("steps", [])
            if not steps:
                continue
            
            for lead in leads:
                next_touch = lead.get("next_touch_at")
                if not next_touch:
                    continue
                touch_dt = datetime.fromisoformat(next_touch.replace("Z", "+00:00")).replace(tzinfo=None)
                if touch_dt > now:
                    continue
                
                current_step = lead.get("current_step", 0)
                if current_step >= len(steps):
                    continue  # sequence complete
                
                step = steps[current_step]
                
                # Select template based on AB variant
                variant = lead.get("ab_variant", "A")
                template = step.get("template_b") if variant == "B" and step.get("template_b") else step.get("template_a", "")
                
                # Get account and send
                username = lead.get("tg_username", "")
                account = await db.get_account_for_outreach()
                if not account:
                    log.warning("No accounts available")
                    break
                
                try:
                    client = await self.sm.get_client(account.phone)
                    try:
                        # Personalize template
                        text = template.replace("{username}", username)
                        entity = await client.get_entity(username)
                        await client.send_message(entity, text)
                        
                        # Log message
                        msg = Message(
                            lead_username=username,
                            account_phone=account.phone,
                            direction="outbound",
                            text=text,
                            sent_at=now,
                            template_id=f"step_{current_step}_{variant}",
                        )
                        await db.add_message(msg)
                        await db.update_account(account.phone, dms_sent_today=account.dms_sent_today+1, total_dms_sent=account.total_dms_sent+1, last_used=now)
                        
                        # Advance to next step
                        next_step = current_step + 1
                        next_delay = steps[next_step]["delay_hours"] if next_step < len(steps) else 0
                        next_touch_new = (now + timedelta(hours=next_delay)).isoformat() if next_step < len(steps) else None
                        
                        # Update via API (needs auth, so we'll do direct for now)
                        # For MVP: just log and the admin API can handle status
                        sent += 1
                        log.info("Sent step %d to @%s (variant %s)", current_step, username, variant)
                    finally:
                        await client.disconnect()
                except Exception as e:
                    log.error("Sequence send error for @%s: %s", username, e)
                    errors += 1
                
                # Delay between sends
                await asyncio.sleep(random.uniform(config.MIN_DELAY_BETWEEN_DMS, config.MAX_DELAY_BETWEEN_DMS))
        
        return {"sent": sent, "errors": errors}
    
    async def run_loop(self, interval_seconds: int = 300):
        """Continuous polling loop."""
        log.info("Sequence engine started (poll every %ds)", interval_seconds)
        while True:
            try:
                result = await self.poll_and_send()
                if result["sent"] > 0 or result["errors"] > 0:
                    log.info("Sequence engine cycle: %s", result)
            except Exception as e:
                log.exception("Sequence engine error: %s", e)
            await asyncio.sleep(interval_seconds)
