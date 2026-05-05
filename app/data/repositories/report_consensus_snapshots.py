from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import ReportConsensusSnapshot


class ReportConsensusSnapshotRepository(BaseRepository[ReportConsensusSnapshot]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReportConsensusSnapshot)

    def get_by_unique(
        self,
        *,
        symbol: str,
        snapshot_date: date,
        window_days: int,
    ) -> ReportConsensusSnapshot | None:
        statement = select(ReportConsensusSnapshot).where(
            ReportConsensusSnapshot.symbol == symbol,
            ReportConsensusSnapshot.snapshot_date == snapshot_date,
            ReportConsensusSnapshot.window_days == window_days,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_by_symbol_date_window(
        self,
        *,
        symbol: str,
        snapshot_date: date,
        window_days: int,
        report_count: int,
        avg_target_price: Decimal | None = None,
        min_target_price: Decimal | None = None,
        max_target_price: Decimal | None = None,
        strong_buy_count: int = 0,
        buy_count: int = 0,
        hold_count: int = 0,
        sell_count: int = 0,
        strong_sell_count: int = 0,
        latest_published_at: date | None = None,
    ) -> ReportConsensusSnapshot:
        existing = self.get_by_unique(
            symbol=symbol,
            snapshot_date=snapshot_date,
            window_days=window_days,
        )
        if existing is None:
            return self.add(
                ReportConsensusSnapshot(
                    symbol=symbol,
                    snapshot_date=snapshot_date,
                    window_days=window_days,
                    report_count=report_count,
                    avg_target_price=avg_target_price,
                    min_target_price=min_target_price,
                    max_target_price=max_target_price,
                    strong_buy_count=strong_buy_count,
                    buy_count=buy_count,
                    hold_count=hold_count,
                    sell_count=sell_count,
                    strong_sell_count=strong_sell_count,
                    latest_published_at=latest_published_at,
                ),
            )
        existing.report_count = report_count
        existing.avg_target_price = avg_target_price
        existing.min_target_price = min_target_price
        existing.max_target_price = max_target_price
        existing.strong_buy_count = strong_buy_count
        existing.buy_count = buy_count
        existing.hold_count = hold_count
        existing.sell_count = sell_count
        existing.strong_sell_count = strong_sell_count
        existing.latest_published_at = latest_published_at
        self.session.flush()
        return existing

    def get_latest_by_symbol(
        self,
        symbol: str,
        *,
        window_days: int | None = None,
    ) -> ReportConsensusSnapshot | None:
        statement = select(ReportConsensusSnapshot).where(
            ReportConsensusSnapshot.symbol == symbol,
        )
        if window_days is not None:
            statement = statement.where(ReportConsensusSnapshot.window_days == window_days)
        statement = statement.order_by(
            ReportConsensusSnapshot.snapshot_date.desc()
        ).limit(1)
        return self.session.execute(statement).scalar_one_or_none()

    def list_recent(self, *, limit: int = 50) -> list[ReportConsensusSnapshot]:
        statement = (
            select(ReportConsensusSnapshot)
            .order_by(ReportConsensusSnapshot.snapshot_date.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
