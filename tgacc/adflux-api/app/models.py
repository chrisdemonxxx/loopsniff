import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Text, Boolean, BigInteger, Integer, Numeric, Date,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    password_hash = Column(Text)
    role = Column(Text, default="admin")
    tg_user_id = Column(BigInteger)
    permissions = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    company = Column(Text)
    tg_username = Column(Text)
    tg_user_id = Column(BigInteger)
    email = Column(Text)
    plan = Column(Text, default="starter")
    status = Column(Text, default="active")
    niche = Column(Text)
    monthly_spend_est = Column(Numeric)
    onboarded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("ClientUser", back_populates="client")
    accounts = relationship("AdAccount", back_populates="client")
    subscriptions = relationship("Subscription", back_populates="client")
    transactions = relationship("Transaction", back_populates="client")


class ClientUser(Base):
    __tablename__ = "client_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    email = Column(Text, nullable=False, unique=True)
    name = Column(Text)
    password_hash = Column(Text)
    role = Column(Text, default="viewer")
    tg_user_id = Column(BigInteger)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    client = relationship("Client", back_populates="users")


class AdAccount(Base):
    __tablename__ = "ad_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    platform = Column(Text, nullable=False)
    account_id = Column(Text)
    name = Column(Text)
    status = Column(Text, default="active")
    balance = Column(Numeric, default=0)
    total_spend = Column(Numeric, default=0)
    daily_limit = Column(Numeric)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    banned_at = Column(DateTime(timezone=True))
    ban_reason = Column(Text)
    replaced_by = Column(UUID(as_uuid=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="accounts")
    spending_records = relationship("SpendingRecord", back_populates="account")


class SpendingRecord(Base):
    __tablename__ = "spending_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id"))
    date = Column(Date, nullable=False)
    spend = Column(Numeric, nullable=False)
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    conversions = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    account = relationship("AdAccount", back_populates="spending_records")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    type = Column(Text)
    ad_amount = Column(Numeric)
    commission = Column(Numeric)
    crypto_amount = Column(Numeric)
    crypto_currency = Column(Text)
    nowpay_id = Column(Text)
    status = Column(Text, default="pending")
    account_id = Column(UUID(as_uuid=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    confirmed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="transactions")


class RevenueLedger(Base):
    __tablename__ = "revenue_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    type = Column(Text)
    amount = Column(Numeric, nullable=False)
    currency = Column(Text, default="USD")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    plan = Column(Text, nullable=False)
    price = Column(Numeric)
    interval_type = Column(Text, default="monthly")
    status = Column(Text, default="active")
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    next_bill = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    notes = Column(Text)

    client = relationship("Client", back_populates="subscriptions")

    @property
    def interval(self):
        return self.interval_type

    @property
    def next_billing_at(self):
        return self.next_bill


class BanTransfer(Base):
    __tablename__ = "ban_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    banned_account = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id"))
    new_account = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id"))
    amount = Column(Numeric)
    status = Column(Text, default="pending")
    requested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    channel = Column(Text)
    status = Column(Text, default="ai")
    assigned_admin = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    closed_at = Column(DateTime(timezone=True))

    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"))
    sender = Column(Text)
    text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class OutreachLead(Base):
    __tablename__ = "outreach_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tg_username = Column(Text)
    tg_user_id = Column(BigInteger)
    source = Column(Text)
    bant_score = Column(Integer, default=0)
    stage = Column(Text, default="new")
    assigned_account = Column(Text)
    last_message_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"))
    action = Column(Text, nullable=False)
    entity_type = Column(Text)
    entity_id = Column(UUID(as_uuid=True))
    details = Column(JSON, default={})
    ip_address = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class NotificationPref(Base):
    __tablename__ = "notification_prefs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_type = Column(Text)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    channel = Column(Text)
    enabled = Column(Boolean, default=True)
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# ── Ticket System ──

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"))
    subject = Column(Text, nullable=False)
    category = Column(Text, default="general")  # billing, technical, account, general
    priority = Column(Text, default="medium")  # low, medium, high, urgent
    status = Column(Text, default="open")  # open, in_progress, awaiting_client, resolved, closed
    assigned_admin = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    created_by_type = Column(Text, default="client")  # client, ai, admin
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True))

    client = relationship("Client", backref="tickets")
    messages = relationship("TicketMessage", back_populates="ticket", order_by="TicketMessage.created_at")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    sender_type = Column(Text, nullable=False)  # client, admin, ai
    sender_id = Column(UUID(as_uuid=True), nullable=True)
    text = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)  # admin-only internal notes
    attachments = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="messages")


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    message_id = Column(UUID(as_uuid=True), ForeignKey("ticket_messages.id"), nullable=True)
    filename = Column(Text, nullable=False)
    file_url = Column(Text, nullable=False)
    file_type = Column(Text)
    file_size = Column(Integer)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# ── Campaign & Sequence Engine ──

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(Text, default="draft")  # draft, active, paused, completed, archived
    target_niche = Column(Text)
    platform = Column(Text, default="telegram")
    sequence_id = Column(UUID(as_uuid=True), ForeignKey("sequences.id"), nullable=True)
    daily_send_cap = Column(Integer, default=20)
    send_window_start = Column(Integer, default=9)  # hour UTC
    send_window_end = Column(Integer, default=21)
    total_enrolled = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)
    total_converted = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    sequence = relationship("Sequence", backref="campaigns")
    leads = relationship("CampaignLead", back_populates="campaign")


