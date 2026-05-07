"""Integration tests for v0.13 Phase C — Validation Report read-only API.

Endpoints covered:
    GET /api/validation/report
    GET /api/validation/report/by-strategy
    GET /api/validation/report/by-regime
    GET /api/validation/report/by-sector

Invariants verified:
    - Happy path: correct aggregation over seeded data
    - Empty DB: 200 + zero/empty results
    - Malformed score_delta in evidence_json: gracefully skipped
    - data_source bucketing: PROVIDER/CSV/MANUAL/FAKE/UNKNOWN
    - policy_enabled_count: accurate count
    - Forbidden fields absent from all responses
    - POST/PUT/PATCH/DELETE → 405
    - Zero external network calls (socket monkeypatched)
"""

from __future__ import annotations

import json
import socket
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.db import Base
from app.db.models import BacktestResult, BacktestRun, Stock
from app.db.session import create_session_factory, get_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(session):
    from app.main import app

    def override_session():
        yield session

    def override_settings():
        return Settings(
            app_env="test",
            app_name="stock_ai_platform",
            timezone="Asia/Seoul",
            log_level="INFO",
            telegram_enabled=False,
            telegram_bot_token="abcd1234efgh5678",
            telegram_chat_id="123456789012",
            telegram_api_base_url="https://mock-telegram.local",
            telegram_timeout_seconds=5,
            kis_app_key="kkkk1111kkkk2222",
            kis_app_secret="ssss3333ssss4444",
            kis_account_no="9876543210",
            kis_account_product_code="01",
            kis_use_paper=True,
            scheduler_enabled=False,
            feature_real_order_execution=False,
            feature_full_auto=False,
            feature_paper_trading=False,
            feature_backtest=False,
            feature_custom_ai_training=False,
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

_RUN_DATE = date(2026, 5, 7)
_START = date(2026, 1, 1)
_END = date(2026, 4, 30)


def _seed_run(
    session,
    *,
    strategy_name: str = "TopGradeStrategy",
    strategy_version: str = "v1.0.0",
    signal_count: int = 10,
    buy_count: int = 4,
    pass_count: int = 5,
    avoid_count: int = 1,
    win_rate_5d: Decimal | None = Decimal("0.7500"),
    avg_return_5d: Decimal | None = Decimal("0.0300"),
    max_drawdown: Decimal | None = Decimal("-0.0500"),
    status: str = "SUCCESS",
) -> BacktestRun:
    run = BacktestRun(
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        run_date=_RUN_DATE,
        start_date=_START,
        end_date=_END,
        signal_count=signal_count,
        buy_count=buy_count,
        pass_count=pass_count,
        avoid_count=avoid_count,
        win_rate_5d=win_rate_5d,
        avg_return_5d=avg_return_5d,
        max_drawdown=max_drawdown,
        status=status,
        config_json={},
        summary_json={},
    )
    session.add(run)
    session.flush()
    return run


def _seed_result(
    session,
    run: BacktestRun,
    *,
    symbol: str = "005930",
    signal_action: str = "BUY",
    return_5d: Decimal | None = Decimal("0.0500"),
    regime: str | None = "BULL",
    cost_adjusted_return_5d: Decimal | None = None,
    evidence_json: dict | None = None,
) -> BacktestResult:
    res = BacktestResult(
        backtest_run_id=run.id,
        symbol=symbol,
        signal_action=signal_action,
        return_5d=return_5d,
        regime=regime,
        cost_adjusted_return_5d=cost_adjusted_return_5d,
        evidence_json=evidence_json,
    )
    session.add(res)
    session.flush()
    return res


def _seed_stock(session, *, symbol: str, sector: str | None = "IT") -> Stock:
    stock = Stock(
        market="KOSPI",
        symbol=symbol,
        name=f"TestCo-{symbol}",
        sector=sector,
        is_active=True,
    )
    session.add(stock)
    session.flush()
    return stock


def _make_score_delta(
    *,
    policy_enabled: bool = True,
    delta: str = "-8.0000",
    components: list | None = None,
) -> dict:
    return {
        "score_delta": {
            "policy_enabled": policy_enabled,
            "score_before": "80.0000",
            "score_after": "72.0000",
            "delta": delta,
            "components": components or [
                {"name": "news", "data_source": "CSV", "factor": "0.90",
                 "before": "80.0000", "after": "72.0000"},
            ],
        }
    }


# ---------------------------------------------------------------------------
# 1. GET /api/validation/report — happy path
# ---------------------------------------------------------------------------


def test_report_happy_path(client, session):
    run = _seed_run(session, win_rate_5d=Decimal("0.7500"), avg_return_5d=Decimal("0.0300"))
    _seed_result(session, run, evidence_json=_make_score_delta())

    resp = client.get("/api/validation/report")
    assert resp.status_code == 200
    data = resp.json()

    assert data["run_count"] == 1
    assert data["signal_count"] == 10
    assert data["buy_count"] == 4
    assert data["win_rate_5d"] == "0.7500"
    assert data["avg_return_5d"] == "0.0300"
    assert "generated_at" in data
    assert "score_delta" in data

    sd = data["score_delta"]
    assert sd["total_scored"] == 1
    assert sd["policy_enabled_count"] == 1
    assert sd["negative_delta_count"] == 1
    assert sd["positive_delta_count"] == 0
    assert sd["neutral_delta_count"] == 0
    assert sd["data_source_counts"]["CSV"] == 1


def test_report_empty_db(client, session):
    resp = client.get("/api/validation/report")
    assert resp.status_code == 200
    data = resp.json()

    assert data["run_count"] == 0
    assert data["signal_count"] == 0
    assert data["buy_count"] == 0
    assert data["win_rate_5d"] is None
    assert data["avg_return_5d"] is None

    sd = data["score_delta"]
    assert sd["total_scored"] == 0
    assert sd["policy_enabled_count"] == 0
    assert sd["avg_delta"] is None
    assert sd["data_source_counts"] == {}


# ---------------------------------------------------------------------------
# 2. GET /api/validation/report/by-strategy — happy path
# ---------------------------------------------------------------------------


def test_by_strategy_happy(client, session):
    _seed_run(session, strategy_name="Alpha", win_rate_5d=Decimal("0.6000"), avg_return_5d=Decimal("0.0200"))
    _seed_run(session, strategy_name="Beta", win_rate_5d=Decimal("0.5000"), avg_return_5d=Decimal("0.0100"))

    resp = client.get("/api/validation/report/by-strategy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    names = [item["strategy_name"] for item in data["items"]]
    assert "Alpha" in names
    assert "Beta" in names

    alpha = next(i for i in data["items"] if i["strategy_name"] == "Alpha")
    assert alpha["run_count"] == 1
    assert alpha["win_rate_5d"] == "0.6000"
    assert alpha["avg_return_5d"] == "0.0200"


def test_by_strategy_empty(client, session):
    resp = client.get("/api/validation/report/by-strategy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["items"] == []


def test_by_strategy_cost_adjusted(client, session):
    run = _seed_run(session, strategy_name="CostTest")
    _seed_result(
        session, run, signal_action="BUY",
        cost_adjusted_return_5d=Decimal("0.0250"),
    )

    resp = client.get("/api/validation/report/by-strategy")
    data = resp.json()
    item = data["items"][0]
    assert item["cost_adjusted_avg_return_5d"] == "0.0250"


# ---------------------------------------------------------------------------
# 3. GET /api/validation/report/by-regime — happy path
# ---------------------------------------------------------------------------


def test_by_regime_happy(client, session):
    run = _seed_run(session)
    _seed_result(session, run, signal_action="BUY", regime="BULL", return_5d=Decimal("0.0300"))
    _seed_result(session, run, signal_action="BUY", regime="BULL", return_5d=Decimal("-0.0100"))
    _seed_result(session, run, signal_action="BUY", regime="BEAR", return_5d=Decimal("0.0100"))
    _seed_result(session, run, signal_action="PASS", regime="BULL", return_5d=Decimal("0.0500"))

    resp = client.get("/api/validation/report/by-regime")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2

    regimes = {item["regime"]: item for item in data["items"]}
    assert "BULL" in regimes
    assert "BEAR" in regimes

    bull = regimes["BULL"]
    assert bull["buy_count"] == 2
    # 1 win out of 2 → 0.5000
    assert bull["win_rate_5d"] == "0.5000"

    bear = regimes["BEAR"]
    assert bear["buy_count"] == 1
    assert bear["win_rate_5d"] == "1.0000"


def test_by_regime_empty(client, session):
    resp = client.get("/api/validation/report/by-regime")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["items"] == []


def test_by_regime_none_regime_bucketed_as_unclassified(client, session):
    run = _seed_run(session)
    _seed_result(session, run, signal_action="BUY", regime=None, return_5d=Decimal("0.01"))

    resp = client.get("/api/validation/report/by-regime")
    data = resp.json()
    assert data["count"] == 1
    assert data["items"][0]["regime"] == "UNCLASSIFIED"


# ---------------------------------------------------------------------------
# 4. GET /api/validation/report/by-sector — happy path
# ---------------------------------------------------------------------------


def test_by_sector_happy(client, session):
    _seed_stock(session, symbol="005930", sector="반도체")
    _seed_stock(session, symbol="035720", sector="IT서비스")
    run = _seed_run(session)
    _seed_result(session, run, symbol="005930", signal_action="BUY", return_5d=Decimal("0.0400"))
    _seed_result(session, run, symbol="035720", signal_action="BUY", return_5d=Decimal("-0.0100"))

    resp = client.get("/api/validation/report/by-sector")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    sectors = {item["sector"]: item for item in data["items"]}
    assert "반도체" in sectors
    assert "IT서비스" in sectors
    assert sectors["반도체"]["buy_count"] == 1
    assert sectors["반도체"]["win_rate_5d"] == "1.0000"
    assert sectors["IT서비스"]["win_rate_5d"] == "0.0000"


def test_by_sector_empty(client, session):
    resp = client.get("/api/validation/report/by-sector")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["items"] == []


def test_by_sector_no_stock_row_bucketed_as_unknown(client, session):
    run = _seed_run(session)
    _seed_result(session, run, symbol="UNKNOWN_SYM", signal_action="BUY", return_5d=None)

    resp = client.get("/api/validation/report/by-sector")
    data = resp.json()
    assert data["count"] == 1
    assert data["items"][0]["sector"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# 5. score_delta aggregation edge cases
# ---------------------------------------------------------------------------


def test_malformed_score_delta_skipped(client, session):
    run = _seed_run(session)
    _seed_result(session, run, evidence_json={"score_delta": "not-a-dict"})
    _seed_result(session, run, evidence_json={"score_delta": 42})
    _seed_result(session, run, evidence_json=None)
    _seed_result(session, run, evidence_json={"other_key": {"value": 1}})

    resp = client.get("/api/validation/report")
    data = resp.json()
    assert data["score_delta"]["total_scored"] == 0


def test_malformed_delta_value_skipped(client, session):
    run = _seed_run(session)
    _seed_result(
        session, run,
        evidence_json={"score_delta": {
            "policy_enabled": True,
            "delta": "not-a-number",
            "components": [],
        }},
    )

    resp = client.get("/api/validation/report")
    data = resp.json()
    sd = data["score_delta"]
    assert sd["total_scored"] == 1
    assert sd["policy_enabled_count"] == 1
    assert sd["avg_delta"] is None
    assert sd["positive_delta_count"] == 0


def test_data_source_counts_correct(client, session):
    run = _seed_run(session)
    ev = {
        "score_delta": {
            "policy_enabled": True,
            "delta": "-5.0000",
            "components": [
                {"name": "news", "data_source": "CSV", "factor": "0.90", "before": "50.0000", "after": "45.0000"},
                {"name": "supply", "data_source": "MANUAL", "factor": "0.80", "before": "50.0000", "after": "40.0000"},
                {"name": "ai", "data_source": "PROVIDER", "factor": "1.00", "before": "70.0000", "after": "70.0000"},
                {"name": "fundamental", "data_source": "FAKE", "factor": "1.00", "before": "60.0000", "after": "60.0000"},
                {"name": "extra", "data_source": "CUSTOM_UNKNOWN", "factor": "1.00", "before": "30.0000", "after": "30.0000"},
            ],
        }
    }
    _seed_result(session, run, evidence_json=ev)

    resp = client.get("/api/validation/report")
    counts = resp.json()["score_delta"]["data_source_counts"]
    assert counts["CSV"] == 1
    assert counts["MANUAL"] == 1
    assert counts["PROVIDER"] == 1
    assert counts["FAKE"] == 1
    assert counts["UNKNOWN"] == 1


def test_policy_enabled_count(client, session):
    run = _seed_run(session)
    _seed_result(session, run, evidence_json=_make_score_delta(policy_enabled=True))
    _seed_result(session, run, evidence_json=_make_score_delta(policy_enabled=False))
    _seed_result(session, run, evidence_json=_make_score_delta(policy_enabled=True))

    resp = client.get("/api/validation/report")
    sd = resp.json()["score_delta"]
    assert sd["total_scored"] == 3
    assert sd["policy_enabled_count"] == 2


def test_positive_neutral_negative_delta_counts(client, session):
    run = _seed_run(session)
    _seed_result(session, run, evidence_json=_make_score_delta(delta="5.0000"))
    _seed_result(session, run, evidence_json=_make_score_delta(delta="-3.0000"))
    _seed_result(session, run, evidence_json=_make_score_delta(delta="0.0000"))

    resp = client.get("/api/validation/report")
    sd = resp.json()["score_delta"]
    assert sd["positive_delta_count"] == 1
    assert sd["negative_delta_count"] == 1
    assert sd["neutral_delta_count"] == 1


# ---------------------------------------------------------------------------
# 6. Forbidden fields not exposed
# ---------------------------------------------------------------------------

_FORBIDDEN = [
    "source_file_path", "raw_text", "full_text", "본문", "원문", "전문",
    "api_key", "token", "password", "secret", "order_id", "quantity", "broker",
    "body", "memo",
]


def _check_no_forbidden(body: str) -> None:
    low = body.lower()
    for f in _FORBIDDEN:
        assert f.lower() not in low, f"Forbidden field '{f}' found in response"


def test_forbidden_fields_absent_from_report(client, session):
    run = _seed_run(session)
    _seed_result(session, run, evidence_json=_make_score_delta())
    resp = client.get("/api/validation/report")
    _check_no_forbidden(resp.text)


def test_forbidden_fields_absent_from_by_strategy(client, session):
    _seed_run(session)
    resp = client.get("/api/validation/report/by-strategy")
    _check_no_forbidden(resp.text)


def test_forbidden_fields_absent_from_by_regime(client, session):
    run = _seed_run(session)
    _seed_result(session, run, signal_action="BUY", regime="BULL")
    resp = client.get("/api/validation/report/by-regime")
    _check_no_forbidden(resp.text)


# ---------------------------------------------------------------------------
# 7. POST/PUT/PATCH/DELETE → 405
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", [
    "/api/validation/report",
    "/api/validation/report/by-strategy",
    "/api/validation/report/by-regime",
    "/api/validation/report/by-sector",
])
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_mutation_methods_rejected(client, session, endpoint, method):
    resp = getattr(client, method)(endpoint)
    assert resp.status_code == 405, (
        f"{method.upper()} {endpoint} should be 405, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# 8. Zero external network calls
# ---------------------------------------------------------------------------


def test_no_external_network_calls(monkeypatch, client, session):
    def _no_network(*args, **kwargs):
        raise RuntimeError("network call forbidden in tests")

    monkeypatch.setattr(socket, "getaddrinfo", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)

    _seed_run(session)
    resp = client.get("/api/validation/report")
    assert resp.status_code == 200
