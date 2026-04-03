from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import AdminUser, ClientUser
from app.auth.jwt import decode_token

security = HTTPBearer()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_type = payload.get("user_type")
    user_id = payload.get("sub")
    if not user_type or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    uid = UUID(user_id)
    if user_type == "admin":
        result = await db.execute(select(AdminUser).where(AdminUser.id == uid))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return {
            "id": str(user.id), "email": user.email, "name": user.name,
            "role": user.role, "user_type": "admin", "client_id": None, "is_active": user.is_active,
        }
    else:
        result = await db.execute(select(ClientUser).where(ClientUser.id == uid))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        return {
            "id": str(user.id), "email": user.email, "name": user.name,
            "role": user.role, "user_type": "client",
            "client_id": str(user.client_id) if user.client_id else None,
            "is_active": user.is_active,
        }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["user_type"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_role(*roles: str):
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles and user["user_type"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _check
