"""Repository for v0.7 Phase B BacktestResult rows."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import asc, func, select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import BacktestResult


class BacktestResultRepository(BaseRepository[BacktestResult]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, BacktestResult)

    def create(
        self,
        *,
        backtest_run_id: int,
        symbol: str,
        signal_action: str,
        recommendation_id: int | None = None,
        recommendation_result_id: int | None = None,
        confidence: Decimal | None = None,
        reason: str | None = None,
        grade: str | None = None,
        total_score: Decimal | None = None,
        return_1d: Decimal | None = None,
        return_3d: Decimal | None = None,
        return_5d: Decimal | None = None,
        return_20d: Decimal | None = None,
        max_drawdown: Decimal | None = None,
        result_status: str | None = None,
        evidence_json: dict[str, Any] | None = None,
    ) -> BacktestResult:
        return self.add(
            BacktestResult(
                backtest_run_id=backtest_run_id,
                symbol=symbol,
                signal_action=signal_action,
                recommendation_id=recommendation_id,
                recommendation_result_id=recommendation_result_id,
                confidence=confidence,
                reason=reason,
                grade=grade,
                total_score=total_score,
                return_1d=return_1d,
                return_3d=return_3d,
                return_5d=return_5d,
                return_20d=return_20d,
                max_drawdown=max_drawdown,
                result_status=result_status,
                evidence_json=evidence_json,
            ),
        )

    def bulk_insert(
        self,
        rows: Iterable[BacktestResult],
    ) -> Sequence[BacktestResult]:
        """Add many results in one flush. Caller controls commit/rollback."""

        materialized = list(rows)
        if not materialized:
            return materialized
        self.session.add_all(materialized)
        self.session.flush()
        return materialized

    def list_by_run(self, backtest_run_id: int) -> list[BacktestResult]:
        statement = (
            select(BacktestResult)
            .where(BacktestResult.backtest_run_id == backtest_run_id)
            .order_by(asc(BacktestResult.id))
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 100,
    ) -> list[BacktestResult]:
        statement = (
            select(BacktestResult)
            .where(BacktestResult.symbol == symbol)
            .order_by(asc(BacktestResult.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def aggregate_by_run(self, backtest_run_id: int) -> dict[str, int]:
        """Return ``{signal_action: count}`` for one run."""

        statement = (
            select(BacktestResult.signal_action, func.count(BacktestResult.id))
            .where(BacktestResult.backtest_run_id == backtest_run_id)
            .group_by(BacktestResult.signal_action)
        )
        rows = self.session.execute(statement).all()
        return {action: count for action, count in rows}

    def aggregate_by_signal_action(
        self,
        signal_action: str,
        *,
        limit: int = 100,
    ) -> list[BacktestResult]:
        """Return raw rows for one action across all runs (debug/inspection)."""

        statement = (
            select(BacktestResult)
            .where(BacktestResult.signal_action == signal_action)
            .order_by(asc(BacktestResult.id))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
