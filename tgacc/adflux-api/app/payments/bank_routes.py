"""Bank transfer deposit endpoints."""

import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.auth.dependencies import get_current_user, require_admin
from app.config import get_settings
from app.database import get_db
from app.models import BankTransferRequest, Wallet, WalletTransaction

from app.payments.schemas import (
    BankTransferDepositRequest,
    BankTransferDepositResponse,
    BankTransferRequestOut,
    BankTransferConfirmRequest,
    BankTransferRejectRequest,
)

log = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/payments/bank", tags=["payments"])


def _require_client_id(user: dict) -> UUID:
    cid = user.get("client_id")
    if not cid:
        raise HTTPException(status_code=403, detail="No client account linked")
    return UUID(cid) if isinstance(cid, str) else cid


async def _get_or_create_wallet(db: AsyncSession, client_id: UUID) -> Wallet:
    result = await db.execute(select(Wallet).where(Wallet.client_id == client_id))
    wallet = result.scalar_one_or_none()
    if wallet:
        return wallet
    wallet = Wallet(client_id=client_id, currency="USD", balance=Decimal("0"), frozen_balance=Decimal("0"))
    db.add(wallet)
    await db.flush()
    await db.refresh(wallet)
    return wallet


def _generate_reference_code() -> str:
    return f"AF-{secrets.token_hex(4).upper()}"


def _bank_details() -> dict:
    return {
        "bank_name": settings.BANK_NAME,
        "account_number": settings.BANK_ACCOUNT_NUMBER,
        "swift_bic": settings.BANK_SWIFT_BIC,
    }


# ── Client endpoints ────────────────────────────────────────────────────────

@router.post("/request", response_model=BankTransferDepositResponse, status_code=201)
async def create_bank_transfer_request(
    data: BankTransferDepositRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a bank transfer deposit request with bank instructions."""
    client_id = _require_client_id(user)
    reference_code = _generate_reference_code()

    bank = _bank_details()
    req = BankTransferRequest(
        client_id=client_id,
        amount=data.amount,
        currency=data.currency,
        reference_code=reference_code,
        bank_name=bank["bank_name"],
        account_number=bank["account_number"],
        swift_bic=bank["swift_bic"],
        status="pending",
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)

    return BankTransferDepositResponse(
        request_id=req.id,
        amount=req.amount,
        currency=req.currency,
        reference_code=reference_code,
        status=req.status,
        bank_details={
            **bank,
            "reference_code": reference_code,
            "instructions": (
                f"Transfer {data.amount} {data.currency} to the account below. "
                f"Use reference code '{reference_code}' in the payment description."
            ),
        },
        created_at=req.created_at,
    )


@router.get("/requests", response_model=list[BankTransferRequestOut])
async def list_bank_transfer_requests(
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current client's bank transfer requests."""
    client_id = _require_client_id(user)
    stmt = select(BankTransferRequest).where(BankTransferRequest.client_id == client_id)
    if status:
        stmt = stmt.where(BankTransferRequest.status == status)
    stmt = stmt.order_by(BankTransferRequest.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Admin endpoints ─────────────────────────────────────────────────────────

@router.put("/requests/{request_id}/confirm", response_model=BankTransferRequestOut)
async def confirm_bank_transfer(
    request_id: UUID,
    data: BankTransferConfirmRequest,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin confirms that a bank transfer has been received."""
    result = await db.execute(
        select(BankTransferRequest).where(BankTransferRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Bank transfer request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    req.status = "confirmed"
    req.confirmed_at = datetime.now(timezone.utc)
    req.admin_note = data.admin_note

    # Credit the client's wallet
    wallet = await _get_or_create_wallet(db, req.client_id)
    wallet.balance += req.amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        type="deposit",
        amount=req.amount,
        fee=Decimal("0"),
        net_amount=req.amount,
        currency=req.currency,
        payment_method="bank_transfer",
        payment_reference=req.reference_code,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        notes=f"Bank transfer confirmed (ref: {req.reference_code})",
    )
    db.add(txn)
    await db.flush()
    await db.refresh(req)
    log.info("Bank transfer confirmed: request=%s amount=%s client=%s", request_id, req.amount, req.client_id)
    return req


@router.put("/requests/{request_id}/reject", response_model=BankTransferRequestOut)
async def reject_bank_transfer(
    request_id: UUID,
    data: BankTransferRejectRequest,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin rejects a bank transfer request."""
    result = await db.execute(
        select(BankTransferRequest).where(BankTransferRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Bank transfer request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    req.status = "rejected"
    req.admin_note = data.reason
    await db.flush()
    await db.refresh(req)
    log.info("Bank transfer rejected: request=%s reason=%s", request_id, data.reason)
    return req
