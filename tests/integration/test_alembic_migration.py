"""Integration tests for v0.8 Phase A Alembic baseline.

Scope:
  * ``alembic upgrade head`` succeeds against a fresh temporary SQLite DB
  * All 27 v0.7-final tables are created (key tables from each cycle spot-checked)
  * ``alembic_version`` table is present and stamped at the baseline revision
  * ``MigrationContext.compare_metadata`` reports zero drift between the upgraded
    schema and ``app.db.models.Base.metadata`` (the test that fails CI when an
    ORM change ships without a matching revision)
  * ``alembic stamp`` (without DDL) marks an existing DB at the baseline so
    later revisions skip the create_table calls
  * ``alembic downgrade base`` cleanly drops the baseline tables (downgrade is
    development-only; production rollback is via backup restore -- see
    INTEGRATION_RUNBOOK)

Safety:
  * Every test uses a per-test temporary directory (``tmp_path``) so the
    operational SQLite (``stock_ai_kis_check.db``) and any other DB is never
    touched. The Alembic config is pointed at the temp DB via the ``-x url=``
    override mechanism that ``alembic/env.py`` reads first.
  * No external API / KIS / DART / Telegram calls.
  * No POST routes, no auth, no Watchlist -- baseline only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.db import models  # noqa: F401  -- ensure all 27 ORM classes register


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
BASELINE_REVISION = "0001_baseline_v0_7"
# v0.8 Phase C introduces the third revision. ``HEAD_REVISION`` is what
# ``alembic upgrade head`` should land on; new revisions update this constant.
HEAD_REVISION = "0010_real_fills"
EXPECTED_TABLE_COUNT = 41  # 27 baseline + 2 (0002) + 2 (0003) + 1 (0004) + 2 (0005) + 3 (0006) + 1 (0007) + 1 (0008) + 1 (0009) + 1 (0010)
SPOT_CHECK_TABLES = (
    # v0.1 backend
    "stocks",
    "recommendations",
    "recommendation_results",
    # v0.4 analyst & theme
    "analyst_reports",
    "report_themes",
    # v0.5 news / disclosure
    "news_items",
    # v0.6 fundamentals + earnings
    "fundamental_snapshots",
    "earnings_events",
    # v0.7 strategy + backtest
    "backtest_runs",
    "backtest_results",
    # v0.8 Phase B auth foundation
    "users",
    "login_audit_logs",
    # v0.8 Phase C watchlist
    "watchlists",
    "watchlist_items",
    # v0.9 Phase C user preferences
    "user_preferences",
    # v0.14 Phase B virtual trading core
    "virtual_accounts",
    "virtual_orders",
    # v0.14 Phase C virtual trading PnL & fill engine
    "virtual_positions",
    "virtual_fills",
    "virtual_pnl_snapshots",
    # v0.15 Phase B Approval Trading Safety Layer staging table
    "order_candidates",
    # v0.15 Phase D Approval Trading audit trail
    "approval_audit_logs",
    # v0.16 Phase C Real Order ORM skeleton
    "real_orders",
    "real_fills",
)


def _make_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    # ``-x url=...`` is the same override env.py reads via context.get_x_argument.
    cfg.cmd_opts = type("Args", (), {"x": [f"url={database_url}"]})()  # type: ignore[attr-defined]
    return cfg


def _sqlite_url(tmp_path: Path, name: str = "alembic_test.db") -> str:
    db_file = tmp_path / name
    return f"sqlite:///{db_file.as_posix()}"


def test_baseline_revision_exists_with_no_parent() -> None:
    """The 0001 baseline revision must exist and have no parent revision."""
    cfg = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision(BASELINE_REVISION)
    assert rev is not None
    assert rev.down_revision is None, "Baseline must have no parent."


def test_head_revision_matches_constant() -> None:
    """alembic head must equal HEAD_REVISION; new revisions must update the constant."""
    cfg = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)
    heads = list(script.get_heads())
    assert heads == [HEAD_REVISION], (
        f"Expected single head {HEAD_REVISION!r}, got {heads!r}. "
        "When a new revision is added, update HEAD_REVISION in this test."
    )


def test_upgrade_head_creates_all_27_tables(tmp_path: Path) -> None:
    """alembic upgrade head against a fresh DB creates all v0.7-final tables."""
    url = _sqlite_url(tmp_path)
    cfg = _make_config(url)

    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    # alembic_version is alembic's bookkeeping table -- expected on top of the 27.
    assert "alembic_version" in names
    user_tables = names - {"alembic_version"}
    assert len(user_tables) == EXPECTED_TABLE_COUNT, (
        f"Expected {EXPECTED_TABLE_COUNT} ORM tables after baseline upgrade, "
        f"got {len(user_tables)}: {sorted(user_tables)}"
    )

    for required in SPOT_CHECK_TABLES:
        assert required in user_tables, (
            f"Required spot-check table {required!r} missing after upgrade head. "
            f"Present: {sorted(user_tables)}"
        )


def test_alembic_version_table_stamped_at_head(tmp_path: Path) -> None:
    """After upgrade head, alembic_version row must equal the head revision."""
    url = _sqlite_url(tmp_path)
    cfg = _make_config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current = ctx.get_current_revision()
    finally:
        engine.dispose()

    assert current == HEAD_REVISION


def test_compare_metadata_after_upgrade_is_empty(tmp_path: Path) -> None:
    """After upgrade head, compare_metadata against ORM must report zero drift.

    This is the load-bearing assertion for Phase A: it guards against any future
    ORM change shipping without a matching revision. If a column or constraint
    is added/removed in app/db/models.py without a follow-up alembic revision,
    this test will fail in CI.
    """
    url = _sqlite_url(tmp_path)
    cfg = _make_config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={"compare_type": True, "compare_server_default": True},
            )
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], (
        "compare_metadata reports drift between the migration result and the "
        "ORM metadata. Run `alembic revision --autogenerate -m '...'` to create "
        f"the missing revision. Diff: {diff!r}"
    )


def test_stamp_marks_existing_db_at_baseline_without_running_ddl(
    tmp_path: Path,
) -> None:
    """alembic stamp updates alembic_version without re-running create_table.

    Simulates the operational migration path: an existing operational DB
    already has the 27 tables (created via Base.metadata.create_all from an
    earlier release). After backup, the operator runs `alembic stamp
    0001_baseline_v0_7` which records the baseline as applied -- no DDL is
    issued, so the existing data is preserved. Later revisions then layer on
    top via `alembic upgrade head`.
    """
    url = _sqlite_url(tmp_path, name="prebuilt.db")

    # Step 1 -- simulate an "existing" DB seeded by Base.metadata.create_all.
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    pre_tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "alembic_version" not in pre_tables  # not yet alembic-managed

    # Step 2 -- stamp at the baseline revision (no DDL).
    cfg = _make_config(url)
    command.stamp(cfg, BASELINE_REVISION)

    engine = create_engine(url)
    try:
        post_tables = set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current = ctx.get_current_revision()
    finally:
        engine.dispose()

    # All ORM tables remain (no destructive op) + alembic_version was added.
    assert pre_tables.issubset(post_tables)
    assert "alembic_version" in post_tables
    assert current == BASELINE_REVISION


def test_downgrade_base_cleanly_drops_all_baseline_tables(tmp_path: Path) -> None:
    """alembic downgrade base must successfully drop everything the baseline created.

    Downgrade is development-only -- production rollback uses backup restore.
    But the downgrade path must remain green so that contributors can iterate
    on revisions locally.
    """
    url = _sqlite_url(tmp_path)
    cfg = _make_config(url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    # alembic_version is left behind by Alembic on downgrade-to-base; that is
    # expected and harmless. The 27 ORM tables MUST be gone.
    assert names <= {"alembic_version"}, (
        f"Downgrade base did not drop all ORM tables. Remaining: {sorted(names)}"
    )


def test_offline_mode_emits_sql_without_connecting(tmp_path: Path) -> None:
    """``alembic upgrade head --sql`` must produce SQL output without touching a DB.

    Offline mode is used for staging migrations against managed databases where
    the operator wants to review the SQL before applying it. The DB file must
    NOT be created as a side effect.
    """
    db_file = tmp_path / "offline_should_not_exist.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_config(url)

    output_file = tmp_path / "offline.sql"
    cfg.attributes["connection"] = None  # ensure online mode is not picked
    # Capture by temporarily redirecting stdout via Alembic's command API.
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)
    output_file.write_text(buf.getvalue(), encoding="utf-8")

    sql_text = output_file.read_text(encoding="utf-8")
    assert "CREATE TABLE" in sql_text.upper()
    # Spot-check a couple of tables made it into the SQL.
    assert "stocks" in sql_text
    assert "backtest_runs" in sql_text
    # The DB file must not have been created -- offline mode does not connect.
    assert not db_file.exists(), (
        "Offline mode unexpectedly created the database file at "
        f"{db_file}. Offline (--sql) must not open a connection."
    )


@pytest.mark.parametrize(
    "table_name",
    [
        "stocks",
        "recommendations",
        "recommendation_results",
        "analyst_reports",
        "news_items",
        "fundamental_snapshots",
        "earnings_events",
        "backtest_runs",
        "backtest_results",
        # v0.8 Phase B auth foundation
        "users",
        "login_audit_logs",
        # v0.8 Phase C watchlist
        "watchlists",
        "watchlist_items",
        # v0.9 Phase C user preferences
        "user_preferences",
        # v0.14 Phase B virtual trading core
        "virtual_accounts",
        "virtual_orders",
        # v0.14 Phase C virtual trading PnL & fill engine
        "virtual_positions",
        "virtual_fills",
        "virtual_pnl_snapshots",
        # v0.15 Phase B Approval Trading Safety Layer staging table
        "order_candidates",
        # v0.15 Phase D Approval Trading audit trail
        "approval_audit_logs",
    ],
)
def test_spot_check_each_required_table_present(
    tmp_path: Path, table_name: str
) -> None:
    """Per-table guard so a missing table fails with a focused message."""
    url = _sqlite_url(tmp_path)
    cfg = _make_config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert table_name in names, (
        f"Required table {table_name!r} missing after baseline upgrade. "
        f"Present: {sorted(names)}"
    )
