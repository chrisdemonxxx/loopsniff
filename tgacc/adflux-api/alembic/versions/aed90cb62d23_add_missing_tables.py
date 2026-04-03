"""add missing tables

Revision ID: aed90cb62d23
Revises: 0698c026383a
Create Date: 2026-04-03 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'aed90cb62d23'
down_revision: Union[str, None] = '0698c026383a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Base tables (no foreign keys) ──

    op.create_table('admin_users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('permissions', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table('clients',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('company', sa.Text(), nullable=True),
        sa.Column('tg_username', sa.Text(), nullable=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('plan', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('niche', sa.Text(), nullable=True),
        sa.Column('monthly_spend_est', sa.Numeric(), nullable=True),
        sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('outreach_leads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tg_username', sa.Text(), nullable=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('bant_score', sa.Integer(), nullable=True),
        sa.Column('stage', sa.Text(), nullable=True),
        sa.Column('assigned_account', sa.Text(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('notification_prefs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_type', sa.Text(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('channel', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('sequences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('lead_memory',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tg_username', sa.Text(), nullable=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('platform_interest', sa.Text(), nullable=True),
        sa.Column('niche', sa.Text(), nullable=True),
        sa.Column('budget_range', sa.Text(), nullable=True),
        sa.Column('timeline', sa.Text(), nullable=True),
        sa.Column('pain_points', sa.JSON(), nullable=True),
        sa.Column('objections', sa.JSON(), nullable=True),
        sa.Column('key_facts', sa.JSON(), nullable=True),
        sa.Column('session_summaries', sa.JSON(), nullable=True),
        sa.Column('bant_score', sa.Integer(), nullable=True),
        sa.Column('last_interaction', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tg_username'),
    )
    op.create_index('ix_lead_memory_tg_username', 'lead_memory', ['tg_username'], unique=True)
    op.create_index('ix_lead_memory_tg_user_id', 'lead_memory', ['tg_user_id'], unique=False)

    # ── Tables depending on clients only ──

    op.create_table('client_users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('password_hash', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table('ad_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('platform', sa.Text(), nullable=False),
        sa.Column('account_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('balance', sa.Numeric(), nullable=True),
        sa.Column('total_spend', sa.Numeric(), nullable=True),
        sa.Column('daily_limit', sa.Numeric(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('banned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ban_reason', sa.Text(), nullable=True),
        sa.Column('replaced_by', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('ad_amount', sa.Numeric(), nullable=True),
        sa.Column('commission', sa.Numeric(), nullable=True),
        sa.Column('crypto_amount', sa.Numeric(), nullable=True),
        sa.Column('crypto_currency', sa.Text(), nullable=True),
        sa.Column('nowpay_id', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('account_id', sa.UUID(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('plan', sa.Text(), nullable=False),
        sa.Column('price', sa.Numeric(), nullable=True),
        sa.Column('interval_type', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_bill', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('channel', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('assigned_admin', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('facebook_integrations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('facebook_user_id', sa.Text(), nullable=False),
        sa.Column('facebook_user_name', sa.Text(), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('connected_pages', sa.JSON(), nullable=True),
        sa.Column('connected_ig_accounts', sa.JSON(), nullable=True),
        sa.Column('connected_ad_accounts', sa.JSON(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('bank_transfer_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('reference_code', sa.Text(), nullable=False),
        sa.Column('bank_name', sa.Text(), nullable=True),
        sa.Column('account_number', sa.Text(), nullable=True),
        sa.Column('swift_bic', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('provisioning_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('platform', sa.Text(), nullable=False),
        sa.Column('business_name', sa.Text(), nullable=False),
        sa.Column('business_url', sa.Text(), nullable=True),
        sa.Column('business_type', sa.Text(), nullable=True),
        sa.Column('spend_limit', sa.Numeric(), nullable=True),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('timezone', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('reject_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on admin_users ──

    op.create_table('audit_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=True),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on clients + admin_users ──

    op.create_table('tickets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('priority', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('assigned_admin', sa.UUID(), nullable=True),
        sa.Column('created_by_type', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['assigned_admin'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('balance_adjustments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['created_by'], ['admin_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on sequences ──

    op.create_table('sequence_steps',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sequence_id', sa.UUID(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('delay_hours', sa.Integer(), nullable=True),
        sa.Column('template_a', sa.Text(), nullable=False),
        sa.Column('template_b', sa.Text(), nullable=True),
        sa.Column('step_type', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['sequence_id'], ['sequences.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('campaigns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('target_niche', sa.Text(), nullable=True),
        sa.Column('platform', sa.Text(), nullable=True),
        sa.Column('sequence_id', sa.UUID(), nullable=True),
        sa.Column('daily_send_cap', sa.Integer(), nullable=True),
        sa.Column('send_window_start', sa.Integer(), nullable=True),
        sa.Column('send_window_end', sa.Integer(), nullable=True),
        sa.Column('total_enrolled', sa.Integer(), nullable=True),
        sa.Column('total_sent', sa.Integer(), nullable=True),
        sa.Column('total_replied', sa.Integer(), nullable=True),
        sa.Column('total_converted', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['sequence_id'], ['sequences.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on ad_accounts ──

    op.create_table('spending_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('spend', sa.Numeric(), nullable=False),
        sa.Column('impressions', sa.BigInteger(), nullable=True),
        sa.Column('clicks', sa.BigInteger(), nullable=True),
        sa.Column('conversions', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['ad_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('ban_transfers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('banned_account', sa.UUID(), nullable=True),
        sa.Column('new_account', sa.UUID(), nullable=True),
        sa.Column('amount', sa.Numeric(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['banned_account'], ['ad_accounts.id']),
        sa.ForeignKeyConstraint(['new_account'], ['ad_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on transactions ──

    op.create_table('revenue_ledger',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=True),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on chat_sessions ──

    op.create_table('chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=True),
        sa.Column('sender', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on tickets ──

    op.create_table('ticket_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('sender_type', sa.Text(), nullable=False),
        sa.Column('sender_id', sa.UUID(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_internal', sa.Boolean(), nullable=True),
        sa.Column('attachments', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on clients + ad_accounts + transactions ──

    op.create_table('orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('order_type', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('account_id', sa.UUID(), nullable=True),
        sa.Column('transaction_id', sa.UUID(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['account_id'], ['ad_accounts.id']),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on campaigns ──

    op.create_table('campaign_leads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('campaign_id', sa.UUID(), nullable=False),
        sa.Column('tg_username', sa.Text(), nullable=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('current_step', sa.Integer(), nullable=True),
        sa.Column('ab_variant', sa.Text(), nullable=True),
        sa.Column('next_touch_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigned_account', sa.Text(), nullable=True),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on tickets + ticket_messages ──

    op.create_table('ticket_attachments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=True),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('file_url', sa.Text(), nullable=False),
        sa.Column('file_type', sa.Text(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.ForeignKeyConstraint(['message_id'], ['ticket_messages.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── Tables depending on campaigns + sequence_steps ──

    op.create_table('ab_tests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('campaign_id', sa.UUID(), nullable=False),
        sa.Column('step_id', sa.UUID(), nullable=False),
        sa.Column('variant_a_sent', sa.Integer(), nullable=True),
        sa.Column('variant_a_replied', sa.Integer(), nullable=True),
        sa.Column('variant_b_sent', sa.Integer(), nullable=True),
        sa.Column('variant_b_replied', sa.Integer(), nullable=True),
        sa.Column('winner', sa.Text(), nullable=True),
        sa.Column('significance', sa.Numeric(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.ForeignKeyConstraint(['step_id'], ['sequence_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('ab_tests')
    op.drop_table('ticket_attachments')
    op.drop_table('campaign_leads')
    op.drop_table('orders')
    op.drop_table('ticket_messages')
    op.drop_table('chat_messages')
    op.drop_table('revenue_ledger')
    op.drop_table('ban_transfers')
    op.drop_table('spending_records')
    op.drop_table('campaigns')
    op.drop_table('sequence_steps')
    op.drop_table('balance_adjustments')
    op.drop_table('tickets')
    op.drop_table('audit_log')
    op.drop_table('provisioning_requests')
    op.drop_table('bank_transfer_requests')
    op.drop_table('facebook_integrations')
    op.drop_table('chat_sessions')
    op.drop_table('subscriptions')
    op.drop_table('transactions')
    op.drop_table('ad_accounts')
    op.drop_table('client_users')
    op.drop_index('ix_lead_memory_tg_user_id', table_name='lead_memory')
    op.drop_index('ix_lead_memory_tg_username', table_name='lead_memory')
    op.drop_table('lead_memory')
    op.drop_table('sequences')
    op.drop_table('notification_prefs')
    op.drop_table('outreach_leads')
    op.drop_table('clients')
    op.drop_table('admin_users')
