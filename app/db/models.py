from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utc_now


class Stock(TimestampMixin, Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theme_tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Holding(TimestampMixin, Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    avg_buy_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    buy_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    strategy_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_holdings_symbol_active", "symbol", "is_active"),
    )


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    trading_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_daily_prices_symbol_date"),
        Index("ix_daily_prices_symbol_date", "symbol", "date"),
    )


class StockIndicator(TimestampMixin, Base):
    __tablename__ = "stock_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ma5: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    ma20: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    ma60: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    ma120: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    rsi14: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    macd: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    macd_signal: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    volume_ratio_20d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    breakout_20d: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    breakout_60d: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ma_alignment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    technical_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    # v0.3 Phase B — additive nullable columns. Existing rows default to NULL.
    atr14: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    candle_patterns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    volatility_band: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_stock_indicators_symbol_date"),
        Index("ix_stock_indicators_symbol_date", "symbol", "date"),
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_job_runs_name_status", "job_name", "status"),
    )

    notification_logs: Mapped[list["NotificationLog"]] = relationship(
        back_populates="related_job",
    )


class MarketCapRanking(TimestampMixin, Base):
    __tablename__ = "market_cap_rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rank_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    listed_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trading_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    is_analysis_target: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("rank_date", "market", "rank", name="uq_market_cap_rank_date_market_rank"),
        UniqueConstraint(
            "rank_date",
            "market",
            "symbol",
            name="uq_market_cap_rank_date_market_symbol",
        ),
        Index("ix_market_cap_rankings_date_market", "rank_date", "market"),
        Index("ix_market_cap_rankings_symbol_date", "symbol", "rank_date"),
    )


class StockUniverse(TimestampMixin, Base):
    __tablename__ = "stock_universes"

    universe_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    members: Mapped[list["StockUniverseMember"]] = relationship(back_populates="universe")


class StockUniverseMember(Base):
    __tablename__ = "stock_universe_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    universe_id: Mapped[int] = mapped_column(
        ForeignKey("stock_universes.universe_id"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    universe: Mapped[StockUniverse] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("universe_id", "symbol", name="uq_stock_universe_members_universe_symbol"),
        Index("ix_stock_universe_members_symbol_universe", "symbol", "universe_id"),
    )


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    related_symbols: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    importance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # v0.5 Phase A — disclosure / news classification
    # (NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "url", name="uq_news_items_source_url"),
        Index("ix_news_items_published_source", "published_at", "source"),
    )


class MarketRegime(Base):
    __tablename__ = "market_regimes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    regime: Mapped[str] = mapped_column(String(64), nullable=False)
    market_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("date", "market", name="uq_market_regimes_date_market"),
        Index("ix_market_regimes_market_date", "market", "date"),
    )


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    price_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    indicator_data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    news_data_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    market_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="snapshot")
    holding_checks: Mapped[list["HoldingCheck"]] = relationship(back_populates="snapshot")
    decision_logs: Mapped[list["DecisionLog"]] = relationship(back_populates="input_snapshot")

    __table_args__ = (
        Index("ix_data_snapshots_symbol_type_time", "symbol", "snapshot_type", "snapshot_time"),
    )


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    telegram_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="run")

    __table_args__ = (
        Index("ix_recommendation_runs_date_status", "run_date", "status"),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation_runs.run_id"),
        nullable=False,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    technical_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    news_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    supply_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    fundamental_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    ai_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    watch_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalid_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_snapshots.snapshot_id"),
        nullable=True,
        index=True,
    )

    run: Mapped[RecommendationRun] = relationship(back_populates="recommendations")
    snapshot: Mapped[DataSnapshot | None] = relationship(back_populates="recommendations")
    results: Mapped[list["RecommendationResult"]] = relationship(back_populates="recommendation")

    __table_args__ = (
        UniqueConstraint("run_id", "rank", name="uq_recommendations_run_rank"),
        UniqueConstraint("run_id", "symbol", name="uq_recommendations_run_symbol"),
        Index("ix_recommendations_run_symbol", "run_id", "symbol"),
    )


