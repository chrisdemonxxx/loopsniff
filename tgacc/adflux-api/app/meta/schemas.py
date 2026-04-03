from pydantic import BaseModel
from typing import Optional, Any
from decimal import Decimal
from datetime import datetime


# ── Campaign ──

class CampaignCreate(BaseModel):
    ad_account_id: str
    access_token: str
    name: str
    objective: str  # TRAFFIC, LEADS, SALES, AWARENESS, ENGAGEMENT, APP_PROMOTION
    status: str = "PAUSED"
    special_ad_categories: list[str] = []
    buying_type: str = "AUCTION"
    daily_budget: Optional[int] = None  # in cents
    lifetime_budget: Optional[int] = None
    bid_strategy: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class CampaignStatusUpdate(BaseModel):
    access_token: str
    status: str  # ACTIVE, PAUSED, DELETED, ARCHIVED


class CampaignOut(BaseModel):
    id: str
    name: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None


# ── Ad Set ──

class AdSetCreate(BaseModel):
    ad_account_id: str
    access_token: str
    campaign_id: str
    name: str
    status: str = "PAUSED"
    daily_budget: Optional[int] = None
    lifetime_budget: Optional[int] = None
    bid_strategy: Optional[str] = None
    bid_amount: Optional[int] = None
    optimization_goal: Optional[str] = None
    billing_event: str = "IMPRESSIONS"
    targeting: dict[str, Any] = {}
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class AdSetOut(BaseModel):
    id: str
    name: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None


# ── Ad ──

class AdCreate(BaseModel):
    ad_account_id: str
    access_token: str
    adset_id: str
    name: str
    status: str = "PAUSED"
    creative: dict[str, Any] = {}
    tracking_specs: Optional[list[dict]] = None


class AdOut(BaseModel):
    id: str
    name: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None


# ── Insights ──

class InsightsRequest(BaseModel):
    access_token: str
    date_preset: str = "last_30d"


class InsightsOut(BaseModel):
    data: list[dict[str, Any]]


# ── Targeting ──

class TargetingSearchResult(BaseModel):
    id: str
    name: str
    audience_size_lower_bound: Optional[int] = None
    audience_size_upper_bound: Optional[int] = None
    type: Optional[str] = None
    path: Optional[list[str]] = None


class TargetingSearchOut(BaseModel):
    results: list[TargetingSearchResult]


# ── Image Upload ──

class ImageUploadOut(BaseModel):
    image_hash: Optional[str] = None
    image_url: Optional[str] = None
    message: Optional[str] = None
