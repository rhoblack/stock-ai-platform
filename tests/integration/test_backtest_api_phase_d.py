"""Integration tests for v0.12 Phase D — /folds and /comparison read-only API.

Verifies:
  * GET /api/backtest/runs/{id}/folds  — walk-forward data from summary_json
  * GET /api/backtest/runs/{id}/comparison — multi-strategy data from summary_json
  * 404 when run not found
  * Empty response (200) when key absent from summary_json
  * Graceful handling of malformed summary_json entries
  * POST / PUT / PATCH / DELETE return 405
  * Forbidden fields (secret / raw payload / body text) not exposed
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.db import Base
from app.db.models import BacktestRun
from app.db.session import create_session_factory, get_session


# ---------------------------------------------------------------------------
# Fixtures (identical pattern to test_api_routes.py)
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
# DB seeders
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 7, 6, 0, tzinfo=timezone.utc)
_RUN_DATE = date(2026, 5, 7)
_START = date(2026, 1, 1)
_END = date(2026, 4, 30)


def _seed_walk_forward_run(session) -> BacktestRun:
    run = BacktestRun(
        strategy_name="TopGradeStrategy",
        strategy_version="v1.0.0",
        run_date=_RUN_DATE,
        start_date=_START,
        end_date=_END,
        signal_count=20,
        buy_count=8,
        pass_count=10,
        avoid_count=2,
        win_rate_5d=Decimal("0.6250"),
        avg_return_5d=Decimal("0.0200"),
        status="SUCCESS",
        config_json={"mode": "walk_forward", "train_window_days": 30, "validate_window_days": 30},
        summary_json={
            "mode": "walk_forward",
            "total_folds": 2,
            "avg_oos_win_rate_5d": "0.6250",
            "avg_oos_avg_return_5d": "0.0200",
            "walk_forward_folds": [
                {
                    "fold_index": 0,
                    "train_start": "2026-01-01",
                    "train_end": "2026-01-30",
                    "validate_start": "2026-01-31",
                    "validate_end": "2026-03-01",
                    "is_oos_gap": 0,
                    "is_signal_count": 5,
                    "is_buy_count": 2,
                    "is_win_rate_5d": "0.5000",
                    "is_avg_return_5d": "0.0100",
                    "oos_signal_count": 5,
                    "oos_buy_count": 2,
                    "oos_win_rate_5d": "0.5000",
                    "oos_avg_return_5d": "0.0100",
                },
                {
                    "fold_index": 1,
                    "train_start": "2026-03-02",
                    "train_end": "2026-03-31",
                    "validate_start": "2026-04-01",
                    "validate_end": "2026-04-30",
                    "is_oos_gap": 0,
                    "is_signal_count": 5,
                    "is_buy_count": 3,
                    "is_win_rate_5d": "0.6667",
                    "is_avg_return_5d": "0.0300",
                    "oos_signal_count": 5,
                    "oos_buy_count": 3,
                    "oos_win_rate_5d": "0.6667",
                    "oos_avg_return_5d": "0.0300",
                },
            ],
            "notes": "BUY signals only.",
        },
    )
    session.add(run)
    session.flush()
    return run


def _seed_multi_strategy_run(session) -> BacktestRun:
    run = BacktestRun(
        strategy_name="MULTI",
        strategy_version="multi",
        run_date=_RUN_DATE,
        start_date=_START,
        end_date=_END,
        signal_count=2,
        buy_count=0,
        pass_count=0,
        avoid_count=0,
        status="SUCCESS",
        config_json={"mode": "multi_strategy_comparison"},
        summary_json={
            "mode": "multi_strategy_comparison",
            "total_strategies": 2,
            "best_strategy_by_win_rate_5d": "TopGradeStrategy",
            "best_strategy_by_avg_return_5d": "TopGradeStrategy",
            "multi_strategy_comparison": [
                {
                    "strategy_name": "TopGradeStrategy",
                    "strategy_version": "v1.0.0",
                    "signal_count": 2,
                    "buy_count": 1,
                    "pass_count": 1,
                    "avoid_count": 0,
                    "win_rate_5d": "1.0000",
                    "avg_return_5d": "0.0500",
                    "cost_adjusted_avg_return_5d": None,
                    "max_drawdown": None,
                    "regime_breakdown": [
                        {
                            "regime": "UNCLASSIFIED",
                            "buy_count": 1,
                            "win_rate_5d": "1.0000",
                            "avg_return_5d": "0.0500",
                            "cost_adjusted_avg_return_5d": None,
                        }
                    ],
                    "sector_breakdown": [
                        {
                            "sector": "IT",
                            "signal_count": 1,
                            "buy_count": 1,
                            "win_rate_5d": "1.0000",
                            "avg_return_5d": "0.0500",
                        },
                        {
                            "sector": "Semiconductor",
                            "signal_count": 1,
                            "buy_count": 0,
                            "win_rate_5d": None,
                            "avg_return_5d": None,
                        },
                    ],
                },
                {
                    "strategy_name": "HighScoreStrategy",
                    "strategy_version": "v1.0.0",
                    "signal_count": 2,
                    "buy_count": 1,
                    "pass_count": 1,
                    "avoid_count": 0,
                    "win_rate_5d": "0.0000",
                    "avg_return_5d": "-0.0300",
                    "cost_adjusted_avg_return_5d": None,
                    "max_drawdown": None,
                    "regime_breakdown": [],
                    "sector_breakdown": [],
                },
            ],
            "notes": "BUY signals only.",
        },
    )
    session.add(run)
    session.flush()
    return run


def _seed_plain_run(session) -> BacktestRun:
    """A standard single-strategy run with no walk_forward / multi_strategy keys."""
    run = BacktestRun(
        strategy_name="HighScoreStrategy",
        strategy_version="v1.0.0",
        run_date=_RUN_DATE,
        start_date=_START,
        end_date=_END,
        signal_count=5,
        buy_count=2,
        pass_count=3,
        avoid_count=0,
        win_rate_5d=Decimal("0.5000"),
        avg_return_5d=Decimal("0.0200"),
        status="SUCCESS",
        config_json={},
        summary_json={"cost_model_version": "constant-v1", "notes": "plain run"},
    )
    session.add(run)
    session.flush()
    return run


# ---------------------------------------------------------------------------
# 1. /folds happy path
# ---------------------------------------------------------------------------


def test_folds_happy_path(client, session):
    """/folds returns correct fold data when summary_json has walk_forward_folds."""
    run = _seed_walk_forward_run(session)
    resp = client.get(f"/api/backtest/runs/{run.id}/folds")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run.id
    assert data["mode"] == "walk_forward"
    assert data["total_folds"] == 2
    assert data["avg_oos_win_rate_5d"] == "0.6250"
    assert data["avg_oos_avg_return_5d"] == "0.0200"
    folds = data["folds"]
    assert len(folds) == 2
    fold0 = folds[0]
    assert fold0["fold_index"] == 0
    assert fold0["train_start"] == "2026-01-01"
    assert fold0["validate_start"] == "2026-01-31"
    assert fold0["oos_win_rate_5d"] == "0.5000"
    assert fold0["is_oos_gap"] == 0
    fold1 = folds[1]
    assert fold1["fold_index"] == 1
    assert fold1["oos_win_rate_5d"] == "0.6667"


# ---------------------------------------------------------------------------
# 2. /folds empty — key absent
# ---------------------------------------------------------------------------


def test_folds_empty_when_no_walk_forward_key(client, session):
    """/folds returns 200 with empty list when run has no walk_forward_folds."""
    run = _seed_plain_run(session)
    resp = client.get(f"/api/backtest/runs/{run.id}/folds")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_folds"] == 0
    assert data["folds"] == []


# ---------------------------------------------------------------------------
# 3. /comparison happy path
# ---------------------------------------------------------------------------


def test_comparison_happy_path(client, session):
    """/comparison returns correct strategy rows from summary_json."""
    run = _seed_multi_strategy_run(session)
    resp = client.get(f"/api/backtest/runs/{run.id}/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run.id
    assert data["mode"] == "multi_strategy_comparison"
    assert data["total_strategies"] == 2
    assert data["best_strategy_by_win_rate_5d"] == "TopGradeStrategy"
    assert data["best_strategy_by_avg_return_5d"] == "TopGradeStrategy"

    strategies = data["strategies"]
    assert len(strategies) == 2

    top = strategies[0]
    assert top["strategy_name"] == "TopGradeStrategy"
    assert top["win_rate_5d"] == "1.0000"
    assert top["avg_return_5d"] == "0.0500"
    assert len(top["regime_breakdown"]) == 1
    assert top["regime_breakdown"][0]["regime"] == "UNCLASSIFIED"
    assert len(top["sector_breakdown"]) == 2
    sector_names = {s["sector"] for s in top["sector_breakdown"]}
    assert "IT" in sector_names
    assert "Semiconductor" in sector_names

    high = strategies[1]
    assert high["strategy_name"] == "HighScoreStrategy"
    assert high["win_rate_5d"] == "0.0000"
    assert high["avg_return_5d"] == "-0.0300"


# ---------------------------------------------------------------------------
# 4. /comparison empty — key absent
# ---------------------------------------------------------------------------


def test_comparison_empty_when_no_multi_key(client, session):
    """/comparison returns 200 with empty strategies list when key is absent."""
    run = _seed_plain_run(session)
    resp = client.get(f"/api/backtest/runs/{run.id}/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_strategies"] == 0
    assert data["strategies"] == []
    assert data["best_strategy_by_win_rate_5d"] is None


# ---------------------------------------------------------------------------
# 5. 404 when run not found
# ---------------------------------------------------------------------------


def test_folds_404_when_run_missing(client, session):
    resp = client.get("/api/backtest/runs/99999/folds")
    assert resp.status_code == 404


def test_comparison_404_when_run_missing(client, session):
    resp = client.get("/api/backtest/runs/99999/comparison")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Malformed summary_json — graceful handling
# ---------------------------------------------------------------------------


def test_folds_skips_non_dict_entries(client, session):
    """Non-dict entries in walk_forward_folds are silently skipped."""
    run = BacktestRun(
        strategy_name="TopGradeStrategy",
        strategy_version="v1.0.0",
        run_date=_RUN_DATE,
        start_date=_START,
        end_date=_END,
        signal_count=0,
        buy_count=0,
        pass_count=0,
        avoid_count=0,
        status="SUCCESS",
        config_json={},
        summary_json={
            "mode": "walk_forward",
            "walk_forward_folds": [
                "this-is-a-string",
                None,
                {
                    "fold_index": 0,
                    "train_start": "2026-01-01",
                    "train_end": "2026-01-30",
                    "validate_start": "2026-01-31",
                    "validate_end": "2026-03-01",
                    "is_oos_gap": 0,
                    "is_signal_count": 0,
                    "is_buy_count": 0,
                    "oos_signal_count": 0,
                    "oos_buy_count": 0,
                },
            ],
        },
    )
    session.add(run)
    session.flush()
    resp = client.get(f"/api/backtest/runs/{run.id}/folds")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_folds"] == 1  # only the valid dict counts


def test_comparison_skips_non_dict_entries(client, session):
    """Non-dict entries in multi_strategy_comparison are silently skipped."""
    run = BacktestRun(
        strategy_name="MULTI",
        strategy_version="multi",
        run_date=_RUN_DATE,
        start_date=_START,
        end_date=_END,
        signal_count=0,
        buy_count=0,
        pass_count=0,
        avoid_count=0,
        status="SUCCESS",
        config_json={},
        summary_json={
            "mode": "multi_strategy_comparison",
            "multi_strategy_comparison": [
                42,
                None,
                {
                    "strategy_name": "TopGradeStrategy",
                    "strategy_version": "v1.0.0",
                    "signal_count": 1,
                    "buy_count": 0,
                    "pass_count": 1,
                    "avoid_count": 0,
                },
            ],
        },
    )
    session.add(run)
    session.flush()
    resp = client.get(f"/api/backtest/runs/{run.id}/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_strategies"] == 1


# ---------------------------------------------------------------------------
# 7. POST / PUT / PATCH / DELETE return 405
# ---------------------------------------------------------------------------


def test_folds_mutating_methods_rejected(client, session):
    run = _seed_plain_run(session)
    for method in ("post", "put", "patch", "delete"):
        resp = getattr(client, method)(f"/api/backtest/runs/{run.id}/folds")
        assert resp.status_code == 405, f"{method.upper()} should be 405, got {resp.status_code}"


def test_comparison_mutating_methods_rejected(client, session):
    run = _seed_plain_run(session)
    for method in ("post", "put", "patch", "delete"):
        resp = getattr(client, method)(f"/api/backtest/runs/{run.id}/comparison")
        assert resp.status_code == 405, f"{method.upper()} should be 405, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 8. Forbidden fields not exposed
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERNS = [
    "source_file_path",
    "raw_text",
    "full_text",
    "본문",
    "원문",
    "전문",
    "api_key",
    "token",
    "password",
    "secret",
    "order_id",
    "quantity",
    "broker",
]


def test_folds_no_forbidden_fields(client, session):
    """The /folds response body must not contain forbidden field names."""
    run = _seed_walk_forward_run(session)
    resp = client.get(f"/api/backtest/runs/{run.id}/folds")
    body = resp.text.lower()
    for pattern in _FORBIDDEN_PATTERNS:
        assert pattern.lower() not in body, f"Forbidden field '{pattern}' found in /folds response"


def test_comparison_no_forbidden_fields(client, session):
    """The /comparison response body must not contain forbidden field names."""
    run = _seed_multi_strategy_run(session)
    resp = client.get(f"/api/backtest/runs/{run.id}/comparison")
    body = resp.text.lower()
    for pattern in _FORBIDDEN_PATTERNS:
        assert pattern.lower() not in body, f"Forbidden field '{pattern}' found in /comparison response"
