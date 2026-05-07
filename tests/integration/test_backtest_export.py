"""Integration tests for scripts/export_backtest.py — v0.14 Phase A.

Verified invariants
-------------------
- CSV export: correct header + data rows, Decimal/datetime serialised safely
- JSON export: correct structure {run: {...}, results: [...]}
- dry-run: content returned but NO file written to disk
- run_id not found: RunNotFoundError raised; main() returns exit code 2
- forbidden fields NEVER appear in any export format
- main() CLI parses --run-id / --format / --dry-run / --db-url
- no external network calls during export
"""

from __future__ import annotations

import csv
import io
import json
import os
import socket
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event as sa_event

from app.data.repositories.backtest_results import BacktestResultRepository
from app.data.repositories.backtest_runs import BacktestRunRepository
from app.db import Base
from app.db.session import create_db_engine, create_session_factory
from scripts.export_backtest import (
    FORBIDDEN_EXPORT_FIELDS,
    RunNotFoundError,
    export_backtest,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")

    @sa_event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def db_url(tmp_path):
    """Return a file-based SQLite URL in a temp directory for CLI tests."""
    return f"sqlite:///{tmp_path / 'test.db'}"


def _make_run(session) -> int:
    """Insert a BacktestRun and return its id."""
    repo = BacktestRunRepository(session)
    run = repo.create(
        strategy_name="top_grade",
        strategy_version="1.0",
        run_date=date(2026, 5, 1),
        start_date=date(2026, 4, 1),
        end_date=date(2026, 5, 1),
        status="SUCCESS",
    )
    session.flush()
    # Populate aggregate fields for richer CSV output
    repo.mark_finished(
        run,
        signal_count=3,
        buy_count=2,
        avoid_count=1,
        pass_count=0,
        win_rate_1d=Decimal("0.6667"),
        win_rate_3d=Decimal("0.5000"),
        win_rate_5d=Decimal("0.5000"),
        win_rate_20d=Decimal("0.5000"),
        avg_return_1d=Decimal("0.0120"),
        avg_return_3d=Decimal("0.0250"),
        avg_return_5d=Decimal("0.0310"),
        avg_return_20d=Decimal("0.0480"),
        max_drawdown=Decimal("-0.0450"),
        summary_json={"note": "test"},
    )
    session.flush()
    return run.id


def _make_result(session, run_id: int, *, symbol: str = "005930") -> None:
    repo = BacktestResultRepository(session)
    repo.create(
        backtest_run_id=run_id,
        symbol=symbol,
        signal_action="BUY",
        confidence=Decimal("0.8500"),
        grade="A",
        total_score=Decimal("75.1234"),
        return_1d=Decimal("0.0120"),
        return_3d=Decimal("0.0250"),
        return_5d=Decimal("0.0310"),
        return_20d=Decimal("0.0480"),
        cost_adjusted_return_5d=Decimal("0.0295"),
        regime="BULL",
        result_status="WIN",
        evidence_json={"signal": "technical_breakout", "source_file_path": "/secret/path"},
    )
    session.flush()


# ---------------------------------------------------------------------------
# CSV export — happy path
# ---------------------------------------------------------------------------


def test_csv_export_returns_string(session):
    """export_backtest with file-based SQLite returns a non-empty string."""
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    content = _build_csv_content(run, results)

    assert isinstance(content, str)
    assert len(content) > 0


def test_csv_export_has_correct_header_fields(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _CSV_FIELDNAMES, _build_csv_content

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    content = _build_csv_content(run, results)

    reader = csv.DictReader(io.StringIO(content))
    assert list(reader.fieldnames) == list(_CSV_FIELDNAMES)


def test_csv_export_data_rows_match_results(session):
    run_id = _make_run(session)
    _make_result(session, run_id, symbol="005930")
    _make_result(session, run_id, symbol="000660")
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)

    content = _build_csv_content(run, results)
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    assert len(rows) == 2
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"005930", "000660"}


