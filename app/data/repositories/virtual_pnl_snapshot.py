"""Repository for v0.14 Phase C VirtualPnLSnapshot rows.

One row per (account_id, snapshot_date). ``create_or_replace_snapshot``
upserts in-place so re-running the daily snapshot job produces the same
final-state table without duplicates.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import VirtualPnLSnapshot


class VirtualPnLSnapshotRepository(BaseRepository[VirtualPnLSnapshot]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VirtualPnLSnapshot)

    # -------- read --------

    def get_by_account_date(
        self, *, account_id: int, snapshot_date: date
    ) -> VirtualPnLSnapshot | None:
        statement = select(VirtualPnLSnapshot).where(
            VirtualPnLSnapshot.account_id == account_id,
            VirtualPnLSnapshot.snapshot_date == snapshot_date,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_account(
        self,
        account_id: int,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 365,
    ) -> list[VirtualPnLSnapshot]:
        statement = select(VirtualPnLSnapshot).where(
            VirtualPnLSnapshot.account_id == account_id
        )
        if from_date is not None:
            statement = statement.where(
                VirtualPnLSnapshot.snapshot_date >= from_date
            )
        if to_date is not None:
            statement = statement.where(
                VirtualPnLSnapshot.snapshot_date <= to_date
            )
        statement = statement.order_by(
            VirtualPnLSnapshot.snapshot_date.asc()
        ).limit(limit)
        return list(self.session.execute(statement).scalars().all())

    # -------- write --------

    def create_or_replace_snapshot(
        self,
        *,
        account_id: int,
        snapshot_date: date,
        cash_balance: Decimal,
        market_value: Decimal,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
    ) -> VirtualPnLSnapshot:
        """Upsert the (account_id, snapshot_date) row with computed totals."""
        total_value = Decimal(cash_balance) + Decimal(market_value)
        existing = self.get_by_account_date(
            account_id=account_id, snapshot_date=snapshot_date
        )
        if existing is None:
            return self.add(
                VirtualPnLSnapshot(
                    account_id=account_id,
                    snapshot_date=snapshot_date,
                    cash_balance=cash_balance,
                    market_value=market_value,
                    total_value=total_value,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=unrealized_pnl,
                )
            )

        existing.cash_balance = cash_balance
        existing.market_value = market_value
        existing.total_value = total_value
        existing.realized_pnl = realized_pnl
        existing.unrealized_pnl = unrealized_pnl
        existing.updated_at = utc_now()
        self.session.flush()
        return existing
