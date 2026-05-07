"""Read-only Validation Report API — v0.13 Phase C.

Endpoints (GET only; POST/PUT/PATCH/DELETE → 405 by FastAPI default):
    GET /api/validation/report              — overall summary
    GET /api/validation/report/by-strategy  — per-strategy breakdown
    GET /api/validation/report/by-regime    — per-regime breakdown
    GET /api/validation/report/by-sector    — per-sector breakdown

Policies:
- Queries backtest_runs and backtest_results only (no new tables, Alembic 0건).
- score_delta is read from backtest_results.evidence_json via whitelist;
  raw evidence_json is never returned.
- Malformed score_delta entries are silently skipped.
- No external network calls; no broker / order / account fields.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ScoreDeltaSummarySchema,
    ValidationRegimeResponse,
    ValidationRegimeSummarySchema,
    ValidationReportSchema,
    ValidationSectorResponse,
    ValidationSectorSummarySchema,
    ValidationStrategyResponse,
    ValidationStrategySummarySchema,
)
from app.db.models import BacktestResult, BacktestRun, Stock
from app.db.session import get_session

router = APIRouter(prefix="/api/validation", tags=["validation"])

_QUANT = Decimal("0.0001")
_VALID_DATA_SOURCES = frozenset({"PROVIDER", "CSV", "MANUAL", "FAKE"})


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        return None


def _avg_str(values: list[Decimal]) -> str | None:
    if not values:
        return None
    result = (sum(values) / len(values)).quantize(_QUANT, rounding=ROUND_HALF_UP)
    return str(result)


def _win_rate_str(wins: int, total_with_return: int) -> str | None:
    if total_with_return == 0:
        return None
    rate = (Decimal(wins) / Decimal(total_with_return)).quantize(
        _QUANT, rounding=ROUND_HALF_UP
    )
    return str(rate)


def _extract_score_delta(evidence: Any) -> dict | None:
    if not isinstance(evidence, dict):
        return None
    sd = evidence.get("score_delta")
    return sd if isinstance(sd, dict) else None


def _aggregate_score_delta(results: list) -> ScoreDeltaSummarySchema:
    total_scored = 0
    policy_enabled_count = 0
    deltas: list[Decimal] = []
    positive = negative = neutral = 0
    ds_counts: dict[str, int] = defaultdict(int)

    for row in results:
        sd = _extract_score_delta(row.evidence_json)
        if sd is None:
            continue
        total_scored += 1
        if sd.get("policy_enabled"):
            policy_enabled_count += 1
        delta_val = _safe_decimal(sd.get("delta"))
        if delta_val is not None:
            deltas.append(delta_val)
            if delta_val > 0:
                positive += 1
            elif delta_val < 0:
                negative += 1
            else:
                neutral += 1
        for comp in sd.get("components", []):
            if not isinstance(comp, dict):
                continue
            ds = comp.get("data_source")
            bucket = ds if ds in _VALID_DATA_SOURCES else "UNKNOWN"
            ds_counts[bucket] += 1

    return ScoreDeltaSummarySchema(
        total_scored=total_scored,
        policy_enabled_count=policy_enabled_count,
        avg_delta=_avg_str(deltas),
        positive_delta_count=positive,
        negative_delta_count=negative,
        neutral_delta_count=neutral,
        data_source_counts=dict(ds_counts),
    )


@router.get("/report", response_model=ValidationReportSchema)
def get_validation_report(db: Session = Depends(get_session)) -> ValidationReportSchema:
    runs = db.execute(select(BacktestRun)).scalars().all()
    results = db.execute(select(BacktestResult)).scalars().all()

    wr_vals = [r.win_rate_5d for r in runs if r.win_rate_5d is not None]
    ar_vals = [r.avg_return_5d for r in runs if r.avg_return_5d is not None]

    return ValidationReportSchema(
        generated_at=datetime.now(timezone.utc),
        run_count=len(runs),
        signal_count=sum(r.signal_count for r in runs),
        buy_count=sum(r.buy_count for r in runs),
        win_rate_5d=_avg_str(wr_vals),
        avg_return_5d=_avg_str(ar_vals),
        score_delta=_aggregate_score_delta(results),
    )


@router.get("/report/by-strategy", response_model=ValidationStrategyResponse)
def get_validation_by_strategy(
    db: Session = Depends(get_session),
) -> ValidationStrategyResponse:
    runs = db.execute(select(BacktestRun)).scalars().all()
    run_id_to_strategy = {r.id: r.strategy_name for r in runs}

    groups: dict[str, dict] = defaultdict(lambda: {
        "run_count": 0,
        "signal_count": 0,
        "buy_count": 0,
        "win_rates": [],
        "avg_returns": [],
        "max_drawdowns": [],
    })
    for run in runs:
        g = groups[run.strategy_name]
        g["run_count"] += 1
        g["signal_count"] += run.signal_count
        g["buy_count"] += run.buy_count
        if run.win_rate_5d is not None:
            g["win_rates"].append(run.win_rate_5d)
        if run.avg_return_5d is not None:
            g["avg_returns"].append(run.avg_return_5d)
        if run.max_drawdown is not None:
            g["max_drawdowns"].append(run.max_drawdown)

    cost_adj: dict[str, list[Decimal]] = defaultdict(list)
    buy_results = db.execute(
        select(BacktestResult).where(BacktestResult.signal_action == "BUY")
    ).scalars().all()
    for res in buy_results:
        if res.cost_adjusted_return_5d is None:
            continue
        sname = run_id_to_strategy.get(res.backtest_run_id)
        if sname:
            cost_adj[sname].append(res.cost_adjusted_return_5d)

    items = [
        ValidationStrategySummarySchema(
            strategy_name=sname,
            run_count=g["run_count"],
            signal_count=g["signal_count"],
            buy_count=g["buy_count"],
            win_rate_5d=_avg_str(g["win_rates"]),
            avg_return_5d=_avg_str(g["avg_returns"]),
            cost_adjusted_avg_return_5d=_avg_str(cost_adj.get(sname, [])),
            max_drawdown=_avg_str(g["max_drawdowns"]),
        )
        for sname, g in sorted(groups.items())
    ]
    return ValidationStrategyResponse(count=len(items), items=items)


@router.get("/report/by-regime", response_model=ValidationRegimeResponse)
def get_validation_by_regime(
    db: Session = Depends(get_session),
) -> ValidationRegimeResponse:
    buy_results = db.execute(
        select(BacktestResult).where(BacktestResult.signal_action == "BUY")
    ).scalars().all()

    groups: dict[str, dict] = defaultdict(lambda: {
        "buy_count": 0,
        "returns": [],
        "wins": 0,
    })
    for res in buy_results:
        regime = res.regime or "UNCLASSIFIED"
        g = groups[regime]
        g["buy_count"] += 1
        if res.return_5d is not None:
            g["returns"].append(res.return_5d)
            if res.return_5d > 0:
                g["wins"] += 1

    items = [
        ValidationRegimeSummarySchema(
            regime=regime,
            buy_count=g["buy_count"],
            win_rate_5d=_win_rate_str(g["wins"], len(g["returns"])),
            avg_return_5d=_avg_str(g["returns"]),
        )
        for regime, g in sorted(groups.items())
    ]
    return ValidationRegimeResponse(count=len(items), items=items)


@router.get("/report/by-sector", response_model=ValidationSectorResponse)
def get_validation_by_sector(
    db: Session = Depends(get_session),
) -> ValidationSectorResponse:
    rows = db.execute(
        select(BacktestResult, Stock.sector)
        .outerjoin(Stock, BacktestResult.symbol == Stock.symbol)
        .where(BacktestResult.signal_action == "BUY")
    ).all()

    groups: dict[str, dict] = defaultdict(lambda: {
        "buy_count": 0,
        "returns": [],
        "wins": 0,
    })
    for res, sector in rows:
        key = sector or "UNKNOWN"
        g = groups[key]
        g["buy_count"] += 1
        if res.return_5d is not None:
            g["returns"].append(res.return_5d)
            if res.return_5d > 0:
                g["wins"] += 1

    items = [
        ValidationSectorSummarySchema(
            sector=sector,
            buy_count=g["buy_count"],
            win_rate_5d=_win_rate_str(g["wins"], len(g["returns"])),
            avg_return_5d=_avg_str(g["returns"]),
        )
        for sector, g in sorted(groups.items())
    ]
    return ValidationSectorResponse(count=len(items), items=items)
