"""Channel-agnostic message / response contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

ChannelName = Literal[
    "telegram_userbot",
    "telegram_bot",
    "whatsapp",
    "messenger",
    "instagram",
    "web_admin",
    "web_client",
    "web_anon",
]


@dataclass
class NormalizedMessage:
    channel: ChannelName
    conversation_id: str
    user_id: str
    text: str
    username: Optional[str] = None
    role: Literal["user", "admin"] = "user"
    metadata: dict = field(default_factory=dict)


@dataclass
class NormalizedResponse:
    text: str
    channel: ChannelName
    conversation_id: str
    bant_score: int = 0
    bant_tier: str = "cold"
    stage: str = "opener"
    action: Optional[str] = None
    action_payload: dict = field(default_factory=dict)
    guardrail_action: str = "allow"
    prompt_version: str = "v3"