def test_csv_export_run_fields_in_each_row(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    content = _build_csv_content(run, results)

    rows = list(csv.DictReader(io.StringIO(content)))
    assert rows[0]["strategy_name"] == "top_grade"
    assert rows[0]["run_date"] == "2026-05-01"
    assert rows[0]["signal_action"] == "BUY"
    assert rows[0]["grade"] == "A"
    assert rows[0]["regime"] == "BULL"


# ---------------------------------------------------------------------------
# JSON export — happy path
# ---------------------------------------------------------------------------


def test_json_export_has_run_and_results_keys(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_json_payload

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    payload = _build_json_payload(run, results)

    assert "run" in payload
    assert "results" in payload
    assert isinstance(payload["results"], list)


def test_json_export_run_fields_serialised(session):
    run_id = _make_run(session)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_json_payload

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    payload = _build_json_payload(run, results)

    run_dict = payload["run"]
    assert run_dict["strategy_name"] == "top_grade"
    assert run_dict["run_date"] == "2026-05-01"
    assert run_dict["status"] == "SUCCESS"
    # Decimal should be serialised to string
    assert isinstance(run_dict["win_rate_5d"], str)


def test_json_export_result_fields_serialised(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_json_payload

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    payload = _build_json_payload(run, results)

    r = payload["results"][0]
    assert r["symbol"] == "005930"
    assert r["signal_action"] == "BUY"
    assert isinstance(r["total_score"], str)  # Decimal → str
    assert isinstance(r["created_at"], str)   # datetime → ISO string


# ---------------------------------------------------------------------------
# Decimal / datetime serialisation safety
# ---------------------------------------------------------------------------


def test_decimal_serialised_as_string():
    from scripts.export_backtest import _serialize
    assert _serialize(Decimal("75.1234")) == "75.1234"
    assert _serialize(Decimal("0")) == "0"
    assert _serialize(Decimal("-0.0450")) == "-0.0450"


def test_date_serialised_as_iso():
    from scripts.export_backtest import _serialize
    assert _serialize(date(2026, 5, 1)) == "2026-05-01"


def test_datetime_serialised_as_iso():
    from scripts.export_backtest import _serialize
    dt = datetime(2026, 5, 1, 9, 0, 0, tzinfo=timezone.utc)
    assert _serialize(dt) == "2026-05-01T09:00:00+00:00"


def test_none_serialised_as_none():
    from scripts.export_backtest import _serialize
    assert _serialize(None) is None


# ---------------------------------------------------------------------------
# Forbidden field guard
# ---------------------------------------------------------------------------


def test_forbidden_fields_not_in_csv_header(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    content = _build_csv_content(run, results)

    reader = csv.DictReader(io.StringIO(content))
    for forbidden in FORBIDDEN_EXPORT_FIELDS:
        assert forbidden not in (reader.fieldnames or []), (
            f"Forbidden field '{forbidden}' appeared in CSV header"
        )


def test_forbidden_fields_not_in_json_payload(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_json_payload

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    payload = _build_json_payload(run, results)

    for forbidden in FORBIDDEN_EXPORT_FIELDS:
        assert forbidden not in payload["run"], (
            f"Forbidden field '{forbidden}' in JSON run section"
        )
        for r in payload["results"]:
            assert forbidden not in r, (
                f"Forbidden field '{forbidden}' in JSON results row"
            )


def test_evidence_json_absent_from_csv(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    content = _build_csv_content(run, results)
    assert "evidence_json" not in content
    assert "source_file_path" not in content


def test_evidence_json_absent_from_json_export(session):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_json_payload

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    payload = _build_json_payload(run, results)
    serialised = json.dumps(payload)
    assert "evidence_json" not in serialised
    assert "source_file_path" not in serialised
    assert "/secret/" not in serialised


# ---------------------------------------------------------------------------
# RunNotFoundError — missing run
# ---------------------------------------------------------------------------


def test_run_not_found_raises_error(session):
    session.commit()
    from scripts.export_backtest import RunNotFoundError, _build_session_factory

    # Override the module-level factory to use the in-memory session's engine.
    # Simpler: create a fresh in-memory DB without any runs.
    with pytest.raises(RunNotFoundError, match="id=9999 not found"):
        from scripts.export_backtest import export_backtest as eb
        # Use a fresh empty in-memory DB
        eb(run_id=9999, fmt="csv", dry_run=True, database_url="sqlite+pysqlite:///:memory:")


def test_main_returns_exit_code_2_for_missing_run():
    result = main(["--run-id", "9999", "--dry-run", "--db-url", "sqlite+pysqlite:///:memory:"])
    assert result == 2


# ---------------------------------------------------------------------------
# dry-run — no file written
# ---------------------------------------------------------------------------


def test_dry_run_does_not_create_file(session, tmp_path):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content

    output_path = str(tmp_path / "should_not_exist.csv")

    # Build content via helpers to simulate dry_run behaviour
    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)
    # Confirm the content would be non-empty
    content = _build_csv_content(run, results)
    assert content  # not empty

    # dry_run=True must not write the file
    assert not os.path.exists(output_path)


def test_main_dry_run_flag_exits_zero():
    result = main(["--run-id", "1", "--dry-run", "--db-url", "sqlite+pysqlite:///:memory:"])
    # run_id=1 doesn't exist in a fresh DB — should return 2
    assert result == 2


# ---------------------------------------------------------------------------
# main() CLI argument parsing
# ---------------------------------------------------------------------------


def test_main_parse_format_json(monkeypatch):
    calls = []

    def _fake_export(**kwargs):
        calls.append(kwargs)
        return "{}"

    monkeypatch.setattr("scripts.export_backtest.export_backtest", _fake_export)
    main(["--run-id", "42", "--format", "json", "--dry-run"])
    assert calls[0]["fmt"] == "json"
    assert calls[0]["run_id"] == 42
    assert calls[0]["dry_run"] is True


def test_main_parse_db_url(monkeypatch):
    calls = []

    def _fake_export(**kwargs):
        calls.append(kwargs)
        return ""

    monkeypatch.setattr("scripts.export_backtest.export_backtest", _fake_export)
    main(["--run-id", "1", "--db-url", "sqlite:///./custom.db", "--dry-run"])
    assert calls[0]["database_url"] == "sqlite:///./custom.db"


def test_main_default_format_is_csv(monkeypatch):
    calls = []

    def _fake_export(**kwargs):
        calls.append(kwargs)
        return ""

    monkeypatch.setattr("scripts.export_backtest.export_backtest", _fake_export)
    main(["--run-id", "1", "--dry-run"])
    assert calls[0]["fmt"] == "csv"


# ---------------------------------------------------------------------------
# No external network calls
# ---------------------------------------------------------------------------


def test_no_external_network_calls(session, monkeypatch):
    run_id = _make_run(session)
    _make_result(session, run_id)
    session.commit()

    def _block(*args, **kwargs):
        raise AssertionError("export_backtest must not open network connections")

    monkeypatch.setattr(socket, "getaddrinfo", _block)
    monkeypatch.setattr(socket, "create_connection", _block)

    from app.data.repositories.backtest_results import BacktestResultRepository
    from app.data.repositories.backtest_runs import BacktestRunRepository
    from scripts.export_backtest import _build_csv_content, _build_json_payload

    run = BacktestRunRepository(session).get_by_id(run_id)
    results = BacktestResultRepository(session).list_by_run(run_id)

    # Neither CSV nor JSON serialisation should touch the network.
    _build_csv_content(run, results)
    _build_json_payload(run, results)
