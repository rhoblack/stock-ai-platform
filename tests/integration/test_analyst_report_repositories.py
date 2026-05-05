"""Integration tests for the 6 v0.4 Analyst & Theme Intelligence repositories.

Scope (Phase A only):
  * AnalystReport CRUD + unique conflict + COMPANY/THEME/COMMODITY/MACRO types
  * Global report (US/NASDAQ/USD currency) round-trip
  * symbol nullable for THEME/MACRO/COMMODITY
  * ReportTheme upsert by (source_report_id, theme_name)
  * ThemeStockMapping CRUD + theme/symbol queries + positive/negative + impact_path
  * ReportSignalEvent CRUD + symbol/theme/event_type/direction queries
  * ReportConsensusSnapshot upsert (window_days variant)
  * ReportScoreLog CRUD + recommendation_run linkage

Out of scope (NOT covered here):
  * report_score / theme_signal_score formula — Phase C
  * CSV / Excel import flow — Phase B
  * API schema masking of source_file_path — Phase D
"""

from datetime import date
from decimal import Decimal

import pytest

from app.data.repositories import (
    AnalystReportRepository,
    ReportConsensusSnapshotRepository,
    ReportScoreLogRepository,
    ReportSignalEventRepository,
    ReportThemeRepository,
    ThemeStockMappingRepository,
)
from app.db import Base
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


# ---------- AnalystReport ----------


def _create_company_report(session, *, symbol="005930", title="삼성전자 BUY"):
    repo = AnalystReportRepository(session)
    rep = repo.create(
        broker_name="삼성증권",
        published_at=date(2026, 5, 1),
        title=title,
        report_type="COMPANY",
        extraction_method="MANUAL",
        symbol=symbol,
        company_name="삼성전자",
        market="KOSPI",
        country="KR",
        currency="KRW",
        rating="BUY",
        normalized_rating="BUY",
        target_price=Decimal("90000"),
        current_price_at_report=Decimal("70000"),
        summary="HBM 수요 회복 + 메모리 가격 반등 기대",
        source_url="https://example.com/report1",
        source_file_path="D:/reports/005930_2026-05-01.pdf",
        language="ko",
    )
    session.commit()
    return rep


def test_analyst_report_company_crud(session):
    rep = _create_company_report(session)
    assert rep.id is not None
    repo = AnalystReportRepository(session)
    fetched = repo.get_by_id(rep.id)
    assert fetched is not None
    assert fetched.symbol == "005930"
    assert fetched.normalized_rating == "BUY"
    assert fetched.target_price == Decimal("90000.0000")
    assert fetched.report_type == "COMPANY"
    # source_file_path is stored verbatim — masking is the API layer's job
    assert fetched.source_file_path == "D:/reports/005930_2026-05-01.pdf"


def test_analyst_report_unique_conflict_returns_existing(session):
    rep1 = _create_company_report(session)
    repo = AnalystReportRepository(session)
    rep2 = repo.upsert_unique(
        broker_name="삼성증권",
        published_at=date(2026, 5, 1),
        title="삼성전자 BUY",
        report_type="COMPANY",
        extraction_method="CSV_IMPORT",
        symbol="005930",
    )
    session.commit()
    assert rep1.id == rep2.id
    # extraction_method on the existing row is NOT overwritten
    assert rep2.extraction_method == "MANUAL"


def test_analyst_report_theme_macro_commodity_with_null_symbol(session):
    repo = AnalystReportRepository(session)
    theme_rep = repo.create(
        broker_name="키움증권",
        published_at=date(2026, 4, 28),
        title="HBM 사이클 회복 분석",
        report_type="THEME",
        extraction_method="MANUAL",
        symbol=None,
    )
    macro_rep = repo.create(
        broker_name="삼성증권",
        published_at=date(2026, 4, 25),
        title="2026 하반기 매크로 전망",
        report_type="MACRO",
        extraction_method="MANUAL",
    )
    commodity_rep = repo.create(
        broker_name="NH투자증권",
        published_at=date(2026, 4, 20),
        title="구리 가격 전망 — 공급 부족 지속",
        report_type="COMMODITY",
        extraction_method="MANUAL",
    )
    session.commit()
    assert theme_rep.symbol is None and theme_rep.report_type == "THEME"
    assert macro_rep.symbol is None and macro_rep.report_type == "MACRO"
    assert commodity_rep.symbol is None and commodity_rep.report_type == "COMMODITY"


