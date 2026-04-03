from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    user_type: str = "client"  # "admin" or "client"
    client_id: Optional[UUID] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user_type: str
    user_id: str
    name: str
    client_id: Optional[str] = None


class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    role: str
    user_type: str
    client_id: Optional[str] = None
    is_active: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str