class RecommendationResult(Base):
    __tablename__ = "recommendation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"),
        nullable=False,
        index=True,
    )
    result_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_after: Mapped[int] = mapped_column(Integer, nullable=False)
    open_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    high_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    low_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    close_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    result_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    recommendation: Mapped[Recommendation] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "days_after",
            name="uq_recommendation_results_recommendation_days",
        ),
    )


class HoldingCheck(Base):
    __tablename__ = "holding_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    avg_buy_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    return_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    technical_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    news_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    earnings_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    ai_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_snapshots.snapshot_id"),
        nullable=True,
        index=True,
    )

    snapshot: Mapped[DataSnapshot | None] = relationship(back_populates="holding_checks")

    __table_args__ = (
        UniqueConstraint("check_date", "check_type", "symbol", name="uq_holding_checks_date_type_symbol"),
        Index("ix_holding_checks_symbol_date", "symbol", "check_date"),
    )


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    input_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_snapshots.snapshot_id"),
        nullable=True,
        index=True,
    )
    rule_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_decision: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    input_snapshot: Mapped[DataSnapshot | None] = relationship(back_populates="decision_logs")

    __table_args__ = (
        Index("ix_decision_logs_type_symbol", "decision_type", "symbol"),
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_runs.job_id"),
        nullable=True,
        index=True,
    )

    related_job: Mapped[JobRun | None] = relationship(back_populates="notification_logs")

    __table_args__ = (
        Index("ix_notification_logs_channel_status", "channel", "status"),
    )


# ---------------------------------------------------------------------------
# v0.4 — Analyst & Theme Intelligence
#
# Six tables that store: raw analyst reports (company / sector / theme /
# commodity / macro / strategy), themes extracted from reports, links from
# themes to affected stocks (with impact direction / strength / path),
# discrete signal events ("target raised", "supply shortage", etc.), per-symbol
# consensus snapshots, and the score-calculation log.
#
# Copyright / compliance: only metadata + short summaries are stored. PDF
# bodies / paragraph text MUST NOT be persisted. `source_file_path` is for
# operator-local PDF locations and MUST NOT be exposed via API. Auto-crawling
# is out of scope for v0.4 — `extraction_method` simply tags how a row got in
# (MANUAL / CSV_IMPORT / RULE_BASED / LLM_ASSISTED).
# ---------------------------------------------------------------------------


class AnalystReport(TimestampMixin, Base):
    __tablename__ = "analyst_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    broker_name: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analyst_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[str | None] = mapped_column(String(32), nullable=True)
    normalized_rating: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    previous_target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    current_price_at_report: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    positive_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # operator-local PDF path; NEVER exposed via API
    source_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_reliability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(16), nullable=False)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    duplicate_group_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    themes: Mapped[list["ReportTheme"]] = relationship(
        back_populates="source_report",
        cascade="all, delete-orphan",
    )
    signal_events: Mapped[list["ReportSignalEvent"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "broker_name",
            "published_at",
            "title",
            name="uq_analyst_reports_broker_pub_title",
        ),
    )


class ReportTheme(TimestampMixin, Base):
    __tablename__ = "report_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    theme_category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    time_horizon: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_report_id: Mapped[int] = mapped_column(
        ForeignKey("analyst_reports.id"),
        nullable=False,
        index=True,
    )
    extraction_method: Mapped[str] = mapped_column(String(16), nullable=False)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    source_report: Mapped[AnalystReport] = relationship(back_populates="themes")
    stock_mappings: Mapped[list["ThemeStockMapping"]] = relationship(
        back_populates="theme",
        cascade="all, delete-orphan",
    )
    signal_events: Mapped[list["ReportSignalEvent"]] = relationship(back_populates="theme")

    __table_args__ = (
        UniqueConstraint(
            "source_report_id",
            "theme_name",
            name="uq_report_themes_report_theme",
        ),
    )


