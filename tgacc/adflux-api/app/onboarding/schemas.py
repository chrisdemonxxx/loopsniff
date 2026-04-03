from pydantic import BaseModel
from typing import Optional


class OnboardingRegister(BaseModel):
    name: str
    email: str
    password: str
    company_name: Optional[str] = None
    phone: Optional[str] = None


class PlatformSelectRequest(BaseModel):
    platforms: list[str]  # e.g. ["meta", "google", "tiktok", "snapchat"]


class PlanSelectRequest(BaseModel):
    plan_slug: str
    interval: str = "monthly"  # monthly, semiannual, annual


class OnboardingCompleteRequest(BaseModel):
    payment_method: Optional[str] = None  # "stripe" or "pay_later"


class OnboardingStatusOut(BaseModel):
    user_id: str
    client_id: Optional[str] = None
    account_created: bool = False
    platforms_selected: bool = False
    plan_selected: bool = False
    onboarding_completed: bool = False
    selected_platforms: list[str] = []
    selected_plan: Optional[str] = None
    selected_interval: Optional[str] = None