class Sequence(Base):
    __tablename__ = "sequences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    steps = relationship("SequenceStep", back_populates="sequence", order_by="SequenceStep.step_order")


class SequenceStep(Base):
    __tablename__ = "sequence_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_id = Column(UUID(as_uuid=True), ForeignKey("sequences.id"), nullable=False)
    step_order = Column(Integer, nullable=False)
    delay_hours = Column(Integer, default=0)
    template_a = Column(Text, nullable=False)
    template_b = Column(Text, nullable=True)  # for A/B testing
    step_type = Column(Text, default="message")  # message, wait, condition
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    sequence = relationship("Sequence", back_populates="steps")


class CampaignLead(Base):
    __tablename__ = "campaign_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    tg_username = Column(Text)
    tg_user_id = Column(BigInteger)
    status = Column(Text, default="enrolled")  # enrolled, in_sequence, replied, converted, unsubscribed, failed
    current_step = Column(Integer, default=0)
    ab_variant = Column(Text)  # A or B
    next_touch_at = Column(DateTime(timezone=True))
    assigned_account = Column(Text)
    enrolled_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_sent_at = Column(DateTime(timezone=True))
    replied_at = Column(DateTime(timezone=True))
    converted_at = Column(DateTime(timezone=True))

    campaign = relationship("Campaign", back_populates="leads")


class ABTest(Base):
    __tablename__ = "ab_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    step_id = Column(UUID(as_uuid=True), ForeignKey("sequence_steps.id"), nullable=False)
    variant_a_sent = Column(Integer, default=0)
    variant_a_replied = Column(Integer, default=0)
    variant_b_sent = Column(Integer, default=0)
    variant_b_replied = Column(Integer, default=0)
    winner = Column(Text)  # A, B, or null (not yet determined)
    significance = Column(Numeric)  # p-value
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))


# ── Persistent Lead Memory ──

class LeadMemory(Base):
    __tablename__ = "lead_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tg_username = Column(Text, unique=True, index=True)
    tg_user_id = Column(BigInteger, nullable=True, index=True)
    platform_interest = Column(Text)
    niche = Column(Text)
    budget_range = Column(Text)
    timeline = Column(Text)
    pain_points = Column(JSON, default=[])
    objections = Column(JSON, default=[])
    key_facts = Column(JSON, default={})
    session_summaries = Column(JSON, default=[])
    bant_score = Column(Integer, default=0)
    last_interaction = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Order Tracking ──

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    order_type = Column(Text, nullable=False)  # ad_account, topup, subscription
    status = Column(Text, default="pending")  # pending, payment_received, processing, delivered, cancelled
    amount = Column(Numeric, nullable=False)
    currency = Column(Text, default="USD")
    account_id = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id"), nullable=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    details = Column(JSON, default={})
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    delivered_at = Column(DateTime(timezone=True))

    client = relationship("Client", backref="orders")


# ── Wallet System ──

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    currency = Column(Text, default="USD")
    balance = Column(Numeric, default=0)
    frozen_balance = Column(Numeric, default=0)  # held for pending operations
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", backref="wallets")
    transactions = relationship("WalletTransaction", back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    type = Column(Text, nullable=False)  # deposit, withdrawal, ad_spend, refund, commission, transfer
    amount = Column(Numeric, nullable=False)
    fee = Column(Numeric, default=0)
    net_amount = Column(Numeric, nullable=False)
    currency = Column(Text, default="USD")
    payment_method = Column(Text)  # crypto, bank_transfer, credit_card, payoneer, swift
    payment_reference = Column(Text)  # external payment ID
    status = Column(Text, default="pending")  # pending, processing, completed, failed, cancelled
    notes = Column(Text)
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))

    wallet = relationship("Wallet", back_populates="transactions")