class ThemeStockMapping(TimestampMixin, Base):
    __tablename__ = "theme_stock_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("report_themes.id"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    relation_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    impact_direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    impact_strength: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    impact_path: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    benefit_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    time_lag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_sentence_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(16), nullable=False)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    theme: Mapped[ReportTheme] = relationship(back_populates="stock_mappings")

    __table_args__ = (
        UniqueConstraint("theme_id", "symbol", name="uq_theme_stock_mappings_theme_symbol"),
    )


class ReportSignalEvent(TimestampMixin, Base):
    __tablename__ = "report_signal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("analyst_reports.id"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    theme_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_themes.id"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    strength: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    time_horizon: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(16), nullable=False)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)

    report: Mapped[AnalystReport] = relationship(back_populates="signal_events")
    theme: Mapped[ReportTheme | None] = relationship(back_populates="signal_events")

    __table_args__ = (
        # NULL-aware uniqueness: SQLite + Postgres both treat NULLs as distinct
        # in unique constraints, which is acceptable here — duplicates without a
        # symbol/theme are rare and the unique tuple still prevents the most
        # common collision (same report + same event_type + same target).
        UniqueConstraint(
            "report_id",
            "event_type",
            "symbol",
            "theme_id",
            name="uq_report_signal_events_report_event_symbol_theme",
        ),
    )


class ReportConsensusSnapshot(Base):
    __tablename__ = "report_consensus_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    min_target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    max_target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    strong_buy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hold_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strong_sell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "snapshot_date",
            "window_days",
            name="uq_report_consensus_symbol_date_window",
        ),
    )


class ReportScoreLog(Base):
    __tablename__ = "report_score_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    theme_signal_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    theme_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_event_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_upside_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    rating_score_avg: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    recency_bonus: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    theme_signal_bonus: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    event_signal_bonus: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    risk_penalty: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendation_runs.run_id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "score_date",
            "recommendation_run_id",
            name="uq_report_score_logs_symbol_date_run",
        ),
    )


# ---------------------------------------------------------------------------
# v0.6 -- Fundamental & Earnings Intelligence
#
# FundamentalSnapshot stores normalized financial metrics only. Financial
# statement source documents, PDF/Excel blobs, full body text, paragraphs, and
# raw filing content are intentionally out of scope.
# ---------------------------------------------------------------------------


class FundamentalSnapshot(TimestampMixin, Base):
    __tablename__ = "fundamental_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    operating_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    total_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    per: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pbr: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    debt_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    revenue_growth_yoy: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    operating_income_growth_yoy: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "snapshot_date",
            "fiscal_year",
            "fiscal_quarter",
            name="uq_fundamental_snapshots_symbol_period",
        ),
    )


class EarningsEvent(TimestampMixin, Base):
    __tablename__ = "earnings_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    revenue_actual: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    revenue_consensus: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    operating_income_actual: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    operating_income_consensus: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    net_income_actual: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    net_income_consensus: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    eps_actual: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    eps_consensus: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    surprise_type: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    surprise_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "event_date",
            "fiscal_year",
            "fiscal_quarter",
            "event_type",
            name="uq_earnings_events_symbol_event",
        ),
    )


# ---------------------------------------------------------------------------
# v0.7 Phase B -- Strategy & Backtest Foundation
#
# BacktestRun is one execution of a single strategy over a date range.
# BacktestResult is one signal (BUY/PASS/AVOID) plus the recommendation_results
# horizon returns it was paired with. Win-rate / avg-return statistics are
# scoped to BUY signals only -- PASS / AVOID are counted but excluded from
# return aggregates (see BacktestEngine docstring).
#
# These tables are write targets for app/backtest/engine.py and read targets
# for the (Phase D) read-only API. They never reference broker / order-side
# fields.
# ---------------------------------------------------------------------------