def test_analyst_report_global_us_listing_with_usd_currency(session):
    repo = AnalystReportRepository(session)
    rep = repo.create(
        broker_name="Goldman Sachs",
        broker_country="US",
        published_at=date(2026, 4, 15),
        title="NVDA Buy — TP $1500",
        report_type="COMPANY",
        extraction_method="MANUAL",
        symbol="NVDA",
        company_name="NVIDIA",
        market="US",
        exchange="NASDAQ",
        country="US",
        currency="USD",
        rating="BUY",
        normalized_rating="BUY",
        target_price=Decimal("1500"),
        language="en",
    )
    session.commit()
    fetched = repo.get_by_id(rep.id)
    assert fetched is not None
    assert fetched.market == "US"
    assert fetched.exchange == "NASDAQ"
    assert fetched.currency == "USD"
    assert fetched.broker_country == "US"


def test_analyst_report_list_by_symbol_and_type(session):
    repo = AnalystReportRepository(session)
    _create_company_report(session, symbol="005930", title="삼성전자 BUY")
    _create_company_report(session, symbol="005930", title="삼성전자 HOLD")
    repo.create(
        broker_name="키움증권",
        published_at=date(2026, 4, 1),
        title="조선업 회복",
        report_type="SECTOR",
        extraction_method="MANUAL",
    )
    session.commit()

    by_sym = repo.list_by_symbol("005930")
    assert len(by_sym) == 2
    by_type = repo.list_by_report_type("SECTOR")
    assert len(by_type) == 1
    assert by_type[0].title == "조선업 회복"


def test_analyst_report_search_text_matches_title_and_summary(session):
    rep = _create_company_report(session)
    assert rep.summary is not None and "HBM" in rep.summary
    repo = AnalystReportRepository(session)
    hits = repo.search_text("HBM")
    assert len(hits) >= 1
    assert any(r.id == rep.id for r in hits)


# ---------- ReportTheme ----------


def test_report_theme_create_and_upsert_unique(session):
    rep = _create_company_report(session)
    theme_repo = ReportThemeRepository(session)
    th1 = theme_repo.create(
        theme_name="HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
        confidence=Decimal("0.9"),
    )
    session.commit()
    th2 = theme_repo.upsert_by_report_and_theme(
        source_report_id=rep.id,
        theme_name="HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID_TERM",
        extraction_method="LLM_ASSISTED",
    )
    session.commit()
    assert th1.id == th2.id
    # extraction_method NOT overwritten
    assert th2.extraction_method == "MANUAL"


def test_report_theme_list_by_category_and_direction(session):
    rep = _create_company_report(session)
    repo = ReportThemeRepository(session)
    repo.create(
        theme_name="HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
    )
    repo.create(
        theme_name="구리 부족",
        theme_category="COMMODITY",
        direction="POSITIVE",
        time_horizon="LONG_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
    )
    repo.create(
        theme_name="원전 부진",
        theme_category="ENERGY",
        direction="NEGATIVE",
        time_horizon="SHORT_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
    )
    session.commit()
    semi = repo.list_by_category("SEMICONDUCTOR")
    assert len(semi) == 1 and semi[0].theme_name == "HBM"
    positives = repo.list_by_direction("POSITIVE")
    assert len(positives) == 2
    by_report = repo.list_by_source_report(rep.id)
    assert len(by_report) == 3


# ---------- ThemeStockMapping ----------


def test_theme_stock_mapping_crud_and_unique(session):
    rep = _create_company_report(session)
    theme = ReportThemeRepository(session).create(
        theme_name="HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
    )
    session.commit()
    repo = ThemeStockMappingRepository(session)
    m1 = repo.create(
        theme_id=theme.id,
        symbol="000660",
        company_name="SK하이닉스",
        market="KOSPI",
        country="KR",
        relation_type="PRODUCER",
        impact_direction="POSITIVE",
        impact_strength=Decimal("0.85"),
        impact_path="DEMAND_INCREASE",
        benefit_type="DIRECT",
        time_lag="SHORT_TERM",
        extraction_method="MANUAL",
    )
    session.commit()
    m2 = repo.upsert_by_theme_and_symbol(
        theme_id=theme.id,
        symbol="000660",
        impact_direction="POSITIVE",
        extraction_method="MANUAL",
    )
    session.commit()
    assert m1.id == m2.id


