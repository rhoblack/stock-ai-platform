"""Pre-seed helper for run.bat — exits 0 if mock data is already loaded.

Used by run.bat to decide whether to run scripts/seed_mock_data.py.

Exit codes:
  0  Mock data is already loaded (skip seed).
  1  DB is empty / table missing / any error (run seed).

Robustness:
  * Uses ``settings.effective_database_url`` so SQLite / Postgres / etc. all
    work uniformly.
  * Catches every exception and returns 1 — better to attempt seed twice
    than to skip needed seeding due to a probe failure.
  * Tests the ``stocks`` table because it is the v0.1 baseline that
    seed_mock_data.py populates first; a non-empty ``stocks`` reliably
    means seed has already run on this DB.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from sqlalchemy import create_engine, text

        from app.config.settings import get_settings

        settings = get_settings()
        engine = create_engine(settings.effective_database_url)
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM stocks"))
                count = result.scalar() or 0
        finally:
            engine.dispose()
    except Exception:  # noqa: BLE001 — any failure means "seed it again"
        return 1
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
