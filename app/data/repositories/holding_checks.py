from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import HoldingCheck


_TYPE_ORDER = {"PRE_MARKET": 0, "POST_MARKET": 1}


class HoldingCheckRepository(BaseRepository[HoldingCheck]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, HoldingCheck)

    def list_by_symbol(self, symbol: str) -> list[HoldingCheck]:
        statement = (
            select(HoldingCheck)
            .where(HoldingCheck.symbol == symbol)
            .order_by(HoldingCheck.check_date.desc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_recent_alerts(self, limit: int = 10) -> list[HoldingCheck]:
        statement = (
            select(HoldingCheck)
            .where(HoldingCheck.alert.is_(True))
            .order_by(HoldingCheck.check_date.desc(), HoldingCheck.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_latest_per_symbol(
        self,
        check_type: str | None = None,
    ) -> list[HoldingCheck]:
        """Return the most recent HoldingCheck per symbol.

        When ``check_type`` is provided, restrict to that type (PRE_MARKET /
        POST_MARKET); otherwise consider all checks. Same-day PRE_MARKET is
        treated as earlier than same-day POST_MARKET.
        """
        statement = select(HoldingCheck)
        if check_type is not None:
            statement = statement.where(HoldingCheck.check_type == check_type)
        rows = list(self.session.execute(statement).scalars().all())
        order = {"PRE_MARKET": 0, "POST_MARKET": 1}
        rows.sort(
            key=lambda r: (r.check_date, order.get(r.check_type, 99)),
        )
        latest_by_symbol: dict[str, HoldingCheck] = {}
        for row in rows:
            latest_by_symbol[row.symbol] = row
        return sorted(latest_by_symbol.values(), key=lambda r: r.symbol)

    def get_by_date_type_symbol(
        self,
        check_date: date,
        check_type: str,
        symbol: str,
    ) -> HoldingCheck | None:
        statement = select(HoldingCheck).where(
            HoldingCheck.check_date == check_date,
            HoldingCheck.check_type == check_type,
            HoldingCheck.symbol == symbol,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_date_type(
        self,
        *,
        check_date: date,
        check_type: str,
    ) -> list[HoldingCheck]:
        statement = (
            select(HoldingCheck)
            .where(
                HoldingCheck.check_date == check_date,
                HoldingCheck.check_type == check_type,
            )
            .order_by(HoldingCheck.symbol)
        )
        return list(self.session.execute(statement).scalars().all())

    def find_previous_for_symbol(
        self,
        symbol: str,
        *,
        before_date: date,
        before_type: str,
    ) -> HoldingCheck | None:
        """Most recent holding_check for ``symbol`` strictly before ``(before_date, before_type)``.

        Same-day PRE_MARKET is treated as earlier than same-day POST_MARKET.
        Older check_dates always rank earlier.
        """
        target_rank = (before_date, _TYPE_ORDER.get(before_type, 99))
        statement = select(HoldingCheck).where(HoldingCheck.symbol == symbol)
        rows = list(self.session.execute(statement).scalars().all())
        earlier = [
            row
            for row in rows
            if (row.check_date, _TYPE_ORDER.get(row.check_type, 99)) < target_rank
        ]
        if not earlier:
            return None
        earlier.sort(key=lambda r: (r.check_date, _TYPE_ORDER.get(r.check_type, 99)))
        return earlier[-1]

    def upsert(
        self,
        *,
        check_date: date,
        check_type: str,
        symbol: str,
        current_price: Decimal | None = None,
        avg_buy_price: Decimal | None = None,
        return_rate: Decimal | None = None,
        technical_score: Decimal | None = None,
        news_score: Decimal | None = None,
        earnings_score: Decimal | None = None,
        ai_score: Decimal | None = None,
        risk_score: Decimal | None = None,
        total_score: Decimal | None = None,
        grade: str | None = None,
        decision: str | None = None,
        reason: str | None = None,
        alert: bool = False,
        snapshot_id: int | None = None,
    ) -> HoldingCheck:
        existing = self.get_by_date_type_symbol(check_date, check_type, symbol)
        if existing is None:
            return self.add(
                HoldingCheck(
                    check_date=check_date,
                    check_type=check_type,
                    symbol=symbol,
                    current_price=current_price,
                    avg_buy_price=avg_buy_price,
                    return_rate=return_rate,
                    technical_score=technical_score,
                    news_score=news_score,
                    earnings_score=earnings_score,
                    ai_score=ai_score,
                    risk_score=risk_score,
                    total_score=total_score,
                    grade=grade,
                    decision=decision,
                    reason=reason,
                    alert=alert,
                    snapshot_id=snapshot_id,
                ),
            )

        existing.current_price = current_price
        existing.avg_buy_price = avg_buy_price
        existing.return_rate = return_rate
        existing.technical_score = technical_score
        existing.news_score = news_score
        existing.earnings_score = earnings_score
        existing.ai_score = ai_score
        existing.risk_score = risk_score
        existing.total_score = total_score
        existing.grade = grade
        existing.decision = decision
        existing.reason = reason
        existing.alert = alert
        existing.snapshot_id = snapshot_id
        self.session.flush()
        return existing
