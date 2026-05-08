"""virtual_trading_core -- v0.14 Phase B (33rd + 34th tables)

Revision ID: 0005_virtual_trading_core
Revises: 0004_user_preferences
Create Date: 2026-05-08

Adds the in-process paper / simulation trading foundation:

  * ``virtual_accounts`` (33rd table) -- one row per simulated account.
    ``user_id`` is a nullable FK to ``users.id`` so single-user deployments
    work without authentication; ``Unique(user_id, name)`` prevents the same
    user from creating duplicate account names while still allowing multiple
    accounts per user.
  * ``virtual_orders`` (34th table) -- per-account simulated orders. Status
    machine: CREATED -> (PARTIALLY_FILLED | FILLED | CANCELED | REJECTED).
    Phase B writes CREATED / CANCELED / REJECTED only; fill states are owned
    by Phase C's ``execute_pending_orders()``.
    ``Unique(account_id, idempotency_key)`` provides per-account dedup.

Forbidden columns (regression-tested): ``broker_order_id``, ``kis_order_id``,
``real_account``, ``api_key``, ``token``, ``secret``.

Rollout: backup DB, then ``alembic upgrade head``.
Rollback: ``alembic downgrade 0004_user_preferences`` drops both tables.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_virtual_trading_core'
down_revision: Union[str, Sequence[str], None] = '0004_user_preferences'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'virtual_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('initial_cash', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('cash_balance', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('paper_trading_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_virtual_accounts_user_name'),
    )
    with op.batch_alter_table('virtual_accounts', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_virtual_accounts_user_id'),
            ['user_id'],
            unique=False,
        )

    op.create_table(
        'virtual_orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('limit_price', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('reason', sa.String(length=256), nullable=True),
        sa.Column('note', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['account_id'], ['virtual_accounts.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'account_id',
            'idempotency_key',
            name='uq_virtual_orders_account_idempotency',
        ),
    )
    with op.batch_alter_table('virtual_orders', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_virtual_orders_account_id'),
            ['account_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_orders_symbol'),
            ['symbol'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_orders_status'),
            ['status'],
            unique=False,
        )
        batch_op.create_index(
            'ix_virtual_orders_account_status',
            ['account_id', 'status'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('virtual_orders', schema=None) as batch_op:
        batch_op.drop_index('ix_virtual_orders_account_status')
        batch_op.drop_index(batch_op.f('ix_virtual_orders_status'))
        batch_op.drop_index(batch_op.f('ix_virtual_orders_symbol'))
        batch_op.drop_index(batch_op.f('ix_virtual_orders_account_id'))

    op.drop_table('virtual_orders')

    with op.batch_alter_table('virtual_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_virtual_accounts_user_id'))

    op.drop_table('virtual_accounts')
