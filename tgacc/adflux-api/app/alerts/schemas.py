from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class AlertOut(BaseModel):
    id: UUID
    title: str
    message: str
    type: str
    scope: str
    target_client_id: Optional[UUID]
    show_banner: bool
    send_email: bool
    is_active: bool
    starts_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertCreate(BaseModel):
    title: str
    message: str
    type: str = "info"
    scope: str = "global"
    target_client_id: Optional[UUID] = None
    show_banner: bool = False
    send_email: bool = False
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class AlertUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None
    show_banner: Optional[bool] = None
    send_email: Optional[bool] = None
    expires_at: Optional[datetime] = None
