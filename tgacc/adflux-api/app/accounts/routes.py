from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models import AdAccount, BanTransfer
from app.auth.dependencies import get_current_user, require_admin
from app.accounts.schemas import AccountCreate, AccountUpdate, AccountOut, BanRequest, FundTransferRequest

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    client_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    skip: int = 0, limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # S2: Force client_id filter for client users
    if user.get("user_type") == "client":
        client_id = UUID(user["client_id"]) if user.get("client_id") else None
        if not client_id:
            return []
    stmt = select(AdAccount)
    if client_id:
        stmt = stmt.where(AdAccount.client_id == client_id)
    if status:
        stmt = stmt.where(AdAccount.status == status)
    if platform:
        stmt = stmt.where(AdAccount.platform == platform)
    stmt = stmt.order_by(AdAccount.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: UUID, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdAccount).where(AdAccount.id == account_id))
    acct = result.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    # S2: Clients can only view their own accounts
    if user.get("user_type") == "client" and user.get("client_id") and str(user["client_id"]) != str(acct.client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return acct


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(data: AccountCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    acct = AdAccount(**data.model_dump())
    db.add(acct)
    await db.flush()
    await db.commit()
    await db.refresh(acct)
    return acct


@router.put("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: UUID, data: AccountUpdate,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdAccount).where(AdAccount.id == account_id))
    acct = result.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(acct, k, v)
    await db.flush()
    await db.commit()
    await db.refresh(acct)
    return acct


@router.post("/{account_id}/ban", response_model=AccountOut)
async def ban_account(
    account_id: UUID, data: BanRequest,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdAccount).where(AdAccount.id == account_id))
    acct = result.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    acct.status = "banned"
    acct.banned_at = datetime.now(timezone.utc)
    acct.ban_reason = data.reason
    await db.flush()
    await db.commit()
    await db.refresh(acct)
    return acct


@router.post("/{account_id}/transfer")
async def transfer_funds(
    account_id: UUID, data: FundTransferRequest,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdAccount).where(AdAccount.id == account_id))
    banned_acct = result.scalar_one_or_none()
    if not banned_acct:
        raise HTTPException(status_code=404, detail="Source account not found")

    result = await db.execute(select(AdAccount).where(AdAccount.id == data.new_account_id))
    new_acct = result.scalar_one_or_none()
    if not new_acct:
        raise HTTPException(status_code=404, detail="Destination account not found")

    amount = data.amount if data.amount is not None else banned_acct.balance
    if amount > banned_acct.balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    banned_acct.balance -= amount
    new_acct.balance += amount
    banned_acct.replaced_by = new_acct.id

    transfer = BanTransfer(
        banned_account=banned_acct.id, new_account=new_acct.id,
        amount=amount, status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(transfer)
    await db.flush()
    await db.commit()
    return {"detail": "Transfer completed", "amount": float(amount)}


@router.delete("/{account_id}")
async def delete_account(account_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdAccount).where(AdAccount.id == account_id))
    acct = result.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(acct)
    return {"detail": "Account deleted"}
