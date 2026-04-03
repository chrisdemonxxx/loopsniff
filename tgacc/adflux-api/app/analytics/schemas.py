from pydantic import BaseModel
from typing import Optional, Any
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID


class OverviewMetrics(BaseModel):
    total_spend: Decimal = Decimal("0")
    total_impressions: int = 0
    total_clicks: int = 0
    total_conversions: int = 0
    roas: Optional[Decimal] = None
    ctr: Optional[Decimal] = None
    cpc: Optional[Decimal] = None
    active_accounts: int = 0
    active_campaigns: int = 0


class CampaignMetrics(BaseModel):
    account_id: UUID
    account_name: Optional[str] = None
    platform: str
    date: date
    spend: Decimal = Decimal("0")
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    ctr: Optional[Decimal] = None
    cpc: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class DailyMetrics(BaseModel):
    date: date
    spend: Decimal = Decimal("0")
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0


class PlatformMetrics(BaseModel):
    platform: str
    spend: Decimal = Decimal("0")
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    accounts: int = 0


class TopPerformingItem(BaseModel):
    account_id: UUID
    account_name: Optional[str] = None
    platform: str
    metric_value: Decimal = Decimal("0")
    spend: Decimal = Decimal("0")
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0


class AccountSyncResult(BaseModel):
    ad_account_id: UUID
    meta_account_id: str
    records_created: int = 0
    error: Optional[str] = None


class SyncSummary(BaseModel):
    accounts_processed: int = 0
    total_records_created: int = 0
    errors: int = 0
    results: list[AccountSyncResult] = []
