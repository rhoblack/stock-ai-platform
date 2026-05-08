"""real_orders -- v0.16 Phase C (40th table)

Revision ID: 0009_real_orders
Revises: 0008_approval_audit_logs
Create Date: 2026-05-08

Adds the RealOrder execution record table:

  * ``real_orders`` (40th table) -- one row per order attempt that exits the
    Approval Workflow. Phase C is the ORM-only skeleton; no actual KIS HTTP
    calls exist yet. Phase D (RealOrderExecutor) will update rows from
    CREATED → SUBMITTED → FILLED / FAILED.

Status machine stored in the ``status`` column:
  DRY_RUN (terminal) / CREATED / SUBMITTED / PARTIALLY_FILLED /
  FILLED / CANCELED / REJECTED / FAILED.

Safety policies baked into the schema:
  * ``dry_run`` defaults to TRUE -- every row is safe-by-default.
  * ``broker_order_no_hash`` stores only a SHA-256 hex (64 chars), never the
    plaintext KIS order number.
  * ``error_message`` is capped at 500 chars via application-side validation.

Forbidden columns (regression-tested in tests/integration/):
  api_key / app_secret / access_token / token / secret /
  raw_response / kis_response_raw / account_number / real_account /
  kis_order_id / broker_order_id.

Rollback: ``alembic downgrade 0008_approval_audit_logs`` drops the table.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_real_orders'
down_revision: Union[str, Sequence[str], None] = '0008_approval_audit_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'real_orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('limit_price', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column(
            'estimated_amount',
            sa.Numeric(precision=18, scale=4),
            nullable=False,
        ),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('dry_run', sa.Boolean(), nullable=False),
        sa.Column('fake_order_no', sa.String(length=32), nullable=True),
        sa.Column('broker_order_no_hash', sa.String(length=64), nullable=True),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('error_code', sa.String(length=32), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['candidate_id'], ['order_candidates.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('real_orders', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_real_orders_candidate_id'),
            ['candidate_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_real_orders_symbol'),
            ['symbol'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_real_orders_status'),
            ['status'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_real_orders_submitted_at'),
            ['submitted_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_real_orders_candidate_status',
            ['candidate_id', 'status'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('real_orders', schema=None) as batch_op:
        batch_op.drop_index('ix_real_orders_candidate_status')
        batch_op.drop_index(batch_op.f('ix_real_orders_submitted_at'))
        batch_op.drop_index(batch_op.f('ix_real_orders_status'))
        batch_op.drop_index(batch_op.f('ix_real_orders_symbol'))
        batch_op.drop_index(batch_op.f('ix_real_orders_candidate_id'))
    op.drop_table('real_orders')
