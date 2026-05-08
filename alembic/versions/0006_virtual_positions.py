"""virtual_positions / virtual_fills / virtual_pnl_snapshots -- v0.14 Phase C

Revision ID: 0006_virtual_positions
Revises: 0005_virtual_trading_core
Create Date: 2026-05-08

Adds the in-process paper trading PnL & fill engine tables (35th, 36th, 37th):

  * ``virtual_positions`` (35th) -- per-(account, symbol) holding state.
    ``UNIQUE(account_id, symbol)``. ``avg_cost`` and ``realized_pnl`` are
    Numeric(18, 4) defaulting to 0; ``quantity`` is Integer defaulting to 0.
  * ``virtual_fills`` (36th) -- one row per actual fill. FK to
    ``virtual_orders`` (CASCADE) and ``virtual_accounts`` (CASCADE). Stores
    ``fee``, ``stamp_tax``, ``slippage`` separately plus the aggregated
    ``gross_amount`` and ``net_amount``. Indexes: order_id, account_id,
    symbol, filled_at, and a composite (account_id, symbol).
  * ``virtual_pnl_snapshots`` (37th) -- daily account-level PnL summary.
    ``UNIQUE(account_id, snapshot_date)`` so a re-run replaces the row.

Forbidden columns (regression-tested): ``broker_order_id``,
``kis_order_id``, ``real_account``, ``api_key``, ``token``, ``secret``.

Rollout: backup DB, then ``alembic upgrade head``.
Rollback: ``alembic downgrade 0005_virtual_trading_core`` drops all three
tables (snapshots → fills → positions order to satisfy FKs).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_virtual_positions'
down_revision: Union[str, Sequence[str], None] = '0005_virtual_trading_core'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'virtual_positions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('avg_cost', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('realized_pnl', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['account_id'], ['virtual_accounts.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'account_id',
            'symbol',
            name='uq_virtual_positions_account_symbol',
        ),
    )
    with op.batch_alter_table('virtual_positions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_virtual_positions_account_id'),
            ['account_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_positions_symbol'),
            ['symbol'],
            unique=False,
        )

    op.create_table(
        'virtual_fills',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('fill_price', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('fee', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('stamp_tax', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('slippage', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('gross_amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('net_amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['order_id'], ['virtual_orders.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['account_id'], ['virtual_accounts.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('virtual_fills', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_virtual_fills_order_id'),
            ['order_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_fills_account_id'),
            ['account_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_fills_symbol'),
            ['symbol'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_fills_filled_at'),
            ['filled_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_virtual_fills_account_symbol',
            ['account_id', 'symbol'],
            unique=False,
        )

    op.create_table(
        'virtual_pnl_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('cash_balance', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('market_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('total_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('realized_pnl', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('unrealized_pnl', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['account_id'], ['virtual_accounts.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'account_id',
            'snapshot_date',
            name='uq_virtual_pnl_snapshots_account_date',
        ),
    )
    with op.batch_alter_table('virtual_pnl_snapshots', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_virtual_pnl_snapshots_account_id'),
            ['account_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_virtual_pnl_snapshots_snapshot_date'),
            ['snapshot_date'],
            unique=False,
        )
        batch_op.create_index(
            'ix_virtual_pnl_snapshots_account_date',
            ['account_id', 'snapshot_date'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('virtual_pnl_snapshots', schema=None) as batch_op:
        batch_op.drop_index('ix_virtual_pnl_snapshots_account_date')
        batch_op.drop_index(batch_op.f('ix_virtual_pnl_snapshots_snapshot_date'))
        batch_op.drop_index(batch_op.f('ix_virtual_pnl_snapshots_account_id'))
    op.drop_table('virtual_pnl_snapshots')

    with op.batch_alter_table('virtual_fills', schema=None) as batch_op:
        batch_op.drop_index('ix_virtual_fills_account_symbol')
        batch_op.drop_index(batch_op.f('ix_virtual_fills_filled_at'))
        batch_op.drop_index(batch_op.f('ix_virtual_fills_symbol'))
        batch_op.drop_index(batch_op.f('ix_virtual_fills_account_id'))
        batch_op.drop_index(batch_op.f('ix_virtual_fills_order_id'))
    op.drop_table('virtual_fills')

    with op.batch_alter_table('virtual_positions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_virtual_positions_symbol'))
        batch_op.drop_index(batch_op.f('ix_virtual_positions_account_id'))
    op.drop_table('virtual_positions')
