"""real_fills -- v0.16 Phase C (41st table)

Revision ID: 0010_real_fills
Revises: 0009_real_orders
Create Date: 2026-05-08

Adds the RealFill per-fill record table:

  * ``real_fills`` (41st table) -- one row per confirmed fill event for a
    RealOrder. Phase C is the ORM-only skeleton; no fill rows will be written
    until Phase D's RealOrderExecutor confirms fills from KIS.

Each fill row records:
  * quantity / fill_price / fee / tax / gross_amount / net_amount -- the cost
    breakdown so reports can reproduce the cash-flow math without hitting KIS.
  * fill_status: FULL (entire order filled in one go) or PARTIAL (more fills
    may follow).
  * filled_at: wall-clock time of the fill event.

Forbidden columns (regression-tested):
  api_key / app_secret / access_token / token / secret /
  raw_response / kis_response_raw / account_number / real_account.

Rollback: ``alembic downgrade 0009_real_orders`` drops this table.
Then ``alembic downgrade 0008_approval_audit_logs`` drops real_orders.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_real_fills'
down_revision: Union[str, Sequence[str], None] = '0009_real_orders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'real_fills',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('real_order_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('fill_price', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('fee', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('tax', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('gross_amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('net_amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('fill_status', sa.String(length=16), nullable=False),
        sa.Column('filled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['real_order_id'], ['real_orders.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('real_fills', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_real_fills_real_order_id'),
            ['real_order_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_real_fills_symbol'),
            ['symbol'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_real_fills_filled_at'),
            ['filled_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_real_fills_order_filled_at',
            ['real_order_id', 'filled_at'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('real_fills', schema=None) as batch_op:
        batch_op.drop_index('ix_real_fills_order_filled_at')
        batch_op.drop_index(batch_op.f('ix_real_fills_filled_at'))
        batch_op.drop_index(batch_op.f('ix_real_fills_symbol'))
        batch_op.drop_index(batch_op.f('ix_real_fills_real_order_id'))
    op.drop_table('real_fills')
