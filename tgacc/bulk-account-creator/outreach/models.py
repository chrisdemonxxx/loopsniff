"""Data models used across the outreach engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    phone: str
    session_file: str
    status: str  # fresh | warming | ready | active | banned | resting
    created_at: datetime
    warmed_at: Optional[datetime] = None
    dms_sent_today: int = 0
    total_dms_sent: int = 0
    spam_reports: int = 0
    last_used: Optional[datetime] = None


@dataclass
class Lead:
    username: str
    source: str  # bhw | aw | hackforums | exploit
    status: str = "new"  # new | contacted | replied | qualified | hot | dead | blocked
    language: str = "en"
    niche: Optional[str] = None
    budget_tier: Optional[str] = None
    contacted_at: Optional[datetime] = None
    contacted_by: Optional[str] = None
    reply_count: int = 0
    bant_score: int = 0
    notes: str = ""


@dataclass
class Message:
    lead_username: str
    account_phone: str
    direction: str  # outbound | inbound
    text: str
    sent_at: datetime
    template_id: Optional[str] = None
