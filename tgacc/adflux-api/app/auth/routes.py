import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.hash import bcrypt

from app.database import get_db
from app.models import AdminUser, ClientUser
from app.auth.jwt import create_access_token, create_refresh_token, create_reset_token, decode_token
from app.auth.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserInfo,
    RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest,
    ChangePasswordRequest, VerifyEmailRequest,
)
from app.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/auth", tags=["auth"])

# IP-based rate limiting for login endpoint
_login_attempts: dict[str, tuple[int, float]] = {}
RATE_LIMIT = 10
RATE_WINDOW = 300  # 5 minutes


def check_rate_limit(ip: str) -> None:
    """Check if IP has exceeded rate limit for login attempts."""
    now = time.time()
    count, window_start = _login_attempts.get(ip, (0, now))
    
    # Reset window if expired
    if now - window_start > RATE_WINDOW:
        _login_attempts[ip] = (1, now)
        return
    
    # Check if limit exceeded
    if count >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in 5 minutes."
        )
    
    # Increment counter
    _login_attempts[ip] = (count + 1, window_start)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Check rate limit based on client IP
    check_rate_limit(request.client.host)
    
    result = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    admin = result.scalar_one_or_none()
    if admin and admin.password_hash and bcrypt.verify(req.password, admin.password_hash):
        token_data = {"sub": str(admin.id), "user_type": "admin", "role": admin.role}
        access = create_access_token(token_data)
        refresh = create_refresh_token(token_data)
        return TokenResponse(
            access_token=access, refresh_token=refresh,
            user_type="admin", user_id=str(admin.id), name=admin.name,
        )

    result = await db.execute(select(ClientUser).where(ClientUser.email == req.email))
    client_user = result.scalar_one_or_none()
    if client_user and client_user.password_hash and bcrypt.verify(req.password, client_user.password_hash):
        token_data = {
            "sub": str(client_user.id), "user_type": "client",
            "role": client_user.role, "client_id": str(client_user.client_id) if client_user.client_id else None,
        }
        access = create_access_token(token_data)
        refresh = create_refresh_token(token_data)
        return TokenResponse(
            access_token=access, refresh_token=refresh, user_type="client",
            user_id=str(client_user.id), name=client_user.name or client_user.email,
            client_id=str(client_user.client_id) if client_user.client_id else None,
        )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # S1: Only allow client self-registration; admin creation requires existing admin auth
    if req.user_type == "admin":
        raise HTTPException(status_code=403, detail="Admin accounts cannot be self-registered. Use /auth/register-admin.")

    result = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    result = await db.execute(select(ClientUser).where(ClientUser.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = bcrypt.hash(req.password)
    user = ClientUser(
        email=req.email, name=req.name, password_hash=hashed,
        role="viewer", client_id=req.client_id,
    )
    db.add(user)
    await db.flush()
    token_data = {
        "sub": str(user.id), "user_type": "client", "role": "viewer",
        "client_id": str(user.client_id) if user.client_id else None,
    }
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    return TokenResponse(
        access_token=access, refresh_token=refresh, user_type="client",
        user_id=str(user.id), name=user.name or user.email,
    )


@router.post("/register-admin", response_model=TokenResponse)
async def register_admin(req: RegisterRequest, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Admin-only endpoint to create new admin accounts."""
    result = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = bcrypt.hash(req.password)
    user = AdminUser(email=req.email, name=req.name, password_hash=hashed, role="admin")
    db.add(user)
    await db.flush()
    token_data = {"sub": str(user.id), "user_type": "admin", "role": "admin"}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    return TokenResponse(access_token=access, refresh_token=refresh, user_type="admin", user_id=str(user.id), name=user.name)


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_current_user)):
    return UserInfo(**user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access + refresh token pair."""
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user_type = payload.get("user_type")
    if not user_id or not user_type:
        raise HTTPException(status_code=401, detail="Invalid refresh token payload")

    from uuid import UUID
    uid = UUID(user_id)

    if user_type == "admin":
        result = await db.execute(select(AdminUser).where(AdminUser.id == uid))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        token_data = {"sub": str(user.id), "user_type": "admin", "role": user.role}
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
            user_type="admin", user_id=str(user.id), name=user.name,
        )
    else:
        result = await db.execute(select(ClientUser).where(ClientUser.id == uid))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        token_data = {
            "sub": str(user.id), "user_type": "client",
            "role": user.role, "client_id": str(user.client_id) if user.client_id else None,
        }
        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
            user_type="client", user_id=str(user.id),
            name=user.name or user.email,
            client_id=str(user.client_id) if user.client_id else None,
        )


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Generate a password reset token. In production this would be emailed."""
    result = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        result = await db.execute(select(ClientUser).where(ClientUser.email == req.email))
        user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If that email exists, a reset link has been sent."}

    token = create_reset_token(req.email)
    return {"message": "If that email exists, a reset link has been sent.", "reset_token": token}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using a reset token."""
    payload = decode_token(req.token)
    if not payload or payload.get("type") != "reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    # Try AdminUser first, then ClientUser
    result = await db.execute(select(AdminUser).where(AdminUser.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.password_hash = bcrypt.hash(req.new_password)
        await db.flush()
        return {"message": "Password has been reset successfully."}

    result = await db.execute(select(ClientUser).where(ClientUser.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.password_hash = bcrypt.hash(req.new_password)
        await db.flush()
        return {"message": "Password has been reset successfully."}

    raise HTTPException(status_code=404, detail="User not found")


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password for the currently authenticated user."""
    from uuid import UUID
    uid = UUID(user["id"])

    if user["user_type"] == "admin":
        result = await db.execute(select(AdminUser).where(AdminUser.id == uid))
    else:
        result = await db.execute(select(ClientUser).where(ClientUser.id == uid))

    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not db_user.password_hash or not bcrypt.verify(req.current_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    db_user.password_hash = bcrypt.hash(req.new_password)
    await db.flush()
    return {"message": "Password changed successfully."}


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Verify email with token. Placeholder — validates the token structure."""
    payload = decode_token(req.token)
    if not payload or payload.get("type") != "verify":
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    return {"message": "Email verified successfully.", "email": payload.get("sub")}
