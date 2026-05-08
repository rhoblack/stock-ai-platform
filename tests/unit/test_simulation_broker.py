"""Unit tests for v0.14 Phase B ``app.broker.simulation_broker``.

Scope:
  * ``Settings.paper_trading_enabled`` defaults to False -- ``submit_order``
    refuses cleanly with :class:`PaperTradingDisabledError`.
  * Per-account ``paper_trading_enabled=False`` also refuses cleanly even
    when the global flag is on.
  * Validation: unknown side / order_type, non-positive quantity, empty
    symbol, MARKET-with-price, LIMIT-without-price, unknown account.
  * ``submit_order`` writes a CREATED-state VirtualOrder when enabled.
  * Idempotency: same key on the same account returns the existing order
    with ``deduplicated=True`` and writes no new row.
  * ``cancel_order`` succeeds for CREATED / SUBMITTED, refuses for terminal
    / fill-progressed states (FILLED / PARTIALLY_FILLED / CANCELED /
    REJECTED) -- and works even when the global switch is off.
  * The module imports NO KIS / DART / RSS / requests / httpx / urllib
    code at load time -- we read the source file and grep the import lines.
  * ``execute_pending_orders`` is a NotImplementedError placeholder in
    Phase B (Phase C/D responsibility).

These tests use an in-memory SQLite session per test. No external
network is reachable.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.broker.simulation_broker import (
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
    SubmitResult,
)
from app.config.settings import Settings
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.db.base import Base
from app.db.session import create_session_factory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):  # noqa: ANN001 - SQLA event signature
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _settings(*, enabled: bool) -> Settings:
    return Settings(paper_trading_enabled=enabled)


def _seed_account(
    session,
    *,
    name: str = "default",
    paper_trading_enabled: bool = True,
    initial_cash: Decimal = Decimal("10000000"),
) -> int:
    repo = VirtualAccountRepository(session)
    acc = repo.create(
        name=name,
        initial_cash=initial_cash,
        paper_trading_enabled=paper_trading_enabled,
    )
    session.commit()
    return acc.id


# ---------------------------------------------------------------------------
# Settings default
# ---------------------------------------------------------------------------


def test_paper_trading_disabled_by_default():
    settings = Settings()
    assert settings.paper_trading_enabled is False


# ---------------------------------------------------------------------------
# submit_order -- master switch
# ---------------------------------------------------------------------------


def test_submit_order_refused_when_global_switch_off(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=False))

    with pytest.raises(PaperTradingDisabledError):
        broker.submit_order(
            session,
            account_id=account_id,
            symbol="005930",
            side="BUY",
            quantity=10,
        )

    # No VirtualOrder row was written.
    orders = VirtualOrderRepository(session).list_by_account(account_id)
    assert orders == []


def test_submit_order_refused_when_account_switch_off(session):
    account_id = _seed_account(session, paper_trading_enabled=False)
    broker = SimulationBroker(settings=_settings(enabled=True))

    with pytest.raises(PaperTradingDisabledError):
        broker.submit_order(
            session,
            account_id=account_id,
            symbol="005930",
            side="BUY",
            quantity=10,
        )


# ---------------------------------------------------------------------------
# submit_order -- happy path
# ---------------------------------------------------------------------------


def test_submit_order_writes_created_row(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    result = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    session.commit()

    assert isinstance(result, SubmitResult)
    assert result.deduplicated is False
    order = result.order
    assert order.id is not None
    assert order.account_id == account_id
    assert order.symbol == "005930"
    assert order.side == "BUY"
    assert order.quantity == 10
    assert order.order_type == "MARKET"
    assert order.limit_price is None
    assert order.status == "CREATED"


def test_submit_limit_order_records_price(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    result = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="SELL",
        quantity=5,
        order_type="LIMIT",
        limit_price="71000",
    )
    session.commit()

    assert result.order.order_type == "LIMIT"
    assert result.order.limit_price == Decimal("71000")
    assert result.order.side == "SELL"


# ---------------------------------------------------------------------------
# submit_order -- validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,match",
    [
        (dict(side="HOLD", quantity=1), "side must be"),
        (dict(side="BUY", quantity=0), "quantity must be > 0"),
        (dict(side="BUY", quantity=-1), "quantity must be > 0"),
        (dict(side="BUY", quantity=1, order_type="STOP"), "order_type must be"),
        (
            dict(
                side="BUY",
                quantity=1,
                order_type="LIMIT",
            ),
            "LIMIT order requires limit_price",
        ),
        (
            dict(
                side="BUY",
                quantity=1,
                order_type="MARKET",
                limit_price="100",
            ),
            "MARKET order must not have limit_price",
        ),
    ],
)
def test_submit_order_rejects_invalid_input(session, kwargs, match):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    with pytest.raises(SimulationBrokerError, match=match):
        broker.submit_order(session, account_id=account_id, symbol="005930", **kwargs)


def test_submit_order_rejects_empty_symbol(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    with pytest.raises(SimulationBrokerError, match="symbol must be non-empty"):
        broker.submit_order(
            session, account_id=account_id, symbol="   ", side="BUY", quantity=1
        )


def test_submit_order_rejects_unknown_account(session):
    broker = SimulationBroker(settings=_settings(enabled=True))

    with pytest.raises(SimulationBrokerError, match="not found"):
        broker.submit_order(
            session, account_id=9999, symbol="005930", side="BUY", quantity=1
        )


def test_submit_limit_order_rejects_non_positive_price(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    with pytest.raises(SimulationBrokerError, match="limit_price must be > 0"):
        broker.submit_order(
            session,
            account_id=account_id,
            symbol="005930",
            side="BUY",
            quantity=1,
            order_type="LIMIT",
            limit_price="0",
        )


# ---------------------------------------------------------------------------
# submit_order -- idempotency
# ---------------------------------------------------------------------------


def test_submit_order_dedups_same_idempotency_key(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    first = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="key-1",
    )
    session.commit()

    second = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="key-1",
    )
    session.commit()

    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.order.id == first.order.id

    rows = VirtualOrderRepository(session).list_by_account(account_id)
    assert len(rows) == 1


def test_submit_order_distinct_keys_create_separate_rows(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))

    a = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="key-a",
    )
    b = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        idempotency_key="key-b",
    )
    session.commit()

    assert a.order.id != b.order.id
    assert a.deduplicated is False
    assert b.deduplicated is False


# ---------------------------------------------------------------------------
# cancel_order
# ---------------------------------------------------------------------------


def test_cancel_order_moves_created_to_canceled(session):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))
    order = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    ).order
    session.commit()

    canceled = broker.cancel_order(
        session, order_id=order.id, reason="user request"
    )
    session.commit()

    assert canceled.status == "CANCELED"
    assert canceled.reason == "user request"


def test_cancel_order_works_when_global_switch_flipped_off(session):
    # Simulate: order was created when the switch was on, then operator
    # disabled paper trading but still wants to cancel.
    account_id = _seed_account(session)
    enabled = SimulationBroker(settings=_settings(enabled=True))
    order = enabled.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    ).order
    session.commit()

    disabled = SimulationBroker(settings=_settings(enabled=False))
    canceled = disabled.cancel_order(session, order_id=order.id)
    session.commit()
    assert canceled.status == "CANCELED"


def test_cancel_order_rejects_unknown_id(session):
    broker = SimulationBroker(settings=_settings(enabled=True))
    with pytest.raises(SimulationBrokerError, match="not found"):
        broker.cancel_order(session, order_id=12345)


@pytest.mark.parametrize(
    "terminal_status",
    ["FILLED", "PARTIALLY_FILLED", "CANCELED", "REJECTED"],
)
def test_cancel_order_rejects_terminal_or_fill_progressed_states(
    session, terminal_status
):
    account_id = _seed_account(session)
    broker = SimulationBroker(settings=_settings(enabled=True))
    order = broker.submit_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    ).order
    # Force the order into a non-cancelable state directly via the repo to
    # simulate Phase C fills / explicit reject.
    VirtualOrderRepository(session).update_status(order, new_status=terminal_status)
    session.commit()

    with pytest.raises(SimulationBrokerError, match="cancelable"):
        broker.cancel_order(session, order_id=order.id)


# ---------------------------------------------------------------------------
# execute_pending_orders -- Phase C — exercised in tests/unit/test_pnl_tracker
# and tests/integration/test_virtual_pnl_engine.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Hard guarantees: NO KIS / external HTTP imports in the broker module
# ---------------------------------------------------------------------------


_SIM_BROKER_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "broker"
    / "simulation_broker.py"
)
_FORBIDDEN_IMPORTS = (
    "import requests",
    "from requests",
    "import httpx",
    "from httpx",
    "import urllib",
    "from urllib",
    "from app.data.dart_provider",
    "from app.data.rss_provider",
    "from app.kis",
    "import app.kis",
)


def test_simulation_broker_source_has_no_external_http_imports():
    text = _SIM_BROKER_PATH.read_text(encoding="utf-8")
    for needle in _FORBIDDEN_IMPORTS:
        assert needle not in text, (
            f"SimulationBroker source unexpectedly contains forbidden import "
            f"{needle!r}. Phase B mandates ZERO external HTTP / KIS / DART / RSS "
            f"imports."
        )


def test_simulation_broker_module_has_no_forbidden_dependencies_in_ast():
    """Static AST check: the broker source has no forbidden import nodes.

    This is robust to whatever else the test process happens to have
    imported (pytest itself may pull in many packages). It directly inspects
    the broker module's parse tree.
    """
    import ast

    tree = ast.parse(_SIM_BROKER_PATH.read_text(encoding="utf-8"))
    forbidden_modules = {"requests", "httpx", "urllib", "urllib3"}
    forbidden_prefixes = ("app.kis", "app.data.dart_provider", "app.data.rss_provider")
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name in forbidden_modules or any(
                    name == p or name.startswith(p + ".") for p in forbidden_prefixes
                ):
                    leaks.append(f"import {name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden_modules or any(
                module == p or module.startswith(p + ".") for p in forbidden_prefixes
            ) or module.startswith(tuple(f"{m}." for m in forbidden_modules)):
                leaks.append(f"from {module} import ...")

    assert leaks == [], (
        f"SimulationBroker AST contains forbidden imports: {leaks!r}. "
        f"Phase B mandates ZERO external HTTP / KIS / DART / RSS imports."
    )