class BacktestRun(TimestampMixin, Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avoid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate_1d: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    win_rate_3d: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    win_rate_5d: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    win_rate_20d: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    avg_return_1d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    avg_return_3d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    avg_return_5d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    avg_return_20d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRY_RUN")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    results: Mapped[list["BacktestResult"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id"),
        nullable=True,
    )
    recommendation_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendation_results.id"),
        nullable=True,
    )
    signal_action: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    return_1d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    return_3d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    return_5d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    return_20d: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    result_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # v0.7 Phase C — cost model + market regime breakdown.
    # cost_adjusted_return_5d is populated for BUY signals only (PASS / AVOID
    # leave it NULL by design). regime is the at-or-before MarketRegime label
    # for the recommendation_run.run_date; NULL when no regime data covers the
    # date (engine summary buckets these under "UNCLASSIFIED").
    cost_adjusted_return_5d: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )
    regime: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    run: Mapped[BacktestRun] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint(
            "backtest_run_id",
            "recommendation_id",
            name="uq_backtest_results_run_recommendation",
        ),
    )


# ---------------------------------------------------------------------------
# v0.8 Phase B -- single-user authentication foundation
#
# User: a single admin account (multi-user / RBAC / OAuth / SSO are out of
# scope -- see PLAN-0008). password_hash uses scrypt (see app/auth/security.py)
# and is NEVER null and NEVER stored in plaintext. last_login_at is updated by
# AuthService.login on a successful POST /api/auth/login.
#
# LoginAuditLog: append-only audit trail for LOGIN_SUCCESS / LOGIN_FAILED /
# LOGOUT events. source_ip and user_agent are SHA256-hashed before insert
# (`app.auth.security.hash_for_audit`) -- raw IP / UA are never persisted.
# ---------------------------------------------------------------------------


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    audit_logs: Mapped[list["LoginAuditLog"]] = relationship(
        back_populates="user",
    )
    watchlists: Mapped[list["Watchlist"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LoginAuditLog(Base):
    __tablename__ = "login_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # username is captured even for LOGIN_FAILED events where user_id is NULL,
    # so operators can investigate brute-force attempts on unknown accounts.
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # SHA256-hashed values only -- raw IP / user agent MUST NOT be stored.
    source_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    user: Mapped[User | None] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index(
            "ix_login_audit_logs_username_created",
            "username",
            "created_at",
        ),
        Index(
            "ix_login_audit_logs_event_created",
            "event_type",
            "created_at",
        ),
    )


# ---------------------------------------------------------------------------
# v0.8 Phase C -- Watchlist DB foundation
#
# Watchlist: a named bucket of stocks owned by exactly one User. A user may
# have multiple watchlists; at most one is `is_default = True`. Repositories
# enforce this invariant; the DB enforces uniqueness via Unique(user_id, name).
#
# WatchlistItem: a single symbol inside a Watchlist, plus an optional short
# operator memo. Symbol is normalized to UPPERCASE before persistence. The
# table intentionally has NO broker / account / quantity / order_price /
# order_type / side columns -- WatchlistItem is a "favourite", not an order.
# ---------------------------------------------------------------------------


class Watchlist(TimestampMixin, Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )


class WatchlistItem(TimestampMixin, Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Operator-facing memo. Hard-capped at 500 chars to discourage paragraph
    # bodies (the v0.4 copyright policy). API validation rejects >500 with 422.
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "symbol",
            name="uq_watchlist_items_watchlist_symbol",
        ),
    )


# ---------------------------------------------------------------------------
# v0.9 Phase C -- UserPreference (32nd table)
#
# One row per user. Stores UI/UX preferences only -- no secrets, no broker
# fields, no order-side data. notification_preferences_json is persisted
# as-is and NEVER connected to a live Telegram/Email sender here.
# default_watchlist_id is a nullable FK; cleared to NULL if the referenced
# watchlist is deleted (SET NULL on delete).
# ---------------------------------------------------------------------------


class UserPreference(TimestampMixin, Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    default_watchlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlists.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_market: Mapped[str | None] = mapped_column(String(32), nullable=True)
    default_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dashboard_layout_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notification_preferences_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="preferences")
    default_watchlist: Mapped["Watchlist | None"] = relationship(foreign_keys=[default_watchlist_id])


