"""Repository for v0.14 Phase B VirtualAccount rows.

VirtualAccount is the per-user (or single-user) container for the in-process
paper trading core. The repository never opens HTTP connections, never
imports any KIS / broker module, and never touches secrets. Callers commit
or flush themselves -- consistent with the rest of the project's repository
pattern.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import VirtualAccount


DEFAULT_INITIAL_CASH = Decimal("10000000")  # 10,000,000 KRW
DEFAULT_CURRENCY = "KRW"


class VirtualAccountRepository(BaseRepository[VirtualAccount]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VirtualAccount)

    # -------- create --------

    def create(
        self,
        *,
        name: str,
        initial_cash: Decimal | int | float | str = DEFAULT_INITIAL_CASH,
        user_id: int | None = None,
        currency: str = DEFAULT_CURRENCY,
        paper_trading_enabled: bool = True,
    ) -> VirtualAccount:
        """Insert a new VirtualAccount with ``cash_balance == initial_cash``."""
        if not name or not name.strip():
            raise ValueError("VirtualAccount.name must not be empty")
        amount = Decimal(str(initial_cash))
        if amount < 0:
            raise ValueError("initial_cash must be >= 0")
        return self.add(
            VirtualAccount(
                user_id=user_id,
                name=name,
                initial_cash=amount,
                cash_balance=amount,
                currency=currency,
                paper_trading_enabled=paper_trading_enabled,
            )
        )

    # -------- read --------

    def get_by_id(self, account_id: int) -> VirtualAccount | None:
        return self.session.get(VirtualAccount, account_id)

    def list_by_user(self, user_id: int | None) -> list[VirtualAccount]:
        statement = (
            select(VirtualAccount)
            .where(VirtualAccount.user_id == user_id)
            .order_by(VirtualAccount.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def get_default(self, user_id: int | None = None) -> VirtualAccount | None:
        """Return the lowest-id active account for the given user (or NULL user).

        "Default" semantics here are intentionally simple in Phase B -- there
        is no per-user is_default flag yet. The frontend / API in later phases
        may pick a different convention.
        """
        statement = (
            select(VirtualAccount)
            .where(VirtualAccount.user_id == user_id)
            .order_by(VirtualAccount.id.asc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    # -------- write --------

    def update_cash_balance(
        self,
        account: VirtualAccount,
        *,
        new_balance: Decimal | int | float | str,
    ) -> VirtualAccount:
        amount = Decimal(str(new_balance))
        if amount < 0:
            raise ValueError("cash_balance must be >= 0")
        account.cash_balance = amount
        account.updated_at = utc_now()
        self.session.flush()
        return account

    def set_paper_trading_enabled(
        self, account: VirtualAccount, *, enabled: bool
    ) -> VirtualAccount:
        account.paper_trading_enabled = enabled
        account.updated_at = utc_now()
        self.session.flush()
        return account
