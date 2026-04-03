"""Campaign manager — orchestrates account rotation, rate limiting, send windows."""
import asyncio, logging, random
from datetime import datetime
from typing import Optional

from . import config, db
from .models import Account

log = logging.getLogger(__name__)

class CampaignManager:
    """Manages account assignment and rate limiting for campaigns."""
    
    def __init__(self):
        self._account_sends_today: dict[str, int] = {}
        self.max_per_account = config.ULTRA_SAFE_DM_LIMIT
    
    async def get_best_account(self) -> Optional[Account]:
        """Get account with lowest sends today (rotation strategy)."""
        accounts = await db.get_accounts(status="active")
        if not accounts:
            return None
        
        # Sort by sends today (ascending) — least used first
        accounts.sort(key=lambda a: a.dms_sent_today)
        
        for acct in accounts:
            if acct.dms_sent_today < self.max_per_account:
                return acct
        
        return None  # All accounts at limit
    
    def is_in_send_window(self, start_hour: int = 9, end_hour: int = 21) -> bool:
        """Check if current UTC hour is within send window."""
        hour = datetime.utcnow().hour
        return start_hour <= hour < end_hour
    
    async def get_daily_capacity(self) -> dict:
        """Calculate remaining daily capacity across all accounts."""
        accounts = await db.get_accounts(status="active")
        total_limit = len(accounts) * self.max_per_account
        total_sent = sum(a.dms_sent_today for a in accounts)
        return {
            "active_accounts": len(accounts),
            "total_limit": total_limit,
            "total_sent": total_sent,
            "remaining": total_limit - total_sent,
        }
    
    async def reset_daily_counts(self):
        """Reset all account daily counters."""
        await db.reset_daily_dm_counts()
        self._account_sends_today.clear()
        log.info("Daily send counts reset")
    
    async def get_account_stats(self) -> list[dict]:
        """Get per-account send statistics."""
        accounts = await db.get_accounts(status="active")
        return [
            {
                "phone": a.phone,
                "dms_today": a.dms_sent_today,
                "dms_total": a.total_dms_sent,
                "limit": self.max_per_account,
                "available": self.max_per_account - a.dms_sent_today,
                "last_used": a.last_used.isoformat() if a.last_used else None,
            }
            for a in accounts
        ]