# ---------------------------------------------------------------------------
# v0.14 Phase B -- Virtual Trading Core (VirtualAccount, VirtualOrder)
#
# Foundation for in-process paper / simulation trading. NO real broker /
# KIS / autotrade integration is wired here -- VirtualOrder is a pure DB row
# written by ``app.broker.simulation_broker.SimulationBroker`` and gated by
# ``Settings.paper_trading_enabled`` (default False).
#
# Forbidden columns (regression-tested in
# tests/integration/test_virtual_trading_core.py): ``broker_order_id``,
# ``kis_order_id``, ``real_account``, ``api_key``, ``token``, ``secret``.
# VirtualPosition / VirtualFill / VirtualPnLSnapshot belong to Phase C.
# ---------------------------------------------------------------------------


class VirtualAccount(TimestampMixin, Base):
    __tablename__ = "virtual_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Optional FK to users.id. Single-user deployments may leave this NULL --
    # the simulation core works without authentication, mirroring the v0.7
    # backtest engine which is also user-agnostic.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="KRW")
    # Per-account opt-in flag. The global ``Settings.paper_trading_enabled``
    # gates the broker; this column is the per-account knob (e.g. an admin
    # can pre-create accounts but keep them inert).
    paper_trading_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    orders: Mapped[list["VirtualOrder"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_virtual_accounts_user_name"),
    )


class VirtualOrder(TimestampMixin, Base):
    __tablename__ = "virtual_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # BUY / SELL only; enforced application-side by SimulationBroker.
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # MARKET / LIMIT only; enforced application-side by SimulationBroker.
    order_type: Mapped[str] = mapped_column(String(16), nullable=False, default="MARKET")
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    # CREATED / SUBMITTED / PARTIALLY_FILLED / FILLED / CANCELED / REJECTED.
    # Phase B writes only CREATED / CANCELED / REJECTED; fill states are
    # produced by Phase C's execute_pending_orders().
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CREATED", index=True
    )
    # Idempotency key for client-driven dedup. Unique per account so two
    # accounts can independently use the same client-side key.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Short, operator-facing reason / note. Hard-capped to 256 chars to
    # discourage paragraph dumps -- VirtualOrder is metadata, not a journal.
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    account: Mapped[VirtualAccount] = relationship(back_populates="orders")

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "idempotency_key",
            name="uq_virtual_orders_account_idempotency",
        ),
        Index("ix_virtual_orders_account_status", "account_id", "status"),
    )


# ---------------------------------------------------------------------------
# v0.14 Phase C -- Virtual Trading PnL & Fill Engine
#
# Three additional tables that complete the in-process paper trading core:
#
#   * ``virtual_positions`` (35th) -- per-(account, symbol) holding state.
#     ``upsert`` semantics: BUY raises quantity and recomputes ``avg_cost``
#     using a cost-basis blended with the new fill (fees included).
#     SELL lowers quantity and accumulates ``realized_pnl``.
#   * ``virtual_fills`` (36th) -- one row per actual fill performed by
#     ``SimulationBroker.execute_pending_orders()``. Records gross / net
#     amounts plus the three cost components separately so reports can
#     reconstruct the cost breakdown.
#   * ``virtual_pnl_snapshots`` (37th) -- daily account-level PnL summary.
#     ``UNIQUE(account_id, snapshot_date)`` so a re-run of the snapshot job
#     replaces the existing row (see PnLTracker.create_daily_pnl_snapshot).
#
# Forbidden columns (regression-tested in
# tests/integration/test_virtual_pnl_engine.py): ``broker_order_id``,
# ``kis_order_id``, ``real_account``, ``api_key``, ``token``, ``secret``.
# ---------------------------------------------------------------------------


class VirtualPosition(TimestampMixin, Base):
    __tablename__ = "virtual_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Cumulative net long position. SELL of held qty zeroes this out and
    # leaves ``avg_cost`` reset to 0; the row itself is preserved so
    # ``realized_pnl`` history is not lost.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    # Lifetime realized P&L on this (account, symbol) pair. Only SELL fills
    # update this; BUY fills only mutate quantity / avg_cost.
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "symbol",
            name="uq_virtual_positions_account_symbol",
        ),
    )


