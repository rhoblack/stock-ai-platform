"""Repository for v0.7 Phase B BacktestRun rows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import BacktestRun


STATUS_DRY_RUN = "DRY_RUN"
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"


class BacktestRunRepository(BaseRepository[BacktestRun]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, BacktestRun)

    def create(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
        run_date: date,
        start_date: date | None = None,
        end_date: date | None = None,
        status: str = STATUS_DRY_RUN,
        config_json: dict[str, Any] | None = None,
    ) -> BacktestRun:
        return self.add(
            BacktestRun(
                strategy_name=strategy_name,
                strategy_version=strategy_version,
                run_date=run_date,
                start_date=start_date,
                end_date=end_date,
                status=status,
                config_json=config_json,
                signal_count=0,
                buy_count=0,
                avoid_count=0,
                pass_count=0,
            ),
        )

    def get_by_id(self, run_id: int) -> BacktestRun | None:
        return self.session.get(BacktestRun, run_id)

    def list_recent(self, *, limit: int = 50) -> list[BacktestRun]:
        statement = (
            select(BacktestRun)
            .order_by(desc(BacktestRun.run_date), desc(BacktestRun.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_strategy(
        self,
        strategy_name: str,
        *,
        limit: int = 50,
    ) -> list[BacktestRun]:
        statement = (
            select(BacktestRun)
            .where(BacktestRun.strategy_name == strategy_name)
            .order_by(desc(BacktestRun.run_date), desc(BacktestRun.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def mark_finished(
        self,
        run: BacktestRun,
        *,
        signal_count: int,
        buy_count: int,
        avoid_count: int,
        pass_count: int,
        win_rate_1d: Decimal | None,
        win_rate_3d: Decimal | None,
        win_rate_5d: Decimal | None,
        win_rate_20d: Decimal | None,
        avg_return_1d: Decimal | None,
        avg_return_3d: Decimal | None,
        avg_return_5d: Decimal | None,
        avg_return_20d: Decimal | None,
        max_drawdown: Decimal | None,
        summary_json: dict[str, Any] | None,
    ) -> BacktestRun:
        run.signal_count = signal_count
        run.buy_count = buy_count
        run.avoid_count = avoid_count
        run.pass_count = pass_count
        run.win_rate_1d = win_rate_1d
        run.win_rate_3d = win_rate_3d
        run.win_rate_5d = win_rate_5d
        run.win_rate_20d = win_rate_20d
        run.avg_return_1d = avg_return_1d
        run.avg_return_3d = avg_return_3d
        run.avg_return_5d = avg_return_5d
        run.avg_return_20d = avg_return_20d
        run.max_drawdown = max_drawdown
        run.summary_json = summary_json
        run.status = STATUS_SUCCESS
        run.error_message = None
        run.updated_at = utc_now()
        self.session.flush()
        return run

    def mark_failed(self, run: BacktestRun, *, error_message: str) -> BacktestRun:
        run.status = STATUS_FAILED
        run.error_message = error_message
        run.updated_at = utc_now()
        self.session.flush()
        return run
