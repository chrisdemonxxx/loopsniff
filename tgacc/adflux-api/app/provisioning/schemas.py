from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime
from uuid import UUID


class ProvisioningRequestCreate(BaseModel):
    platform: str  # meta, google, tiktok, snapchat
    business_name: str
    business_url: Optional[str] = None
    business_type: Optional[str] = None
    spend_limit: Optional[Decimal] = None
    currency: str = "USD"
    timezone: str = "UTC"
    notes: Optional[str] = None


class ProvisioningRequestOut(BaseModel):
    id: UUID
    client_id: UUID
    platform: str
    business_name: str
    business_url: Optional[str] = None
    business_type: Optional[str] = None
    spend_limit: Optional[Decimal] = None
    currency: str
    timezone: str
    status: str
    admin_notes: Optional[str] = None
    reject_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProvisioningApproval(BaseModel):
    account_id: Optional[str] = None  # external platform account id
    account_name: Optional[str] = None
    daily_limit: Optional[Decimal] = None
    admin_notes: Optional[str] = None


class ProvisioningRejection(BaseModel):
    reason: str


class PlatformInfo(BaseModel):
    platform: str
    display_name: str
    requirements: list[str]
    supported_currencies: list[str]
    min_spend: Optional[Decimal] = None


class ProvisioningExecuteRequest(BaseModel):
    access_token: str
    business_manager_id: str


class ProvisioningExecuteOut(BaseModel):
    request_id: UUID
    status: str
    platform_account_id: Optional[str] = None
    ad_account_id: Optional[UUID] = None
    error: Optional[str] = None
