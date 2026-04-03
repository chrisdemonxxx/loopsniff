from pydantic import BaseModel
from typing import Optional


class OverallMetrics(BaseModel):
    total_leads: int = 0
    total_contacted: int = 0
    total_replied: int = 0
    total_qualified: int = 0
    total_converted: int = 0
    total_lost: int = 0
    reply_rate: float = 0.0
    qualification_rate: float = 0.0
    conversion_rate: float = 0.0
    avg_messages_per_lead: float = 0.0


class CampaignMetrics(BaseModel):
    campaign_id: str
    campaign_name: str
    enrolled: int = 0
    sent: int = 0
    replied: int = 0
    converted: int = 0
    reply_rate: float = 0.0
    conversion_rate: float = 0.0


class StepMetrics(BaseModel):
    step_order: int
    template_a_preview: Optional[str] = None
    template_b_preview: Optional[str] = None
    sent: int = 0
    replied: int = 0
    drop_off_rate: float = 0.0


class ABResult(BaseModel):
    step_order: int
    variant_a_sent: int = 0
    variant_a_replied: int = 0
    variant_a_rate: float = 0.0
    variant_b_sent: int = 0
    variant_b_replied: int = 0
    variant_b_rate: float = 0.0
    winner: Optional[str] = None
    significance: Optional[float] = None


class DailySendStats(BaseModel):
    date: str
    sent: int = 0
    replied: int = 0
