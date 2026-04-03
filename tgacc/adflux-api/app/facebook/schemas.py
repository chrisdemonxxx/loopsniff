from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Auth ──

class FacebookAuthURL(BaseModel):
    auth_url: str


class FacebookCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


class FacebookTokenResponse(BaseModel):
    connected: bool
    facebook_user_id: str
    name: str
    message: str


# ── Pages ──

class FacebookPage(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    access_token: Optional[str] = None
    connected: bool = False


class FacebookPageList(BaseModel):
    pages: list[FacebookPage]


class FacebookPageConnect(BaseModel):
    page_id: str
    name: str


# ── Instagram Accounts ──

class InstagramAccount(BaseModel):
    id: str
    username: Optional[str] = None
    name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    followers_count: Optional[int] = None
    connected: bool = False


class InstagramAccountList(BaseModel):
    accounts: list[InstagramAccount]


# ── Ad Accounts ──

class MetaAdAccountInfo(BaseModel):
    id: str
    account_id: str  # act_XXXXX
    name: str
    currency: Optional[str] = None
    timezone: Optional[str] = None
    business_name: Optional[str] = None
    connected: bool = False


class MetaAdAccountList(BaseModel):
    ad_accounts: list[MetaAdAccountInfo]


class MetaAdAccountConnect(BaseModel):
    account_id: str
    name: str
    currency: Optional[str] = None
    timezone: Optional[str] = None


# ── Status ──

class FacebookConnectionStatus(BaseModel):
    connected: bool
    facebook_user_id: Optional[str] = None
    facebook_user_name: Optional[str] = None
    connected_at: Optional[datetime] = None
    pages: list[FacebookPage] = []
    instagram_accounts: list[InstagramAccount] = []
    ad_accounts: list[MetaAdAccountInfo] = []


class DisconnectResponse(BaseModel):
    disconnected: bool
    message: str
