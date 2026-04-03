from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional

from app.database import get_db
from app.models import Wallet, WalletTransaction, DepositConfig, AdAccount
from app.auth.dependencies import get_current_user, require_admin
from app.wallet.schemas import (
    WalletOut,
    WalletTransactionOut,
    DepositRequest,
    WithdrawalRequest,
    TransferRequest,
    DepositConfigOut,
    DepositConfigCreate,
)

router = APIRouter(tags=["wallet"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAYMENT_METHODS = {"crypto", "bank_transfer", "credit_card", "payoneer", "swift"}


def _require_client_id(user: dict) -> UUID:
    """Extract and validate client_id from the current user token."""
    cid = user.get("client_id")
    if not cid:
        raise HTTPException(status_code=403, detail="No client account linked")
    return UUID(cid) if isinstance(cid, str) else cid


async def _get_or_create_wallet(db: AsyncSession, client_id: UUID) -> Wallet:
    """Return the client's wallet, creating one if it doesn't exist."""
    result = await db.execute(
        select(Wallet).where(Wallet.client_id == client_id)
    )
    wallet = result.scalar_one_or_none()
    if wallet:
        return wallet
    wallet = Wallet(client_id=client_id, currency="USD", balance=Decimal("0"), frozen_balance=Decimal("0"))
    db.add(wallet)
    await db.flush()
    await db.commit()
    await db.refresh(wallet)
    return wallet


# ---------------------------------------------------------------------------
# Client endpoints — /wallet
# ---------------------------------------------------------------------------

@router.get("/wallet", response_model=WalletOut)
async def get_wallet(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's wallet (auto-creates if not exists)."""
    client_id = _require_client_id(user)
    wallet = await _get_or_create_wallet(db, client_id)
    return wallet


@router.get("/wallet/transactions", response_model=list[WalletTransactionOut])
async def list_wallet_transactions(
    status: Optional[str] = Query(None),
    tx_type: Optional[str] = Query(None, alias="type"),
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get wallet transaction history with optional filters."""
    client_id = _require_client_id(user)
    wallet = await _get_or_create_wallet(db, client_id)
    stmt = select(WalletTransaction).where(WalletTransaction.wallet_id == wallet.id)
    if status:
        stmt = stmt.where(WalletTransaction.status == status)
    if tx_type:
        stmt = stmt.where(WalletTransaction.type == tx_type)
    stmt = stmt.order_by(WalletTransaction.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/wallet/deposit", response_model=WalletTransactionOut, status_code=201)
async def initiate_deposit(
    data: DepositRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a deposit into the user's wallet."""
    if data.payment_method not in VALID_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Invalid payment method. Must be one of: {', '.join(sorted(VALID_PAYMENT_METHODS))}")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    client_id = _require_client_id(user)
    wallet = await _get_or_create_wallet(db, client_id)

    # Look up fee configuration
    result = await db.execute(
        select(DepositConfig).where(
            DepositConfig.payment_method == data.payment_method,
            DepositConfig.currency == data.currency,
            DepositConfig.is_active == True,
        )
    )
    config = result.scalar_one_or_none()

    fee = Decimal("0")
    if config:
        if data.amount < config.min_amount:
            raise HTTPException(status_code=400, detail=f"Minimum deposit amount is {config.min_amount} {data.currency}")
        if config.max_amount and data.amount > config.max_amount:
            raise HTTPException(status_code=400, detail=f"Maximum deposit amount is {config.max_amount} {data.currency}")
        fee = (data.amount * config.fee_percent / Decimal("100")) + config.fee_fixed

    net_amount = data.amount - fee

    txn = WalletTransaction(
        wallet_id=wallet.id,
        type="deposit",
        amount=data.amount,
        fee=fee,
        net_amount=net_amount,
        currency=data.currency,
        payment_method=data.payment_method,
        status="pending",
    )
    db.add(txn)
    await db.flush()
    await db.commit()
    await db.refresh(txn)
    return txn


@router.post("/wallet/withdraw", response_model=WalletTransactionOut, status_code=201)
async def request_withdrawal(
    data: WithdrawalRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request a withdrawal from the user's wallet."""
    if data.payment_method not in VALID_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Invalid payment method. Must be one of: {', '.join(sorted(VALID_PAYMENT_METHODS))}")
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    client_id = _require_client_id(user)
    wallet = await _get_or_create_wallet(db, client_id)

    available = wallet.balance - wallet.frozen_balance
    if data.amount > available:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Freeze the amount while withdrawal is pending
    wallet.frozen_balance += data.amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        type="withdrawal",
        amount=data.amount,
        fee=Decimal("0"),
        net_amount=data.amount,
        currency=data.currency,
        payment_method=data.payment_method,
        payment_reference=data.destination,
        status="pending",
    )
    db.add(txn)
    await db.flush()
    await db.commit()
    await db.refresh(txn)
    return txn


@router.post("/wallet/transfer", response_model=WalletTransactionOut, status_code=201)
async def transfer_to_account(
    data: TransferRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transfer funds from wallet to an ad account."""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    client_id = _require_client_id(user)
    wallet = await _get_or_create_wallet(db, client_id)

    available = wallet.balance - wallet.frozen_balance
    if data.amount > available:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Verify ad account exists and belongs to this client
    result = await db.execute(
        select(AdAccount).where(AdAccount.id == data.target_account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Ad account not found")
    if str(account.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail="Ad account does not belong to you")

    # Move funds
    wallet.balance -= data.amount
    account.balance += data.amount

    txn = WalletTransaction(
        wallet_id=wallet.id,
        type="transfer",
        amount=data.amount,
        fee=Decimal("0"),
        net_amount=data.amount,
        currency=wallet.currency,
        payment_reference=str(data.target_account_id),
        status="completed",
        completed_at=datetime.now(timezone.utc),
        notes=f"Transfer to ad account {data.target_account_id}",
    )
    db.add(txn)
    await db.flush()
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("/wallet/deposit-config", response_model=list[DepositConfigOut])
async def get_deposit_config(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get available deposit methods with their fees."""
    result = await db.execute(
        select(DepositConfig).where(DepositConfig.is_active == True)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Admin endpoints — /admin/wallets, /admin/wallet-transactions, /admin/deposit-config
# ---------------------------------------------------------------------------

@router.get("/admin/wallets", response_model=list[WalletOut])
async def admin_list_wallets(
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all wallets (admin only)."""
    result = await db.execute(
        select(Wallet).order_by(Wallet.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/admin/wallets/{client_id}", response_model=WalletOut)
async def admin_get_wallet(
    client_id: UUID,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific client's wallet (admin only)."""
    result = await db.execute(
        select(Wallet).where(Wallet.client_id == client_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found for this client")
    return wallet


@router.put("/admin/wallet-transactions/{txn_id}/status", response_model=WalletTransactionOut)
async def admin_update_transaction_status(
    txn_id: UUID,
    status: str = Query(..., description="New status: completed, failed, cancelled"),
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a wallet transaction's status (admin only)."""
    allowed_statuses = {"completed", "failed", "cancelled"}
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(sorted(allowed_statuses))}")

    result = await db.execute(
        select(WalletTransaction).where(WalletTransaction.id == txn_id)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.status != "pending":
        raise HTTPException(status_code=400, detail=f"Transaction is already {txn.status}")

    # Fetch the wallet for balance adjustments
    result = await db.execute(select(Wallet).where(Wallet.id == txn.wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Associated wallet not found")

    old_status = txn.status
    txn.status = status

    if status == "completed":
        txn.completed_at = datetime.now(timezone.utc)
        if txn.type == "deposit":
            wallet.balance += txn.net_amount
        elif txn.type == "withdrawal":
            wallet.balance -= txn.amount
            wallet.frozen_balance -= txn.amount
    elif status in ("failed", "cancelled"):
        if txn.type == "withdrawal":
            # Unfreeze the amount
            wallet.frozen_balance -= txn.amount

    await db.flush()
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("/admin/deposit-config", response_model=list[DepositConfigOut])
async def admin_list_deposit_configs(
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all deposit configurations (admin only)."""
    result = await db.execute(select(DepositConfig))
    return result.scalars().all()


@router.post("/admin/deposit-config", response_model=DepositConfigOut, status_code=201)
async def admin_create_deposit_config(
    data: DepositConfigCreate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new deposit configuration (admin only)."""
    config = DepositConfig(**data.model_dump())
    db.add(config)
    await db.flush()
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/admin/deposit-config/{config_id}", response_model=DepositConfigOut)
async def admin_update_deposit_config(
    config_id: UUID,
    data: DepositConfigCreate,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing deposit configuration (admin only)."""
    result = await db.execute(
        select(DepositConfig).where(DepositConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Deposit config not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(config, k, v)
    await db.flush()
    await db.commit()
    await db.refresh(config)
    return config
