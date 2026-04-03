from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class WalletOut(BaseModel):
    id: UUID
    client_id: UUID
    currency: str
    balance: Decimal
    frozen_balance: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class WalletTransactionOut(BaseModel):
    id: UUID
    wallet_id: UUID
    type: str
    amount: Decimal
    fee: Decimal
    net_amount: Decimal
    currency: str
    payment_method: Optional[str]
    payment_reference: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DepositRequest(BaseModel):
    amount: Decimal
    currency: str = "USD"
    payment_method: str  # crypto, bank_transfer, credit_card, payoneer, swift


class WithdrawalRequest(BaseModel):
    amount: Decimal
    currency: str = "USD"
    payment_method: str
    destination: str  # wallet address, bank details, etc.


class TransferRequest(BaseModel):
    amount: Decimal
    target_account_id: UUID  # ad account to fund


class DepositConfigOut(BaseModel):
    id: UUID
    payment_method: str
    currency: str
    fee_percent: Decimal
    fee_fixed: Decimal
    min_amount: Decimal
    max_amount: Optional[Decimal]
    is_active: bool

    class Config:
        from_attributes = True


class DepositConfigCreate(BaseModel):
    payment_method: str
    currency: str = "USD"
    fee_percent: Decimal = Decimal("0")
    fee_fixed: Decimal = Decimal("0")
    min_amount: Decimal = Decimal("0")
    max_amount: Optional[Decimal] = None
    is_active: bool = True
    client_id: Optional[UUID] = None