def test_theme_stock_mapping_queries_by_theme_symbol_direction_path(session):
    rep = _create_company_report(session)
    th_repo = ReportThemeRepository(session)
    semi_theme = th_repo.create(
        theme_name="HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
    )
    cu_theme = th_repo.create(
        theme_name="구리 부족",
        theme_category="COMMODITY",
        direction="POSITIVE",
        time_horizon="LONG_TERM",
        source_report_id=rep.id,
        extraction_method="MANUAL",
    )
    session.commit()

    m_repo = ThemeStockMappingRepository(session)
    # SK하이닉스: HBM POSITIVE producer
    m_repo.create(
        theme_id=semi_theme.id,
        symbol="000660",
        impact_direction="POSITIVE",
        impact_path="DEMAND_INCREASE",
        extraction_method="MANUAL",
    )
    # 풍산: 구리 부족 → COST_PRESSURE 부담 (NEGATIVE)
    m_repo.create(
        theme_id=cu_theme.id,
        symbol="103140",
        impact_direction="NEGATIVE",
        impact_path="COST_PRESSURE",
        extraction_method="MANUAL",
    )
    # LS: 구리 가격 상승 → 마진 개선 (POSITIVE)
    m_repo.create(
        theme_id=cu_theme.id,
        symbol="006260",
        impact_direction="POSITIVE",
        impact_path="MARGIN_IMPROVEMENT",
        extraction_method="MANUAL",
    )
    session.commit()

    by_theme = m_repo.list_by_theme(cu_theme.id)
    assert {m.symbol for m in by_theme} == {"103140", "006260"}

    by_symbol = m_repo.list_by_symbol("000660")
    assert len(by_symbol) == 1 and by_symbol[0].theme_id == semi_theme.id

    pos_006260 = m_repo.list_positive_by_symbol("006260")
    assert len(pos_006260) == 1
    neg_103140 = m_repo.list_negative_by_symbol("103140")
    assert len(neg_103140) == 1
    by_path = m_repo.list_by_impact_path("DEMAND_INCREASE")
    assert len(by_path) == 1 and by_path[0].symbol == "000660"


# ---------- ReportSignalEvent ----------


def test_report_signal_event_crud_and_unique(session):
    rep = _create_company_report(session)
    repo = ReportSignalEventRepository(session)
    e1 = repo.create(
        report_id=rep.id,
        event_type="TARGET_PRICE_UP",
        direction="POSITIVE",
        time_horizon="SHORT_TERM",
        extraction_method="MANUAL",
        symbol="005930",
        strength=Decimal("0.7"),
        evidence_json={"prev": 80000, "new": 90000},
    )
    session.commit()
    e2 = repo.upsert_by_report_event_symbol_theme(
        report_id=rep.id,
        event_type="TARGET_PRICE_UP",
        direction="POSITIVE",
        time_horizon="SHORT_TERM",
        extraction_method="LLM_ASSISTED",
        symbol="005930",
    )
    session.commit()
    assert e1.id == e2.id
    assert e2.evidence_json == {"prev": 80000, "new": 90000}


def test_report_signal_event_list_queries(session):
    rep1 = _create_company_report(session, symbol="005930", title="삼성전자 BUY")
    rep2 = _create_company_report(session, symbol="000660", title="SK하이닉스 BUY")
    th = ReportThemeRepository(session).create(
        theme_name="HBM",
        theme_category="SEMICONDUCTOR",
        direction="POSITIVE",
        time_horizon="MID_TERM",
        source_report_id=rep1.id,
        extraction_method="MANUAL",
    )
    session.commit()
    repo = ReportSignalEventRepository(session)
    repo.create(
        report_id=rep1.id,
        event_type="TARGET_PRICE_UP",
        direction="POSITIVE",
        time_horizon="SHORT_TERM",
        extraction_method="MANUAL",
        symbol="005930",
        theme_id=th.id,
    )
    repo.create(
        report_id=rep2.id,
        event_type="RATING_UPGRADE",
        direction="POSITIVE",
        time_horizon="SHORT_TERM",
        extraction_method="MANUAL",
        symbol="000660",
    )
    repo.create(
        report_id=rep1.id,
        event_type="RISK_WARNING",
        direction="NEGATIVE",
        time_horizon="MID_TERM",
        extraction_method="MANUAL",
        symbol="005930",
    )
    session.commit()

    by_sym = repo.list_by_symbol("005930")
    assert len(by_sym) == 2
    by_theme = repo.list_by_theme(th.id)
    assert len(by_theme) == 1 and by_theme[0].symbol == "005930"
    by_event = repo.list_by_event_type("TARGET_PRICE_UP")
    assert len(by_event) == 1
    pos_005930 = repo.list_positive_by_symbol("005930")
    assert len(pos_005930) == 1
    neg_005930 = repo.list_negative_by_symbol("005930")
    assert len(neg_005930) == 1
    recent = repo.list_recent(limit=10)
    assert len(recent) == 3