class VirtualFill(Base):
    __tablename__ = "virtual_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("virtual_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    fill_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # Cost components stored separately so reports can reproduce the math.
    fee: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    stamp_tax: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    slippage: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    # gross_amount = fill_price * quantity (always positive)
    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    # net_amount: cash flow direction is encoded by ``side``. For BUY this is
    # cash spent (gross + fee + slippage); for SELL this is cash received
    # (gross - fee - stamp_tax - slippage). Always stored as a positive value
    # representing the magnitude.
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    filled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_virtual_fills_account_symbol", "account_id", "symbol"),
    )


class VirtualPnLSnapshot(TimestampMixin, Base):
    __tablename__ = "virtual_pnl_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # total_value = cash_balance + market_value
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "snapshot_date",
            name="uq_virtual_pnl_snapshots_account_date",
        ),
        Index(
            "ix_virtual_pnl_snapshots_account_date",
            "account_id",
            "snapshot_date",
        ),
    )


# ---------------------------------------------------------------------------
# v0.15 Phase B -- Approval Trading Safety Layer (OrderCandidate, 38th table)
#
# OrderCandidate is the staging row for any order that wants to be executed
# against a paper account. Phase B introduces ORM + repository + state
# machine; the PreTradeRiskEngine (Phase C), Approval API + AuditLog
# (Phase D), and frontend (Phase E) consume this table afterwards.
#
# Hard policies enforced here:
#   * Only paper execution is allowed -- the optional ``virtual_order_id``
#     FK pointing at ``virtual_orders.id`` is the ONLY downstream link.
#     Real KIS / real broker / real account columns are explicitly absent.
#   * Forbidden columns (regression-tested in
#     tests/integration/test_order_candidate_repository.py):
#     ``broker_order_id``, ``kis_order_id``, ``real_account``, ``real_order_id``,
#     ``api_key``, ``token``, ``secret``.
# ---------------------------------------------------------------------------


class OrderCandidate(TimestampMixin, Base):
    __tablename__ = "order_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("virtual_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Provenance: where this candidate came from. Validated application-side.
    # Allowed values: RECOMMENDATION / STRATEGY / PAPER / MANUAL.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # Optional id of the upstream row (recommendation_id / backtest_result_id /
    # virtual_order_id at submission time / NULL for MANUAL). The FK is
    # intentionally NOT modeled so that referencing tables can come and go
    # without breaking historical candidates.
    source_ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # BUY / SELL only; enforced application-side by the repository.
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # MARKET / LIMIT only; enforced application-side by the repository.
    order_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MARKET"
    )
    limit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    # quantity * (limit_price OR last close price). Set by the caller at
    # creation time so the risk engine can evaluate per-order / daily caps
    # without re-resolving prices.
    estimated_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    # 8-state machine -- DRAFT / RISK_CHECKING / RISK_REJECTED /
    # PENDING_APPROVAL / APPROVED / EXECUTED_PAPER / REJECTED / EXPIRED.
    # Allowed transitions are enforced by OrderCandidateRepository.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", index=True
    )
    # PreTradeRiskEngine output (Phase C). Whitelist-shaped:
    # {"passed": bool, "violations": [{"rule_name": str, "message": str,
    #  "severity": "HARD"|"SOFT"}], "policy_version": str,
    #  "evaluated_at": ISO8601}.
    risk_check_result_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    # Filled when an admin user approves OR rejects the candidate.
    approver_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    # Short, operator-facing reason for REJECTED / RISK_REJECTED / EXPIRED.
    rejection_reason: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    # TTL. PENDING_APPROVAL candidates past this time are eligible for
    # EXPIRED transition (lazy or scheduler-driven, Phase D).
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # Set when the approved candidate has been forwarded to
    # SimulationBroker.submit_order. NEVER points at a real KIS order.
    virtual_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("virtual_orders.id"),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_order_candidates_account_status",
            "account_id",
            "status",
        ),
    )
