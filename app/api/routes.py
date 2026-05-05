"""FastAPI v0.1 dashboard router.

All endpoints are read-only GETs. Per AGENTS.md routes do NOT:
    * call KIS / external APIs
    * recompute indicators or scores
    * generate recommendations or run holding checks
    * send Telegram messages
    * place or simulate orders

Routes only translate Repository / DB rows into Pydantic response schemas.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    DailyPriceSchema,
    HoldingCheckSchema,
    HoldingCheckSymbolMetrics,
    HoldingCheckSymbolResponse,
    HoldingChecksResponse,
    HoldingSchema,
    HoldingsResponse,
    JobRunDetailSchema,
    JobRunSchema,
    JobsResponse,
    MarketCapRankingResponse,
    MarketCapRankingSchema,
    MarketRegimeSchema,
    NewsItemSchema,
    NewsResponse,
    RecommendationHistoryItem,
    RecommendationHistoryResponse,
    RecommendationItemSchema,
    RecommendationResultSchema,
    RecommendationRunDetailResponse,
    RecommendationRunSchema,
    RiskSummarySchema,
    SettingsResponse,
    StockBriefSchema,
    StockDetailResponse,
    StockIndicatorSchema,
    StockPriceSeriesResponse,
    TodayReportResponse,
)
from app.config.settings import Settings, get_settings
from app.data.collectors.kis_client import mask_sensitive_value
from app.data.repositories import (
    DailyPriceRepository,
    DataSnapshotRepository,
    HoldingCheckRepository,
    HoldingRepository,
    JobRunRepository,
    MarketCapRankingRepository,
    MarketRegimeRepository,
    NewsItemRepository,
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
    StockIndicatorRepository,
    StockRepository,
)
from app.db.models import (
    DataSnapshot,
    JobRun,
    NewsItem,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
)
from app.db.session import get_session
from app.notification.report_generator import extract_risk_summary
from app.notification.telegram_notifier import mask_chat_id


router = APIRouter()


# ---------- helpers ----------

def _risk_summary_from_snapshot(
    snapshot: Optional[DataSnapshot],
) -> Optional[RiskSummarySchema]:
    if snapshot is None:
        return None
    level, flags = extract_risk_summary(snapshot)
    penalty = (
        (snapshot.market_context_json or {})
        .get("risk_summary", {})
        .get("penalty")
    )
    return RiskSummarySchema(level=level, flags=flags, penalty=penalty)


def _recommendation_result_to_schema(
    result: RecommendationResult,
) -> RecommendationResultSchema:
    return RecommendationResultSchema(
        days_after=result.days_after,
        result_date=result.result_date,
        open_return=result.open_return,
        high_return=result.high_return,
        low_return=result.low_return,
        close_return=result.close_return,
        max_return=result.max_return,
        max_drawdown=result.max_drawdown,
        result_status=result.result_status,
    )


def _recommendation_to_schema(
    rec: Recommendation,
    snapshot: Optional[DataSnapshot],
    results: list[RecommendationResult],
    run: Optional[RecommendationRun] = None,
) -> RecommendationItemSchema:
    risk_summary = _risk_summary_from_snapshot(snapshot)
    return RecommendationItemSchema(
        recommendation_id=rec.id,
        run_id=rec.run_id,
        run_date=run.run_date if run is not None else None,
        telegram_sent=run.telegram_sent if run is not None else None,
        rank=rec.rank,
        market=rec.market,
        symbol=rec.symbol,
        name=rec.name,
        grade=rec.grade,
        total_score=rec.total_score,
        technical_score=rec.technical_score,
        news_score=rec.news_score,
        supply_score=rec.supply_score,
        fundamental_score=rec.fundamental_score,
        ai_score=rec.ai_score,
        risk_score=rec.risk_score,
        reason=rec.reason,
        risk_note=rec.risk_note,
        snapshot_id=rec.snapshot_id,
        risk_level=risk_summary.level if risk_summary is not None else None,
        risk_flags=risk_summary.flags if risk_summary is not None else [],
        risk_summary=risk_summary,
        results=[_recommendation_result_to_schema(r) for r in results],
    )


def _holding_check_to_schema(
    check,
    snapshot: Optional[DataSnapshot],
) -> HoldingCheckSchema:
    risk_summary = _risk_summary_from_snapshot(snapshot)
    return HoldingCheckSchema(
        id=check.id,
        check_date=check.check_date,
        check_type=check.check_type,
        symbol=check.symbol,
        current_price=check.current_price,
        avg_buy_price=check.avg_buy_price,
        return_rate=check.return_rate,
        technical_score=check.technical_score,
        news_score=check.news_score,
        earnings_score=check.earnings_score,
        ai_score=check.ai_score,
        risk_score=check.risk_score,
        total_score=check.total_score,
        grade=check.grade,
        decision=check.decision,
        reason=check.reason,
        alert=check.alert,
        snapshot_id=check.snapshot_id,
        risk_level=risk_summary.level if risk_summary is not None else None,
        risk_flags=risk_summary.flags if risk_summary is not None else [],
        risk_summary=risk_summary,
    )


def _resolve_recommendation_items(
    recommendations: list[Recommendation],
    snapshot_repo: DataSnapshotRepository,
    result_repo: RecommendationResultRepository,
    run: Optional[RecommendationRun] = None,
) -> list[RecommendationItemSchema]:
    items: list[RecommendationItemSchema] = []
    for rec in recommendations:
        snapshot = (
            snapshot_repo.get(rec.snapshot_id) if rec.snapshot_id is not None else None
        )
        results = result_repo.list_by_recommendation_id(rec.id)
        items.append(_recommendation_to_schema(rec, snapshot, results, run))
    return items


def _resolve_recent_recommendations_for_symbol(
    *,
    session: Session,
    symbol: str,
    snapshot_repo: DataSnapshotRepository,
    result_repo: RecommendationResultRepository,
    limit: int,
) -> list[RecommendationItemSchema]:
    statement = (
        select(Recommendation, RecommendationRun)
        .join(RecommendationRun, Recommendation.run_id == RecommendationRun.run_id)
        .where(Recommendation.symbol == symbol)
        .order_by(desc(RecommendationRun.run_date), desc(RecommendationRun.run_id), Recommendation.rank)
        .limit(limit)
    )
    rows = list(session.execute(statement).all())
    items: list[RecommendationItemSchema] = []
    for rec, run in rows:
        snapshot = (
            snapshot_repo.get(rec.snapshot_id) if rec.snapshot_id is not None else None
        )
        results = result_repo.list_by_recommendation_id(rec.id)
        items.append(_recommendation_to_schema(rec, snapshot, results, run))
    return items


_AGGREGATE_DAYS_AFTER = (1, 3, 5, 20)
_SUCCESS_RATE_DAYS_AFTER = 5
_FINALIZED_STATUSES = {"SUCCESS", "FAILED"}
_AGGREGATE_QUANT = Decimal("0.0001")


def _quantize_aggregate(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_AGGREGATE_QUANT, rounding=ROUND_HALF_UP)


def _aggregate_run_results(session: Session, run_id: int) -> dict:
    """Per-run aggregates for `RecommendationHistoryItem`.

    * ``avg_close_return_<N>d`` averages ``close_return`` over recommendations
      whose results at days_after=N have a non-null close_return.
    * ``success_rate`` is computed against days_after=5 results that are
      already finalized (``SUCCESS`` or ``FAILED``); PENDING rows are excluded
      from both the numerator and denominator. Returned as a percentage value
      in ``[0, 100]``.
    * If a metric has no eligible rows, the value is ``None``.
    """
    statement = (
        select(RecommendationResult)
        .join(
            Recommendation,
            RecommendationResult.recommendation_id == Recommendation.id,
        )
        .where(Recommendation.run_id == run_id)
    )
    rows = list(session.execute(statement).scalars().all())

    by_days: dict[int, list[RecommendationResult]] = defaultdict(list)
    for row in rows:
        by_days[row.days_after].append(row)

    aggregates: dict[str, Decimal | None] = {}
    for n in _AGGREGATE_DAYS_AFTER:
        closes = [r.close_return for r in by_days.get(n, []) if r.close_return is not None]
        if closes:
            avg = sum(closes, Decimal("0")) / Decimal(len(closes))
            aggregates[f"avg_close_return_{n}d"] = _quantize_aggregate(avg)
        else:
            aggregates[f"avg_close_return_{n}d"] = None

    finalized = [
        r
        for r in by_days.get(_SUCCESS_RATE_DAYS_AFTER, [])
        if r.result_status in _FINALIZED_STATUSES
    ]
    if finalized:
        success = sum(1 for r in finalized if r.result_status == "SUCCESS")
        rate = Decimal(success) * Decimal("100") / Decimal(len(finalized))
        aggregates["success_rate"] = _quantize_aggregate(rate)
    else:
        aggregates["success_rate"] = None

    return aggregates


def _resolve_holding_checks(
    checks: list,
    snapshot_repo: DataSnapshotRepository,
) -> list[HoldingCheckSchema]:
    items: list[HoldingCheckSchema] = []
    for check in checks:
        snapshot = (
            snapshot_repo.get(check.snapshot_id)
            if check.snapshot_id is not None
            else None
        )
        items.append(_holding_check_to_schema(check, snapshot))
    return items


_CHECK_TYPE_ORDER = {"PRE_MARKET": 0, "POST_MARKET": 1}


def _summarize_holding_check_history(
    sorted_checks: list,
    snapshot_repo: DataSnapshotRepository,
) -> HoldingCheckSymbolMetrics:
    """Aggregate metrics across the full per-symbol holding_check history.

    ``sorted_checks`` must already be in latest-first order (by ``check_date``
    desc, with same-day POST_MARKET ranked after PRE_MARKET). Empty input
    returns the schema's zero/None defaults so the dashboard can render
    without conditional checks.
    """
    if not sorted_checks:
        return HoldingCheckSymbolMetrics()

    risk_levels: list[Optional[str]] = []
    for check in sorted_checks:
        snapshot = (
            snapshot_repo.get(check.snapshot_id)
            if check.snapshot_id is not None
            else None
        )
        level, _flags = extract_risk_summary(snapshot)
        risk_levels.append(level)

    latest = sorted_checks[0]
    previous = sorted_checks[1] if len(sorted_checks) > 1 else None

    if (
        previous is not None
        and latest.total_score is not None
        and previous.total_score is not None
    ):
        total_score_change: Decimal | None = latest.total_score - previous.total_score
    else:
        total_score_change = None

    return_rates = [c.return_rate for c in sorted_checks if c.return_rate is not None]
    best_return_rate = max(return_rates) if return_rates else None
    worst_return_rate = min(return_rates) if return_rates else None

    return HoldingCheckSymbolMetrics(
        total_check_count=len(sorted_checks),
        alert_count=sum(1 for c in sorted_checks if c.alert),
        high_risk_count=sum(1 for level in risk_levels if level == "HIGH"),
        latest_check_date=latest.check_date,
        latest_total_score=latest.total_score,
        previous_total_score=(previous.total_score if previous is not None else None),
        total_score_change=total_score_change,
        latest_return_rate=latest.return_rate,
        best_return_rate=best_return_rate,
        worst_return_rate=worst_return_rate,
        latest_decision=latest.decision,
        latest_risk_level=risk_levels[0],
    )


def _summary_int(summary: dict, *keys: str) -> int | None:
    for key in keys:
        value = summary.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _summary_list(summary: dict, key: str) -> list[dict]:
    value = summary.get(key)
    return value if isinstance(value, list) else []


def _job_run_to_schema(row: JobRun) -> JobRunSchema:
    summary = row.result_summary or {}
    success_count = _summary_int(
        summary,
        "success_count",
        "daily_success_count",
        "saved_count",
        "snapshots_saved",
        "upserted_results",
    )
    failed_count = _summary_int(
        summary,
        "failed_count",
        "failure_count",
        "daily_failure_count",
    )
    skipped_count = _summary_int(
        summary,
        "skipped_count",
        "skipped_no_prices",
        "skipped_no_price",
        "skipped_no_indicator",
        "skipped_no_reference",
    )
    total_count = _summary_int(
        summary,
        "total_count",
        "members_count",
        "symbols_count",
        "processed_recommendations",
        "candidate_count",
    )
    partial_count = _summary_int(summary, "partial_count")
    if partial_count is None and row.status == "PARTIAL":
        partial_count = 1

    return JobRunSchema(
        job_id=row.job_id,
        job_name=row.job_name,
        started_at=row.started_at,
        finished_at=row.finished_at,
        status=row.status,
        error_message=row.error_message,
        result_summary=row.result_summary,
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        partial_count=partial_count,
        total_count=total_count,
        provider_type=summary.get("provider_type"),
        universe_name=summary.get("universe") or summary.get("universe_name"),
        batch_size=_summary_int(summary, "batch_size"),
    )


def _job_run_to_detail_schema(row: JobRun) -> JobRunDetailSchema:
    summary = row.result_summary or {}
    base = _job_run_to_schema(row).dict()
    return JobRunDetailSchema(
        **base,
        successes=_summary_list(summary, "successes"),
        skipped=_summary_list(summary, "skipped"),
        failures=_summary_list(summary, "failures"),
        batches=_summary_list(summary, "batches"),
    )


# ---------- /api/reports/today ----------

@router.get("/api/reports/today", response_model=TodayReportResponse, tags=["reports"])
def get_today_report(session: Session = Depends(get_session)) -> TodayReportResponse:
    today = datetime.now(timezone.utc).date()

    regime = MarketRegimeRepository(session).latest()
    latest_run = RecommendationRunRepository(session).latest()
    snapshot_repo = DataSnapshotRepository(session)
    result_repo = RecommendationResultRepository(session)

    top_recs: list[RecommendationItemSchema] = []
    if latest_run is not None:
        recs = RecommendationRepository(session).list_by_run_id(latest_run.run_id)
        top_recs = _resolve_recommendation_items(
            recs[:5],
            snapshot_repo,
            result_repo,
            latest_run,
        )

    alerts = HoldingCheckRepository(session).list_recent_alerts(limit=10)
    alert_items = _resolve_holding_checks(alerts, snapshot_repo)

    return TodayReportResponse(
        date=today,
        market_regime=(
            MarketRegimeSchema.from_orm(regime) if regime is not None else None
        ),
        latest_run=(
            RecommendationRunSchema.from_orm(latest_run) if latest_run is not None else None
        ),
        top_recommendations=top_recs,
        holding_alerts=alert_items,
    )


# ---------- /api/recommendations/* ----------

@router.get(
    "/api/recommendations/latest",
    response_model=RecommendationRunDetailResponse,
    tags=["recommendations"],
)
def get_latest_recommendation_run(
    session: Session = Depends(get_session),
) -> RecommendationRunDetailResponse:
    latest_run = RecommendationRunRepository(session).latest()
    if latest_run is None:
        raise HTTPException(status_code=404, detail="No recommendation runs found")

    snapshot_repo = DataSnapshotRepository(session)
    result_repo = RecommendationResultRepository(session)
    recs = RecommendationRepository(session).list_by_run_id(latest_run.run_id)
    return RecommendationRunDetailResponse(
        run=RecommendationRunSchema.from_orm(latest_run),
        recommendations=_resolve_recommendation_items(
            recs, snapshot_repo, result_repo, latest_run,
        ),
    )


@router.get(
    "/api/recommendations/history",
    response_model=RecommendationHistoryResponse,
    tags=["recommendations"],
)
def get_recommendation_history(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> RecommendationHistoryResponse:
    statement = select(RecommendationRun).order_by(desc(RecommendationRun.run_date))
    if start_date is not None:
        statement = statement.where(RecommendationRun.run_date >= start_date)
    if end_date is not None:
        statement = statement.where(RecommendationRun.run_date <= end_date)
    statement = statement.offset(offset).limit(limit)

    runs = list(session.execute(statement).scalars().all())
    rec_repo = RecommendationRepository(session)
    items: list[RecommendationHistoryItem] = []
    for run in runs:
        recs = rec_repo.list_by_run_id(run.run_id)
        aggregates = _aggregate_run_results(session, run.run_id)
        items.append(
            RecommendationHistoryItem(
                run=RecommendationRunSchema.from_orm(run),
                recommendation_count=len(recs),
                **aggregates,
            ),
        )
    return RecommendationHistoryResponse(items=items, limit=limit, offset=offset)


@router.get(
    "/api/recommendations/{run_id}",
    response_model=RecommendationRunDetailResponse,
    tags=["recommendations"],
)
def get_recommendation_run(
    run_id: int,
    session: Session = Depends(get_session),
) -> RecommendationRunDetailResponse:
    run = RecommendationRunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run_id {run_id} not found")
    snapshot_repo = DataSnapshotRepository(session)
    result_repo = RecommendationResultRepository(session)
    recs = RecommendationRepository(session).list_by_run_id(run.run_id)
    return RecommendationRunDetailResponse(
        run=RecommendationRunSchema.from_orm(run),
        recommendations=_resolve_recommendation_items(
            recs, snapshot_repo, result_repo, run,
        ),
    )


# ---------- /api/holdings* ----------

@router.get("/api/holdings", response_model=HoldingsResponse, tags=["holdings"])
def get_holdings(session: Session = Depends(get_session)) -> HoldingsResponse:
    holdings = list(HoldingRepository(session).list_active())
    return HoldingsResponse(
        items=[HoldingSchema.from_orm(h) for h in holdings],
    )


@router.get(
    "/api/holdings/checks/latest",
    response_model=HoldingChecksResponse,
    tags=["holdings"],
)
def get_latest_holding_checks(
    check_type: Optional[str] = Query(None, regex="^(PRE_MARKET|POST_MARKET)$"),
    session: Session = Depends(get_session),
) -> HoldingChecksResponse:
    checks = HoldingCheckRepository(session).list_latest_per_symbol(
        check_type=check_type,
    )
    snapshot_repo = DataSnapshotRepository(session)
    return HoldingChecksResponse(items=_resolve_holding_checks(checks, snapshot_repo))


@router.get(
    "/api/holdings/{symbol}/checks",
    response_model=HoldingCheckSymbolResponse,
    tags=["holdings"],
)
def get_holding_checks_for_symbol(
    symbol: str,
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> HoldingCheckSymbolResponse:
    checks = HoldingCheckRepository(session).list_by_symbol(symbol)
    sorted_checks = sorted(
        checks,
        key=lambda c: (c.check_date, _CHECK_TYPE_ORDER.get(c.check_type, 0)),
        reverse=True,
    )
    snapshot_repo = DataSnapshotRepository(session)
    summary = _summarize_holding_check_history(sorted_checks, snapshot_repo)
    items = _resolve_holding_checks(sorted_checks[:limit], snapshot_repo)
    return HoldingCheckSymbolResponse(items=items, summary=summary)


# ---------- /api/stocks/{symbol} ----------

@router.get(
    "/api/stocks/{symbol}",
    response_model=StockDetailResponse,
    tags=["stocks"],
)
def get_stock_detail(
    symbol: str,
    recommendation_limit: int = Query(10, ge=0, le=100),
    holding_check_limit: int = Query(20, ge=0, le=200),
    session: Session = Depends(get_session),
) -> StockDetailResponse:
    stock = StockRepository(session).get_by_symbol(symbol)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"symbol {symbol} not found")
    latest_price = DailyPriceRepository(session).get_latest_by_symbol(symbol)
    latest_indicator = StockIndicatorRepository(session).get_latest_by_symbol(symbol)
    snapshot_repo = DataSnapshotRepository(session)
    result_repo = RecommendationResultRepository(session)
    recent_recommendations = _resolve_recent_recommendations_for_symbol(
        session=session,
        symbol=symbol,
        snapshot_repo=snapshot_repo,
        result_repo=result_repo,
        limit=recommendation_limit,
    )
    recent_holding_checks = _resolve_holding_checks(
        HoldingCheckRepository(session).list_by_symbol(symbol)[:holding_check_limit],
        snapshot_repo,
    )
    return StockDetailResponse(
        stock=StockBriefSchema.from_orm(stock),
        latest_price=(
            DailyPriceSchema.from_orm(latest_price)
            if latest_price is not None
            else None
        ),
        latest_indicator=(
            StockIndicatorSchema.from_orm(latest_indicator)
            if latest_indicator is not None
            else None
        ),
        recent_recommendations=recent_recommendations,
        recent_holding_checks=recent_holding_checks,
    )


@router.get(
    "/api/stocks/{symbol}/prices",
    response_model=StockPriceSeriesResponse,
    tags=["stocks"],
)
def get_stock_price_series(
    symbol: str,
    days: int = Query(120, ge=1, le=500),
    session: Session = Depends(get_session),
) -> StockPriceSeriesResponse:
    stock = StockRepository(session).get_by_symbol(symbol)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"symbol {symbol} not found")
    rows = DailyPriceRepository(session).list_by_symbol(symbol, limit=days)
    return StockPriceSeriesResponse(
        symbol=symbol,
        days=days,
        count=len(rows),
        prices=[DailyPriceSchema.from_orm(row) for row in rows],
    )


# ---------- /api/universe/market-cap-top ----------

@router.get(
    "/api/universe/market-cap-top",
    response_model=MarketCapRankingResponse,
    tags=["universe"],
)
def get_market_cap_top(
    market: str = Query("KOSPI"),
    rank_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> MarketCapRankingResponse:
    repo = MarketCapRankingRepository(session)
    target_date = rank_date or repo.latest_rank_date(market=market)
    if target_date is None:
        return MarketCapRankingResponse(rank_date=None, market=market, items=[])
    rows = repo.list_by_date_market(target_date, market)[:limit]
    return MarketCapRankingResponse(
        rank_date=target_date,
        market=market,
        items=[MarketCapRankingSchema.from_orm(row) for row in rows],
    )


# ---------- /api/market-regime/latest ----------

@router.get(
    "/api/market-regime/latest",
    response_model=Optional[MarketRegimeSchema],
    tags=["market"],
)
def get_latest_market_regime(
    market: Optional[str] = Query(None),
    session: Session = Depends(get_session),
) -> Optional[MarketRegimeSchema]:
    regime = MarketRegimeRepository(session).latest(market=market)
    if regime is None:
        return None
    return MarketRegimeSchema.from_orm(regime)


# ---------- /api/news ----------

@router.get("/api/news", response_model=NewsResponse, tags=["news"])
def get_news(
    symbol: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> NewsResponse:
    statement = select(NewsItem).order_by(desc(NewsItem.published_at))
    if start_time is not None:
        statement = statement.where(NewsItem.published_at >= start_time)
    if end_time is not None:
        statement = statement.where(NewsItem.published_at <= end_time)
    if theme is not None:
        statement = statement.where(NewsItem.theme == theme)
    if sentiment is not None:
        statement = statement.where(NewsItem.sentiment == sentiment)
    statement = statement.offset(offset).limit(limit)

    rows = list(session.execute(statement).scalars().all())
    if symbol is not None:
        rows = [
            row
            for row in rows
            if row.related_symbols and symbol in row.related_symbols
        ]

    return NewsResponse(
        items=[NewsItemSchema.from_orm(row) for row in rows],
        limit=limit,
        offset=offset,
    )


# ---------- /api/jobs ----------

@router.get("/api/jobs", response_model=JobsResponse, tags=["jobs"])
def get_jobs(
    job_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> JobsResponse:
    statement = select(JobRun).order_by(desc(JobRun.started_at))
    if job_name is not None:
        statement = statement.where(JobRun.job_name == job_name)
    if status is not None:
        statement = statement.where(JobRun.status == status)
    if start_date is not None:
        statement = statement.where(JobRun.started_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        statement = statement.where(JobRun.started_at <= datetime.combine(end_date, datetime.max.time()))
    statement = statement.offset(offset).limit(limit)

    rows = list(session.execute(statement).scalars().all())
    return JobsResponse(
        items=[_job_run_to_schema(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/api/jobs/{job_id}", response_model=JobRunDetailSchema, tags=["jobs"])
def get_job(
    job_id: int,
    session: Session = Depends(get_session),
) -> JobRunDetailSchema:
    row = JobRunRepository(session).get(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job run not found")
    return _job_run_to_detail_schema(row)


# ---------- /api/settings ----------

@router.get("/api/settings", response_model=SettingsResponse, tags=["settings"])
def get_settings_endpoint(
    settings: Settings = Depends(get_settings),
) -> SettingsResponse:
    return SettingsResponse(
        app_env=settings.app_env,
        app_name=settings.app_name,
        timezone=settings.timezone,
        log_level=settings.log_level,
        telegram_enabled=settings.telegram_enabled,
        telegram_bot_token=mask_sensitive_value(settings.telegram_bot_token),
        telegram_chat_id=mask_chat_id(settings.telegram_chat_id),
        kis_app_key=mask_sensitive_value(settings.kis_app_key),
        kis_app_secret=mask_sensitive_value(settings.kis_app_secret),
        kis_account_no=mask_sensitive_value(settings.kis_account_no),
        kis_use_paper=settings.kis_use_paper,
        scheduler_enabled=settings.scheduler_enabled,
        feature_real_order_execution=settings.feature_real_order_execution,
        feature_full_auto=settings.feature_full_auto,
        feature_paper_trading=settings.feature_paper_trading,
        feature_backtest=settings.feature_backtest,
        feature_custom_ai_training=settings.feature_custom_ai_training,
    )