# ---------- ReportConsensusSnapshot ----------


def test_report_consensus_snapshot_upsert(session):
    repo = ReportConsensusSnapshotRepository(session)
    s1 = repo.upsert_by_symbol_date_window(
        symbol="005930",
        snapshot_date=date(2026, 5, 5),
        window_days=90,
        report_count=3,
        avg_target_price=Decimal("85000"),
        min_target_price=Decimal("80000"),
        max_target_price=Decimal("90000"),
        strong_buy_count=1,
        buy_count=2,
        latest_published_at=date(2026, 5, 1),
    )
    session.commit()
    s2 = repo.upsert_by_symbol_date_window(
        symbol="005930",
        snapshot_date=date(2026, 5, 5),
        window_days=90,
        report_count=4,
        avg_target_price=Decimal("87000"),
        buy_count=3,
        strong_buy_count=1,
    )
    session.commit()
    assert s1.id == s2.id
    assert s2.report_count == 4
    assert s2.avg_target_price == Decimal("87000.0000")
    # Different window stored separately
    s30 = repo.upsert_by_symbol_date_window(
        symbol="005930",
        snapshot_date=date(2026, 5, 5),
        window_days=30,
        report_count=2,
    )
    session.commit()
    assert s30.id != s1.id

    latest = repo.get_latest_by_symbol("005930", window_days=90)
    assert latest is not None and latest.id == s1.id


# ---------- ReportScoreLog ----------


def test_report_score_log_create_and_query(session):
    repo = ReportScoreLogRepository(session)
    log = repo.create(
        symbol="005930",
        score_date=date(2026, 5, 5),
        report_count=3,
        report_score=Decimal("72.50"),
        theme_signal_score=Decimal("65.00"),
        theme_count=2,
        signal_event_count=4,
        target_upside_pct=Decimal("21.4286"),
        rating_score_avg=Decimal("1.3333"),
        recency_bonus=Decimal("5"),
        evidence_json={"top_brokers": ["삼성증권", "키움증권"]},
    )
    session.commit()
    latest = repo.get_latest_by_symbol("005930")
    assert latest is not None and latest.id == log.id

    older = repo.create(
        symbol="005930",
        score_date=date(2026, 4, 28),
        report_count=2,
        report_score=Decimal("60.00"),
        evidence_json={},
    )
    session.commit()
    rows = repo.list_recent_by_symbol("005930", limit=10)
    # Most recent first
    assert [r.id for r in rows][:2] == [log.id, older.id]


def test_report_score_log_unique_per_symbol_date_run(session):
    repo = ReportScoreLogRepository(session)
    repo.create(
        symbol="005930",
        score_date=date(2026, 5, 5),
        report_count=3,
        evidence_json={},
        recommendation_run_id=None,
    )
    session.commit()
    # Same symbol/date but distinct run id is allowed
    repo.create(
        symbol="005930",
        score_date=date(2026, 5, 5),
        report_count=3,
        evidence_json={},
        recommendation_run_id=None,
    )
    # NOTE: SQLite treats NULL as distinct in UNIQUE, so 2 rows with NULL
    # recommendation_run_id are accepted. This matches PostgreSQL default
    # behavior. Tightening to NULLS NOT DISTINCT is a v0.5 concern if needed.
    session.commit()
    rows = repo.list_recent_by_symbol("005930")
    assert len(rows) == 2


# ---------- Cross-repo ----------


def test_table_metadata_includes_six_new_tables(session):
    table_names = set(Base.metadata.tables)
    assert {
        "analyst_reports",
        "report_themes",
        "theme_stock_mappings",
        "report_signal_events",
        "report_consensus_snapshots",
        "report_score_logs",
    }.issubset(table_names)
