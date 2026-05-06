"""user_preferences -- v0.9 Phase C (32nd table)

Revision ID: 0004_user_preferences
Revises: 0003_watchlist
Create Date: 2026-05-07

Adds ``user_preferences`` (32nd table):

  * One row per user (UNIQUE user_id).
  * ``default_watchlist_id`` is a nullable FK to ``watchlists.id`` with
    ON DELETE SET NULL so deleting a watchlist never orphans the preference.
  * ``dashboard_layout_json`` and ``notification_preferences_json`` store
    opaque JSON blobs. ``notification_preferences_json`` is persisted only --
    no live Telegram / Email sender is wired here.
  * No broker / account / quantity / order_price / order_type / side columns.

Rollout: backup DB, then ``alembic upgrade head``.
Rollback: ``alembic downgrade 0003_watchlist`` drops the table cleanly.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_user_preferences'
down_revision: Union[str, Sequence[str], None] = '0003_watchlist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('default_watchlist_id', sa.Integer(), nullable=True),
        sa.Column('default_market', sa.String(length=32), nullable=True),
        sa.Column('default_strategy', sa.String(length=64), nullable=True),
        sa.Column('dashboard_layout_json', sa.JSON(), nullable=True),
        sa.Column('notification_preferences_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['default_watchlist_id'], ['watchlists.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('user_preferences', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_preferences_user_id'), ['user_id'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('user_preferences', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_preferences_user_id'))

    op.drop_table('user_preferences')
