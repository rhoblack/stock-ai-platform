"""Integration tests for the v0.4 Phase B `update_report_consensus_snapshots` job.

Covers:
  * No active reports → SUCCESS + data_status=NO_DATA
  * Multiple reports across multiple symbols → consensus per symbol
  * Outside-window reports excluded (report > 90 days old)
  * Re-run is idempotent (same date + window_days → upsert overwrites)
  * `job_runs` row reflects the run (status / result_summary)
  * Non-COMPANY reports (THEME / COMMODITY) excluded from consensus
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.data.repositories import (
    AnalystReportRepository,
    JobRunRepository,
    ReportConsensusSnapshotRepository,
)
from app.db import Base
from app.db.session import create_db_engine, create_session_factory
from app.scheduler.jobs import (
    JOB_FUNCTIONS,
    JOB_NAME_UPDATE_REPORT_CONSENSUS,
    run_job,
    update_report_consensus_snapshots,
)


@pytest.fixture()
def session_factory():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield factory
    Base.metadata.drop_all(engine)


def _read_session(session_factory):
    return session_factory()


def _seed_company_report(
    session,
    *,
    symbol: str,
    broker: str,
    days_ago: int,
    rating: str | None,
    target_price: Decimal | None,
    title_suffix: str = "",
):
    """Create one COMPANY report N days before today."""
    return AnalystReportRepository(session).create(
        broker_name=broker,
        published_at=date.today() - timedelta(days=days_ago),
        title=f"{symbol} {broker} {days_ago}d {title_suffix}",
        report_type="COMPANY",
        extraction_method="MANUAL",
        symbol=symbol,
        normalized_rating=rating,
        target_price=target_price,
    )


# ---------- empty / no-op ----------


def test_no_active_reports_returns_no_data(session_factory):
    s = _read_session(session_factory)
    s.commit()
    s.close()
    result = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )
    assert result.status == "SUCCESS"
    assert result.result_summary["data_status"] == "NO_DATA"
    assert result.result_summary["active_reports"] == 0
    assert result.result_summary["snapshots_upserted"] == 0


# ---------- happy path ----------


def test_consensus_aggregation_across_symbols(session_factory):
    s = _read_session(session_factory)
    # symbol 005930: 3 reports, one BUY/STRONG_BUY/HOLD
    _seed_company_report(s, symbol="005930", broker="A", days_ago=10, rating="BUY", target_price=Decimal("80000"))
    _seed_company_report(s, symbol="005930", broker="B", days_ago=5, rating="STRONG_BUY", target_price=Decimal("90000"))
    _seed_company_report(s, symbol="005930", broker="C", days_ago=2, rating="HOLD", target_price=Decimal("75000"))
    # symbol 000660: 1 report
    _seed_company_report(s, symbol="000660", broker="A", days_ago=7, rating="BUY", target_price=Decimal("180000"))
    s.commit()
    s.close()

    result = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )
    assert result.status == "SUCCESS"
    assert result.result_summary["data_status"] == "SUCCESS"
    assert result.result_summary["active_reports"] == 4
    assert result.result_summary["symbols_processed"] == 2
    assert result.result_summary["snapshots_upserted"] == 2

    s = _read_session(session_factory)
    snap_005930 = ReportConsensusSnapshotRepository(s).get_latest_by_symbol("005930")
    assert snap_005930.report_count == 3
    # avg = (80000 + 90000 + 75000) / 3 = 81666.6666...
    assert snap_005930.avg_target_price > Decimal("81666")
    assert snap_005930.avg_target_price < Decimal("81667")
    assert snap_005930.min_target_price == Decimal("75000.0000")
    assert snap_005930.max_target_price == Decimal("90000.0000")
    assert snap_005930.strong_buy_count == 1
    assert snap_005930.buy_count == 1
    assert snap_005930.hold_count == 1
    assert snap_005930.sell_count == 0

    snap_000660 = ReportConsensusSnapshotRepository(s).get_latest_by_symbol("000660")
    assert snap_000660.report_count == 1
    assert snap_000660.avg_target_price == Decimal("180000.0000")
    s.close()


# ---------- window exclusion ----------


def test_old_reports_excluded_from_window(session_factory):
    s = _read_session(session_factory)
    _seed_company_report(s, symbol="005930", broker="A", days_ago=200, rating="STRONG_SELL", target_price=Decimal("50000"))
    _seed_company_report(s, symbol="005930", broker="B", days_ago=10, rating="BUY", target_price=Decimal("80000"))
    s.commit()
    s.close()

    result = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )
    assert result.result_summary["active_reports"] == 1  # 200d 보고서 제외

    s = _read_session(session_factory)
    snap = ReportConsensusSnapshotRepository(s).get_latest_by_symbol("005930")
    assert snap.report_count == 1
    assert snap.strong_sell_count == 0
    assert snap.buy_count == 1
    s.close()


# ---------- type filter ----------


def test_non_company_reports_excluded(session_factory):
    s = _read_session(session_factory)
    AnalystReportRepository(s).create(
        broker_name="X",
        published_at=date.today() - timedelta(days=5),
        title="HBM theme",
        report_type="THEME",
        extraction_method="MANUAL",
    )
    AnalystReportRepository(s).create(
        broker_name="Y",
        published_at=date.today() - timedelta(days=5),
        title="Cu commodity",
        report_type="COMMODITY",
        extraction_method="MANUAL",
    )
    _seed_company_report(s, symbol="005930", broker="A", days_ago=5, rating="BUY", target_price=Decimal("80000"))
    s.commit()
    s.close()

    result = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )
    assert result.result_summary["active_reports"] == 1  # only the COMPANY row
    assert result.result_summary["symbols_processed"] == 1


# ---------- idempotency ----------


def test_same_day_re_run_overwrites_consensus(session_factory):
    s = _read_session(session_factory)
    _seed_company_report(s, symbol="005930", broker="A", days_ago=5, rating="BUY", target_price=Decimal("80000"))
    s.commit()
    s.close()

    run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )

    # Now add another report and re-run on the same date
    s = _read_session(session_factory)
    _seed_company_report(s, symbol="005930", broker="B", days_ago=3, rating="STRONG_BUY", target_price=Decimal("90000"))
    s.commit()
    s.close()

    run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )

    s = _read_session(session_factory)
    snaps = ReportConsensusSnapshotRepository(s).list_recent()
    # Same (symbol, snapshot_date, window_days) → 1 row only
    assert len(snaps) == 1
    assert snaps[0].report_count == 2
    assert snaps[0].buy_count == 1
    assert snaps[0].strong_buy_count == 1
    s.close()


# ---------- job_runs persistence ----------


def test_job_run_record_includes_consensus_summary(session_factory):
    s = _read_session(session_factory)
    _seed_company_report(s, symbol="005930", broker="A", days_ago=5, rating="BUY", target_price=Decimal("80000"))
    s.commit()
    s.close()

    outcome = run_job(
        session_factory=session_factory,
        job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS,
        fn=update_report_consensus_snapshots,
    )

    s = _read_session(session_factory)
    rows = JobRunRepository(s).list()
    assert len(rows) == 1
    row = rows[0]
    assert row.job_id == outcome.job_run_id
    assert row.job_name == JOB_NAME_UPDATE_REPORT_CONSENSUS
    assert row.status == "SUCCESS"
    assert row.result_summary["phase"] == "v0.4-B"
    assert row.result_summary["snapshots_upserted"] == 1
    s.close()


# ---------- registry sanity ----------


def test_consensus_job_is_registered_in_job_functions():
    assert JOB_NAME_UPDATE_REPORT_CONSENSUS in JOB_FUNCTIONS
    assert JOB_FUNCTIONS[JOB_NAME_UPDATE_REPORT_CONSENSUS] is update_report_consensus_snapshots


def test_consensus_job_is_in_default_schedule():
    from app.scheduler.scheduler import DEFAULT_SCHEDULE

    assert JOB_NAME_UPDATE_REPORT_CONSENSUS in DEFAULT_SCHEDULE
    assert DEFAULT_SCHEDULE[JOB_NAME_UPDATE_REPORT_CONSENSUS] == (6, 30)
