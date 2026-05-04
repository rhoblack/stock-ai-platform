"""Deterministic mock seed for v0.1 local integration runs.

Populates every v0.1 table the dashboard / scheduler / engines read from, so
that operators (and CI smoke jobs) can exercise the full backend stack
without any KIS API keys, real Telegram bot, or production DB.

Boundary rules (Test / Review / Docs Agent):
    * No KIS HTTP calls, no Telegram dispatch, no order placement.
    * No score-formula or engine logic — values are plausibility-tuned by
      hand so the UI and engines have realistic inputs to display / process.
    * Idempotent: re-running upserts the same rows. Pass ``--reset`` to drop
      and recreate the schema (destructive — only safe for the local SQLite
      file).
    * Targets ``settings.effective_database_url`` by default. Override with
      ``--db-url`` when seeding a Docker/Postgres instance.

Tables seeded:
    stocks · market_cap_rankings · stock_universes · stock_universe_members
    daily_prices · stock_indicators · holdings · recommendation_runs ·
    recommendations · data_snapshots · holding_checks

Tables intentionally untouched (populated by jobs / future pipelines):
    job_runs · notification_logs · decision_logs · recommendation_results ·
    news_items · market_regimes
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.data.repositories import (
    DailyPriceRepository,
    DataSnapshotRepository,
    HoldingCheckRepository,
    HoldingRepository,
    MarketCapRankingRepository,
    RecommendationRepository,
    RecommendationRunRepository,
    StockIndicatorRepository,
    StockRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.db import Base
from app.db.models import (
    DataSnapshot,
    Holding,
    MarketCapRanking,
    Recommendation,
    RecommendationRun,
    HoldingCheck,
)
from app.db.session import create_session_factory


_TOTAL_PRICE_BARS = 30
_UNIVERSE_NAME = "MARKET_CAP_TOP_500"


@dataclass(frozen=True)
class _SeedStock:
    symbol: str
    name: str
    market: str
    sector: str
    rank: int
    market_cap: Decimal
    listed_shares: int
    base_price: Decimal
    trend: Decimal  # per-bar drift
    volatility: Decimal  # per-bar high/low spread


_STOCKS: list[_SeedStock] = [
    _SeedStock(
        symbol="005930", name="삼성전자", market="KOSPI", sector="반도체",
        rank=1, market_cap=Decimal("450000000000000"), listed_shares=5_969_782_550,
        base_price=Decimal("70000"), trend=Decimal("80"), volatility=Decimal("450"),
    ),
    _SeedStock(
        symbol="000660", name="SK하이닉스", market="KOSPI", sector="반도체",
        rank=2, market_cap=Decimal("150000000000000"), listed_shares=728_002_365,
        base_price=Decimal("180000"), trend=Decimal("260"), volatility=Decimal("1200"),
    ),
    _SeedStock(
        symbol="035420", name="NAVER", market="KOSPI", sector="인터넷",
        rank=3, market_cap=Decimal("32000000000000"), listed_shares=164_263_395,
        base_price=Decimal("210000"), trend=Decimal("-90"), volatility=Decimal("1300"),
    ),
    _SeedStock(
        symbol="005380", name="현대차", market="KOSPI", sector="자동차",
        rank=4, market_cap=Decimal("60000000000000"), listed_shares=210_991_796,
        base_price=Decimal("260000"), trend=Decimal("180"), volatility=Decimal("1700"),
    ),
    _SeedStock(
        symbol="035720", name="카카오", market="KOSPI", sector="인터넷",
        rank=5, market_cap=Decimal("28000000000000"), listed_shares=443_116_201,
        base_price=Decimal("55000"), trend=Decimal("-40"), volatility=Decimal("550"),
    ),
]


@dataclass(frozen=True)
class _SeedHolding:
    symbol: str
    quantity: Decimal
    avg_buy_price: Decimal
    buy_date: date
    strategy_type: str


@dataclass(frozen=True)
class _RecommendationSeed:
    run_offset_days: int
    items: tuple[tuple[str, int, str, Decimal, Decimal], ...]  # symbol, rank, grade, total, technical


_RECOMMENDATIONS: tuple[_RecommendationSeed, ...] = (
    _RecommendationSeed(
        run_offset_days=0,
        items=(
            ("005930", 1, "A", Decimal("82"), Decimal("80")),
            ("000660", 2, "B", Decimal("68"), Decimal("64")),
            ("005380", 3, "B", Decimal("60"), Decimal("58")),
        ),
    ),
    _RecommendationSeed(
        run_offset_days=3,
        items=(
            ("000660", 1, "A", Decimal("78"), Decimal("76")),
            ("005930", 2, "A", Decimal("76"), Decimal("74")),
            ("035420", 3, "C", Decimal("48"), Decimal("44")),
        ),
    ),
    _RecommendationSeed(
        run_offset_days=7,
        items=(
            ("005930", 1, "A", Decimal("80"), Decimal("82")),
            ("005380", 2, "B", Decimal("62"), Decimal("60")),
        ),
    ),
)


def _summary() -> dict[str, int]:
    return {
        "stocks": 0,
        "market_cap_rankings": 0,
        "universe_members": 0,
        "daily_prices": 0,
        "stock_indicators": 0,
        "holdings": 0,
        "recommendation_runs": 0,
        "recommendations": 0,
        "holding_checks": 0,
        "data_snapshots": 0,
    }


def _seed_stocks(session: Session, summary: dict[str, int]) -> None:
    repo = StockRepository(session)
    for stock in _STOCKS:
        _, created = repo.upsert(
            symbol=stock.symbol,
            market=stock.market,
            name=stock.name,
            sector=stock.sector,
        )
        if created:
            summary["stocks"] += 1


def _seed_market_cap_rankings(
    session: Session, *, today: date, summary: dict[str, int]
) -> None:
    repo = MarketCapRankingRepository(session)
    rankings = [
        MarketCapRanking(
            rank_date=today,
            market=stock.market,
            rank=stock.rank,
            symbol=stock.symbol,
            name=stock.name,
            market_cap=stock.market_cap,
            close_price=stock.base_price + (stock.trend * Decimal(_TOTAL_PRICE_BARS - 1)),
            listed_shares=stock.listed_shares,
            sector=stock.sector,
            is_analysis_target=True,
        )
        for stock in _STOCKS
    ]
    summary["market_cap_rankings"] = repo.replace_for_date_market(
        rank_date=today,
        market="KOSPI",
        rankings=rankings,
    )


def _seed_universe(session: Session, summary: dict[str, int]) -> None:
    universe_repo = StockUniverseRepository(session)
    member_repo = StockUniverseMemberRepository(session)
    universe, _ = universe_repo.get_or_create(
        name=_UNIVERSE_NAME,
        description="시가총액 상위 종목 (mock seed)",
    )
    session.flush()
    for stock in _STOCKS:
        _, created = member_repo.add_if_missing(
            universe_id=universe.universe_id,
            symbol=stock.symbol,
            reason="seed_mock_data",
        )
        if created:
            summary["universe_members"] += 1


def _seed_daily_prices(
    session: Session, *, today: date, summary: dict[str, int]
) -> None:
    repo = DailyPriceRepository(session)
    for stock in _STOCKS:
        for offset in range(_TOTAL_PRICE_BARS):
            bar_date = today - timedelta(days=_TOTAL_PRICE_BARS - 1 - offset)
            close = stock.base_price + (stock.trend * Decimal(offset))
            high = close + stock.volatility
            low = close - stock.volatility
            open_ = close - (stock.trend / Decimal(2))
            existing = repo.get_by_symbol_date(stock.symbol, bar_date)
            if existing is None:
                summary["daily_prices"] += 1
            from app.db.models import DailyPrice
            if existing is None:
                repo.add(
                    DailyPrice(
                        symbol=stock.symbol,
                        date=bar_date,
                        open=open_,
                        high=high,
                        low=low,
                        close=close,
                        volume=1_500_000 + offset * 10_000,
                        trading_value=close * Decimal(1_500_000 + offset * 10_000),
                    ),
                )
            else:
                existing.open = open_
                existing.high = high
                existing.low = low
                existing.close = close
                existing.volume = 1_500_000 + offset * 10_000
                existing.trading_value = close * Decimal(
                    1_500_000 + offset * 10_000,
                )
        session.flush()


def _seed_stock_indicators(
    session: Session, *, today: date, summary: dict[str, int]
) -> None:
    repo = StockIndicatorRepository(session)
    for stock in _STOCKS:
        latest_close = stock.base_price + (
            stock.trend * Decimal(_TOTAL_PRICE_BARS - 1)
        )
        ma5 = latest_close - (stock.trend * Decimal("2"))
        ma20 = latest_close - (stock.trend * Decimal("9"))
        ma60 = latest_close - (stock.trend * Decimal("9"))  # only 30 bars seeded
        # Bullish if ma5 > ma20, bearish otherwise
        if ma5 > ma20:
            alignment = "BULL"
            technical_score = Decimal("78")
        elif ma5 == ma20:
            alignment = "NEUTRAL"
            technical_score = Decimal("55")
        else:
            alignment = "BEAR"
            technical_score = Decimal("38")
        previous_indicator = repo.get_by_symbol_date(stock.symbol, today)
        if previous_indicator is None:
            summary["stock_indicators"] += 1
        repo.upsert(
            symbol=stock.symbol,
            indicator_date=today,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            ma120=None,
            rsi14=Decimal("55"),
            macd=stock.trend * Decimal("0.05"),
            macd_signal=stock.trend * Decimal("0.04"),
            volume_ratio_20d=Decimal("1.4") if alignment == "BULL" else Decimal("0.9"),
            breakout_20d=alignment == "BULL",
            breakout_60d=False,
            ma_alignment=alignment,
            technical_score=technical_score,
        )


def _seed_holdings(session: Session, summary: dict[str, int]) -> None:
    repo = HoldingRepository(session)
    seeds: list[_SeedHolding] = [
        _SeedHolding(
            symbol="005930",
            quantity=Decimal("20"),
            avg_buy_price=Decimal("66000"),
            buy_date=date(2026, 4, 1),
            strategy_type="LONG",
        ),
        _SeedHolding(
            symbol="000660",
            quantity=Decimal("5"),
            avg_buy_price=Decimal("190000"),
            buy_date=date(2026, 4, 10),
            strategy_type="MID",
        ),
    ]
    for s in seeds:
        existing = repo.get_active_by_symbol(s.symbol)
        if existing is None:
            repo.add(
                Holding(
                    symbol=s.symbol,
                    quantity=s.quantity,
                    avg_buy_price=s.avg_buy_price,
                    buy_date=s.buy_date,
                    strategy_type=s.strategy_type,
                    is_active=True,
                ),
            )
            summary["holdings"] += 1
        else:
            existing.quantity = s.quantity
            existing.avg_buy_price = s.avg_buy_price
            existing.buy_date = s.buy_date
            existing.strategy_type = s.strategy_type
            existing.is_active = True
    session.flush()


def _seed_recommendation_runs(
    session: Session, *, today: date, summary: dict[str, int]
) -> None:
    run_repo = RecommendationRunRepository(session)
    rec_repo = RecommendationRepository(session)
    snapshot_repo = DataSnapshotRepository(session)
    stock_lookup = {s.symbol: s for s in _STOCKS}

    for seed in _RECOMMENDATIONS:
        run_date = today - timedelta(days=seed.run_offset_days)
        # Idempotency: skip if a run already exists on that date.
        existing_runs = run_repo.list_by_date_range(
            start_date=run_date, end_date=run_date,
        )
        if existing_runs:
            continue
        started_at = datetime.combine(
            run_date, datetime.min.time(), tzinfo=UTC,
        ).replace(hour=6)
        run = run_repo.add(
            RecommendationRun(
                run_date=run_date,
                started_at=started_at,
                finished_at=started_at + timedelta(minutes=2),
                status="SUCCESS",
                telegram_sent=False,
                market_summary={
                    "universe": _UNIVERSE_NAME,
                    "candidate_count": len(seed.items),
                    "saved_count": len(seed.items),
                    "phase": "seed_mock_data",
                },
            ),
        )
        session.flush()
        summary["recommendation_runs"] += 1

        for symbol, rank, grade, total, technical in seed.items:
            stock = stock_lookup[symbol]
            risk_level = "LOW" if total >= Decimal("65") else "MEDIUM"
            risk_flags: list[str] = (
                [] if risk_level == "LOW" else ["BEARISH_MA_ALIGNMENT"]
            )
            snapshot = snapshot_repo.add(
                DataSnapshot(
                    snapshot_time=started_at,
                    symbol=symbol,
                    snapshot_type="RECOMMENDATION",
                    indicator_data_json={"technical_score": str(technical)},
                    market_context_json={
                        "phase": "seed_mock_data",
                        "risk_summary": {
                            "level": risk_level,
                            "flags": risk_flags,
                            "penalty": "0" if risk_level == "LOW" else "8",
                        },
                    },
                ),
            )
            session.flush()
            summary["data_snapshots"] += 1
            rec_repo.add(
                Recommendation(
                    run_id=run.run_id,
                    rank=rank,
                    market=stock.market,
                    symbol=symbol,
                    name=stock.name,
                    grade=grade,
                    total_score=total,
                    technical_score=technical,
                    news_score=Decimal("50"),
                    supply_score=Decimal("55") if risk_level == "LOW" else Decimal("45"),
                    fundamental_score=Decimal("50"),
                    ai_score=Decimal("55") if risk_level == "LOW" else Decimal("45"),
                    risk_score=Decimal("0") if risk_level == "LOW" else Decimal("8"),
                    reason=f"{stock.name} 관찰 후보 · 기술점수 {technical}",
                    risk_note="seed_mock_data placeholder",
                    snapshot_id=snapshot.snapshot_id,
                ),
            )
            summary["recommendations"] += 1


def _seed_holding_checks(
    session: Session, *, today: date, summary: dict[str, int]
) -> None:
    """Seed PRE_MARKET (today-1) + PRE_MARKET (today) + POST_MARKET (today)
    for the first holding so the dashboard /api/holdings/{symbol}/checks
    summary has trend data, plus a single PRE_MARKET row for the second
    holding so /api/holdings/checks/latest returns multi-symbol coverage.
    """
    check_repo = HoldingCheckRepository(session)
    snapshot_repo = DataSnapshotRepository(session)

    yesterday = today - timedelta(days=1)
    holding_seeds = (
        # symbol, check_date, check_type, total_score, return_rate, alert, decision, level
        ("005930", yesterday, "PRE_MARKET", Decimal("70"), Decimal("4"), False, "HOLD", "LOW"),
        ("005930", today, "PRE_MARKET", Decimal("60"), Decimal("3"), False, "WATCH", "MEDIUM"),
        ("005930", today, "POST_MARKET", Decimal("48"), Decimal("2"), True, "REDUCE", "HIGH"),
        ("000660", today, "PRE_MARKET", Decimal("66"), Decimal("-5"), False, "WATCH", "MEDIUM"),
    )

    for symbol, c_date, c_type, total, rr, alert, decision, level in holding_seeds:
        existing = check_repo.get_by_date_type_symbol(c_date, c_type, symbol)
        if existing is not None:
            continue
        flags = (
            ["MA20_BREAKDOWN"] if level == "HIGH"
            else (["SCORE_DROP"] if level == "MEDIUM" else [])
        )
        snapshot = snapshot_repo.add(
            DataSnapshot(
                snapshot_time=datetime.combine(
                    c_date, datetime.min.time(), tzinfo=UTC,
                ).replace(hour=8 if c_type == "PRE_MARKET" else 16, minute=30),
                symbol=symbol,
                snapshot_type="HOLDING_CHECK",
                market_context_json={
                    "check_date": c_date.isoformat(),
                    "check_type": c_type,
                    "phase": "seed_mock_data",
                    "risk_summary": {
                        "level": level,
                        "flags": flags,
                        "penalty": "0" if level == "LOW" else "8",
                    },
                },
            ),
        )
        session.flush()
        summary["data_snapshots"] += 1
        check_repo.add(
            HoldingCheck(
                check_date=c_date,
                check_type=c_type,
                symbol=symbol,
                current_price=Decimal("70000") if symbol == "005930" else Decimal("180000"),
                avg_buy_price=Decimal("66000") if symbol == "005930" else Decimal("190000"),
                return_rate=rr,
                technical_score=total - Decimal("5"),
                news_score=Decimal("50"),
                earnings_score=Decimal("50"),
                ai_score=Decimal("50"),
                risk_score=Decimal("0") if level == "LOW" else Decimal("8"),
                total_score=total,
                grade="A" if total >= Decimal("70") else ("B" if total >= Decimal("55") else "C"),
                decision=decision,
                reason=f"seed mock — {decision}",
                alert=alert,
                snapshot_id=snapshot.snapshot_id,
            ),
        )
        summary["holding_checks"] += 1


def seed(
    *,
    database_url: str | None = None,
    reset: bool = False,
) -> dict[str, int]:
    """Seed the database. Returns a counts summary."""
    url = database_url or get_settings().effective_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)

    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    factory = create_session_factory(engine)
    session: Session = factory()
    summary = _summary()
    today = datetime.now(UTC).date()

    try:
        _seed_stocks(session, summary)
        _seed_market_cap_rankings(session, today=today, summary=summary)
        _seed_universe(session, summary)
        _seed_daily_prices(session, today=today, summary=summary)
        _seed_stock_indicators(session, today=today, summary=summary)
        _seed_holdings(session, summary)
        _seed_recommendation_runs(session, today=today, summary=summary)
        _seed_holding_checks(session, today=today, summary=summary)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="SQLAlchemy URL override (default: settings.effective_database_url)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DROP all tables before seeding (destructive — local SQLite only)",
    )
    args = parser.parse_args()
    summary = seed(database_url=args.db_url, reset=args.reset)
    print("Mock seed complete. New rows by table:")
    for key, value in summary.items():
        print(f"  {key:>22}: {value}")


if __name__ == "__main__":
    main()
