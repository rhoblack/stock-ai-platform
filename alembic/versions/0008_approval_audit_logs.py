"""approval_audit_logs -- v0.15 Phase D (39th table)

Revision ID: 0008_approval_audit_logs
Revises: 0007_order_candidates
Create Date: 2026-05-08

Adds the Approval Workflow append-only audit trail:

  * ``approval_audit_logs`` (39th table) -- one row per state transition /
    kill-switch block. NO update / delete API exists; the repository only
    exposes ``append`` / ``list_*``. Raw IP / user-agent values are NEVER
    persisted -- only SHA256 hashes via ``app.auth.security.hash_for_audit``.
  * 8 event types: CREATED / RISK_CHECKED / RISK_REJECTED / APPROVED /
    REJECTED / EXPIRED / EXECUTED_PAPER / KILL_SWITCH_BLOCKED.

Forbidden columns (regression-tested): ``broker_order_id`` /
``kis_order_id`` / ``real_account`` / ``real_order_id`` / ``api_key`` /
``token`` / ``secret``.

Rollout: backup DB, then ``alembic upgrade head``.
Rollback: ``alembic downgrade 0007_order_candidates`` drops the table.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_approval_audit_logs'
down_revision: Union[str, Sequence[str], None] = '0007_order_candidates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'approval_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(length=256), nullable=True),
        sa.Column('details_json', sa.JSON(), nullable=True),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('user_agent_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['candidate_id'], ['order_candidates.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('approval_audit_logs', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_approval_audit_logs_candidate_id'),
            ['candidate_id'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_approval_audit_logs_event_type'),
            ['event_type'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_approval_audit_logs_created_at'),
            ['created_at'],
            unique=False,
        )
        batch_op.create_index(
            'ix_approval_audit_logs_candidate_event',
            ['candidate_id', 'event_type'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('approval_audit_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_approval_audit_logs_candidate_event')
        batch_op.drop_index(batch_op.f('ix_approval_audit_logs_created_at'))
        batch_op.drop_index(batch_op.f('ix_approval_audit_logs_event_type'))
        batch_op.drop_index(batch_op.f('ix_approval_audit_logs_candidate_id'))
    op.drop_table('approval_audit_logs')