class DepositConfig(Base):
    __tablename__ = "deposit_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_method = Column(Text, nullable=False)  # crypto, bank_transfer, credit_card, payoneer, swift
    currency = Column(Text, default="USD")
    fee_percent = Column(Numeric, default=0)
    fee_fixed = Column(Numeric, default=0)
    min_amount = Column(Numeric, default=0)
    max_amount = Column(Numeric)
    is_active = Column(Boolean, default=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)  # null = global default
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Balance Adjustments ──

class BalanceAdjustment(Base):
    __tablename__ = "balance_adjustments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    type = Column(Text, nullable=False)  # credit, debit
    amount = Column(Numeric, nullable=False)
    reason = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    client = relationship("Client", backref="adjustments")


# ── Affiliate System ──

class AffiliateCode(Base):
    __tablename__ = "affiliate_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    code = Column(Text, nullable=False, unique=True)
    commission_percent = Column(Numeric, default=40)
    is_active = Column(Boolean, default=True)
    total_referrals = Column(Integer, default=0)
    total_earnings = Column(Numeric, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    client = relationship("Client", backref="affiliate_codes")
    referrals = relationship("AffiliateReferral", back_populates="affiliate_code")


class AffiliateReferral(Base):
    __tablename__ = "affiliate_referrals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_code_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_codes.id"), nullable=False)
    referred_client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    status = Column(Text, default="active")  # active, churned
    total_commission = Column(Numeric, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    affiliate_code = relationship("AffiliateCode", back_populates="referrals")
    referred_client = relationship("Client", foreign_keys=[referred_client_id])


class AffiliateCommission(Base):
    __tablename__ = "affiliate_commissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_code_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_codes.id"), nullable=False)
    referral_id = Column(UUID(as_uuid=True), ForeignKey("affiliate_referrals.id"), nullable=False)
    amount = Column(Numeric, nullable=False)
    source_transaction_id = Column(UUID(as_uuid=True))
    status = Column(Text, default="pending")  # pending, approved, paid
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    paid_at = Column(DateTime(timezone=True))


# ── Subscription Plans ──

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)  # Single Platform, All Platforms, Enterprise
    slug = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    price_monthly = Column(Numeric, nullable=False)
    price_semiannual = Column(Numeric)
    price_annual = Column(Numeric)
    platforms = Column(JSON, default=[])  # list of platform slugs included
    max_accounts = Column(Integer)  # null = unlimited
    cashback_percent = Column(Numeric, default=0)
    features = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# ── CRM Leads ──

class CRMLead(Base):
    __tablename__ = "crm_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    email = Column(Text)
    phone = Column(Text)
    company = Column(Text)
    position = Column(Text)
    source = Column(Text)  # website, telegram, referral, cold_outreach, linkedin, etc.
    status = Column(Text, default="new")  # new, contacted, qualified, proposal, negotiation, won, lost
    priority = Column(Text, default="medium")  # low, medium, high, urgent

    # BANT scoring
    budget = Column(Text)
    authority = Column(Text)
    need = Column(Text)
    timeline = Column(Text)
    bant_score = Column(Integer, default=0)

    # Contact methods
    telegram_username = Column(Text)
    whatsapp = Column(Text)
    wechat = Column(Text)
    linkedin = Column(Text)
    instagram = Column(Text)
    discord = Column(Text)

    # Business details
    monthly_budget = Column(Numeric)
    company_size = Column(Text)
    industry = Column(Text)
    interested_platforms = Column(JSON, default=[])

    # Assignment
    assigned_bdm_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    converted_client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)

    notes = Column(Text)
    tags = Column(JSON, default=[])
    custom_fields = Column(JSON, default={})

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = Column(DateTime(timezone=True))

    assigned_bdm = relationship("AdminUser", foreign_keys=[assigned_bdm_id])
    converted_client = relationship("Client", foreign_keys=[converted_client_id])


# ── Team Management ──

class TeamTarget(Base):
    __tablename__ = "team_targets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    period = Column(Text, nullable=False)  # "2024-01", "2024-Q1", etc.
    target_type = Column(Text, nullable=False)  # leads, revenue, conversions, accounts
    target_value = Column(Numeric, nullable=False)
    achieved_value = Column(Numeric, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    admin = relationship("AdminUser", foreign_keys=[admin_id])


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(Text, default="info")  # info, warning, error, success
    scope = Column(Text, default="global")  # global, company, user
    target_client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    show_banner = Column(Boolean, default=False)
    send_email = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    starts_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)


# ── Meta Ads Integration ──

