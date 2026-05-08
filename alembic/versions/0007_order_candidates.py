"""order_candidates -- v0.15 Phase B (38th table)

Revision ID: 0007_order_candidates
Revises: 0006_virtual_positions
Create Date: 2026-05-08

Adds the Approval Trading Safety Layer staging table:

  * ``order_candidates`` (38th table) -- staged orders awaiting risk check
    + user approval. Only paper execution is allowed downstream;
    ``virtual_order_id`` is the sole FK to ``virtual_orders.id`` and there
    is NO real-broker / KIS column.
  * 8-state status machine: DRAFT / RISK_CHECKING / RISK_REJECTED /
    PENDING_APPROVAL / APPROVED / EXECUTED_PAPER / REJECTED / EXPIRED.
    Allowed transitions are enforced by OrderCandidateRepository (Phase B).

Forbidden columns (regression-tested):
``broker_order_id`` / ``kis_order_id`` / ``real_account`` / ``real_order_id`` /
``api_key`` / ``token`` / ``secret``.

Rollout: backup DB, then ``alembic upgrade head``.
Rollback: ``alembic downgrade 0006_virtual_positions`` drops the table.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_order_candidates'
down_revision: Union[str, Sequence[str], None] = '0006_virtual_positions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'order_candidates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('source_ref_id', sa.Integer(), nullable=True),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('limit_price', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column(
            'estimated_amount', sa.Numeric(precision=18, scale=4), nullable=False
        ),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('risk_check_result_json', sa.JSON(), nullable=True),
        sa.Column('approver_user_id', sa.Integer(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=256), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('virtual_order_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['account_id'], ['virtual_accounts.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['approver_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['virtual_order_id'], ['virtual_orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('order_candidates', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_order_candidates_account_id'),
            ['account_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_order_candidates_symbol'),
            ['symbol'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_order_candidates_status'),
            ['status'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_order_candidates_expires_at'),
            ['expires_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_order_candidates_account_status',
            ['account_id', 'status'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('order_candidates', schema=None) as batch_op:
        batch_op.drop_index('ix_order_candidates_account_status')
        batch_op.drop_index(batch_op.f('ix_order_candidates_expires_at'))
        batch_op.drop_index(batch_op.f('ix_order_candidates_status'))
        batch_op.drop_index(batch_op.f('ix_order_candidates_symbol'))
        batch_op.drop_index(batch_op.f('ix_order_candidates_account_id'))

    op.drop_table('order_candidates')
