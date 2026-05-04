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
