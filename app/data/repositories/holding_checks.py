from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import HoldingCheck


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