class MetaAdAccount(Base):
    __tablename__ = "meta_ad_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ad_account_id = Column(UUID(as_uuid=True), ForeignKey("ad_accounts.id"), nullable=False)
    meta_account_id = Column(Text, nullable=False)  # act_XXXXX
    access_token = Column(Text)  # encrypted
    token_expires_at = Column(DateTime(timezone=True))
    business_manager_id = Column(Text)
    facebook_page_id = Column(Text)
    instagram_account_id = Column(Text)
    timezone = Column(Text, default="UTC")
    currency = Column(Text, default="USD")
    status = Column(Text, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    ad_account = relationship("AdAccount", backref="meta_config")


class MetaCampaign(Base):
    __tablename__ = "meta_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meta_ad_account_id = Column(UUID(as_uuid=True), ForeignKey("meta_ad_accounts.id"), nullable=False)
    meta_campaign_id = Column(Text)  # from Meta API
    name = Column(Text, nullable=False)
    objective = Column(Text, nullable=False)  # TRAFFIC, LEADS, SALES, AWARENESS, ENGAGEMENT, APP_PROMOTION
    status = Column(Text, default="PAUSED")
    special_ad_categories = Column(JSON, default=[])
    buying_type = Column(Text, default="AUCTION")
    budget_optimization = Column(Text)  # CAMPAIGN_BUDGET, AD_SET_BUDGET
    daily_budget = Column(Numeric)
    lifetime_budget = Column(Numeric)
    bid_strategy = Column(Text)  # LOWEST_COST, BID_CAP, COST_CAP
    bid_amount = Column(Numeric)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))

    # Metrics (cached from API)
    spend = Column(Numeric, default=0)
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    conversions = Column(Integer, default=0)
    ctr = Column(Numeric, default=0)
    cpc = Column(Numeric, default=0)
    cpm = Column(Numeric, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    meta_ad_account = relationship("MetaAdAccount", backref="campaigns")
    ad_sets = relationship("MetaAdSet", back_populates="campaign")


class MetaAdSet(Base):
    __tablename__ = "meta_ad_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("meta_campaigns.id"), nullable=False)
    meta_adset_id = Column(Text)
    name = Column(Text, nullable=False)
    status = Column(Text, default="PAUSED")
    daily_budget = Column(Numeric)
    lifetime_budget = Column(Numeric)
    bid_strategy = Column(Text)
    bid_amount = Column(Numeric)
    optimization_goal = Column(Text)
    billing_event = Column(Text, default="IMPRESSIONS")
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))

    # Targeting
    targeting = Column(JSON, default={})  # geo, age, gender, interests, etc.
    placements = Column(JSON, default={})

    # Metrics
    spend = Column(Numeric, default=0)
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    conversions = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("MetaCampaign", back_populates="ad_sets")
    ads = relationship("MetaAd", back_populates="ad_set")


class MetaAd(Base):
    __tablename__ = "meta_ads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ad_set_id = Column(UUID(as_uuid=True), ForeignKey("meta_ad_sets.id"), nullable=False)
    meta_ad_id = Column(Text)
    name = Column(Text, nullable=False)
    status = Column(Text, default="PAUSED")
    creative = Column(JSON, default={})  # headline, body, image_url, video_url, cta, link
    format = Column(Text)  # SINGLE_IMAGE, SINGLE_VIDEO, CAROUSEL, EXISTING_POST
    facebook_page_id = Column(Text)
    instagram_account_id = Column(Text)
    url_parameters = Column(Text)
    tracking_specs = Column(JSON, default={})

    # Metrics
    spend = Column(Numeric, default=0)
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    conversions = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    ad_set = relationship("MetaAdSet", back_populates="ads")


# ── Facebook/Instagram OAuth Integration ──

class FacebookIntegration(Base):
    __tablename__ = "facebook_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    facebook_user_id = Column(Text, nullable=False)
    facebook_user_name = Column(Text)
    access_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True))
    scopes = Column(JSON, default=[])

    connected_pages = Column(JSON, default=[])        # [{id, name, access_token}]
    connected_ig_accounts = Column(JSON, default=[])   # [{id, username, name}]
    connected_ad_accounts = Column(JSON, default=[])   # [{id, account_id, name, currency, timezone}]

    status = Column(Text, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", backref="facebook_integration")


# ── Stripe & Bank Transfer ──

class BankTransferRequest(Base):
    __tablename__ = "bank_transfer_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(Text, default="USD")
    reference_code = Column(Text, nullable=False)
    bank_name = Column(Text)
    account_number = Column(Text)
    swift_bic = Column(Text)
    status = Column(Text, default="pending")  # pending, confirmed, rejected
    admin_note = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    confirmed_at = Column(DateTime(timezone=True))

    client = relationship("Client")
