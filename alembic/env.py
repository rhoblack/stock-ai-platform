"""Alembic environment for the Stock AI Platform.

Resolves the database URL from `app.config.settings.get_settings()` so SQLite
(dev / CI) and PostgreSQL (prod) work without editing `alembic.ini`. Operators
may still override via `alembic -x url=...` for ad-hoc verification against a
disposable database.

`target_metadata` points at `app.db.models.Base.metadata` so all 27 tables
(v0.7-final) are visible to autogenerate. The v0.8 Phase A baseline revision
re-emits those tables verbatim — `compare_metadata` against this metadata is
the test that guards against drift.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import the project metadata. The `prepend_sys_path = .` line in alembic.ini
# means `app.*` resolves regardless of which working directory invokes alembic.
from app.config.settings import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: F401, E402  -- ensure all models register

config = context.config

# Apply alembic.ini's [loggers] section without disabling pre-existing loggers.
# This matters when env.py runs inside pytest: the default
# ``disable_existing_loggers=True`` would silence app.* loggers (e.g.
# app.data.collectors.kis_client) and break downstream caplog assertions in
# the same pytest session. Alembic's own loggers are still configured.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _resolve_database_url() -> str:
    """Resolve the runtime database URL.

    Order:
      1. `-x url=...` CLI override (useful for `alembic -x url=sqlite:///tmp.db ...`)
      2. `sqlalchemy.url` set in `alembic.ini` (left blank by default)
      3. `Settings.effective_database_url` (DATABASE_URL or SQLITE_DATABASE_URL)
    """
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("url"):
        return x_args["url"]
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url:
        return ini_url
    return get_settings().effective_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emits SQL without a live connection)."""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live connection."""
    url = _resolve_database_url()
    config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # SQLite needs batch mode for ALTER operations in future revisions.
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
