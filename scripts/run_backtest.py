"""Operator CLI for running v0.7 BacktestEngine against existing recommendations.

Default behaviour is dry-run: build snapshots, evaluate the chosen strategy,
report counts + win-rate + avg-return + missing-horizon counts, then rollback.
Pass ``--commit`` to persist a ``BacktestRun`` + N ``BacktestResult`` rows.

Pass ``--walk-forward`` to run WalkForwardBacktestEngine instead of the plain
engine.  Requires ``--from-date`` and ``--to-date``.  ``--train-window-days``
(default 60) and ``--validate-window-days`` (default 20) control window sizes;
``--gap-days`` (default 0) inserts a gap between IS and OOS windows.

Pass ``--multi`` to run MultiStrategyRunner over all registered strategies (or
a custom subset via ``--strategies``).  Requires ``--from-date`` and
``--to-date``.  Regime and sector breakdowns are included by default; suppress
with ``--no-regime-breakdown`` / ``--no-sector-breakdown``.

This CLI **never** calls KIS / DART / Telegram and **never** places orders. It
only reads from existing tables (``recommendations``, ``recommendation_results``,
``data_snapshots``) and writes (when committed) to the new ``backtest_runs`` /
``backtest_results`` tables.

Examples
--------

    python -m scripts.run_backtest --strategy top_grade
    python -m scripts.run_backtest --strategy high_score --from-date 2026-04-01
    python -m scripts.run_backtest --strategy multi_signal --from-date 2026-04-01 --to-date 2026-05-04 --commit
    python -m scripts.run_backtest --strategy top_grade --db-url sqlite:///./trial.db --limit 50 --commit
    python -m scripts.run_backtest --strategy top_grade --walk-forward --from-date 2025-01-01 --to-date 2026-04-30
    python -m scripts.run_backtest --strategy high_score --walk-forward --from-date 2025-01-01 --to-date 2026-04-30 --train-window-days 90 --validate-window-days 30 --gap-days 5 --commit
    python -m scripts.run_backtest --multi --from-date 2025-01-01 --to-date 2026-04-30
    python -m scripts.run_backtest --multi --strategies top_grade,high_score --from-date 2025-01-01 --to-date 2026-04-30 --commit
    python -m scripts.run_backtest --multi --from-date 2025-01-01 --to-date 2026-04-30 --no-sector-breakdown
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine

from app.backtest.engine import BacktestEngine, BacktestRunSummary
from app.backtest.multi_strategy_runner import MultiStrategyComparison, MultiStrategyRunner
from app.backtest.walk_forward import WalkForwardBacktestEngine, WalkForwardSummary
from app.config.settings import get_settings
from app.db.base import Base
from app.db.session import create_session_factory
from app.strategy.registry import (
    KNOWN_STRATEGIES,
    UnknownStrategyError,
    get_strategy,
)


def _parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {raw!r}; expected YYYY-MM-DD") from exc


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    # --- Common ---
    parser.add_argument(
        "--from-date",
        dest="from_date",
        type=_parse_date,
        default=None,
        help="Inclusive lower bound on RecommendationRun.run_date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        type=_parse_date,
        default=None,
        help="Inclusive upper bound on RecommendationRun.run_date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist BacktestRun rows. Default is dry-run rollback.",
    )
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="SQLAlchemy URL override (default: settings.effective_database_url).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap evaluated recommendations (most recent first). Ignored in walk-forward mode.",
    )

    # --- Single-strategy (plain engine) ---
    parser.add_argument(
        "--strategy",
        choices=KNOWN_STRATEGIES,
        default=None,
        help=f"Strategy name for plain/walk-forward mode (one of: {', '.join(KNOWN_STRATEGIES)}).",
    )

    # --- Walk-forward options ---
    parser.add_argument(
        "--walk-forward",
        dest="walk_forward",
        action="store_true",
        help="Run WalkForwardBacktestEngine instead of plain BacktestEngine.",
    )
    parser.add_argument(
        "--train-window-days",
        dest="train_window_days",
        type=int,
        default=60,
        help="IS window size in calendar days (default: 60). Walk-forward only.",
    )
    parser.add_argument(
        "--validate-window-days",
        dest="validate_window_days",
        type=int,
        default=20,
        help="OOS window size in calendar days (default: 20). Walk-forward only.",
    )
    parser.add_argument(
        "--gap-days",
        dest="gap_days",
        type=int,
        default=0,
        help="Gap in calendar days between IS end and OOS start (default: 0). Walk-forward only.",
    )

    # --- Multi-strategy options ---
    parser.add_argument(
        "--multi",
        action="store_true",
        help="Run MultiStrategyRunner over multiple strategies and compare results.",
    )
    parser.add_argument(
        "--strategies",
        dest="strategies",
        default=None,
        help=(
            "Comma-separated strategy names for --multi mode "
            f"(default: all registered strategies: {','.join(KNOWN_STRATEGIES)})."
        ),
    )
    parser.add_argument(
        "--no-regime-breakdown",
        dest="no_regime_breakdown",
        action="store_true",
        help="Suppress per-regime breakdown in --multi mode.",
    )
    parser.add_argument(
        "--no-sector-breakdown",
        dest="no_sector_breakdown",
        action="store_true",
        help="Suppress per-sector breakdown in --multi mode.",
    )

    return parser.parse_args(argv)


def _build_session_factory(database_url: str | None):
    url = database_url or get_settings().effective_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


# ---------------------------------------------------------------------------
# Runner functions
# ---------------------------------------------------------------------------


def run_backtest(
    *,
    strategy_name: str,
    commit: bool,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int | None = None,
    database_url: str | None = None,
) -> BacktestRunSummary:
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        strategy = get_strategy(strategy_name)
        engine = BacktestEngine(session)
        summary = engine.run(
            strategy=strategy,
            start_date=from_date,
            end_date=to_date,
            limit=limit,
            dry_run=not commit,
        )
        if commit:
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()
    return summary


def run_walk_forward_backtest(
    *,
    strategy_name: str,
    commit: bool,
    from_date: date,
    to_date: date,
    train_window_days: int = 60,
    validate_window_days: int = 20,
    gap_days: int = 0,
    database_url: str | None = None,
) -> WalkForwardSummary:
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        strategy = get_strategy(strategy_name)
        engine = WalkForwardBacktestEngine(
            session,
            train_window_days=train_window_days,
            validate_window_days=validate_window_days,
            gap_days=gap_days,
        )
        summary = engine.run(
            strategy=strategy,
            start_date=from_date,
            end_date=to_date,
            dry_run=not commit,
        )
        if commit:
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()
    return summary


def run_multi_strategy_backtest(
    *,
    strategy_names: list[str],
    commit: bool,
    from_date: date,
    to_date: date,
    limit: int | None = None,
    with_regime_breakdown: bool = True,
    with_sector_breakdown: bool = True,
    database_url: str | None = None,
) -> MultiStrategyComparison:
    factory = _build_session_factory(database_url)
    session = factory()
    try:
        strategies = [get_strategy(name) for name in strategy_names]
        runner = MultiStrategyRunner(
            session,
            with_regime_breakdown=with_regime_breakdown,
            with_sector_breakdown=with_sector_breakdown,
        )
        comparison = runner.run(
            strategies=strategies,
            start_date=from_date,
            end_date=to_date,
            limit=limit,
            dry_run=not commit,
        )
        if commit:
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()
    return comparison


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------


def _print_summary(summary: BacktestRunSummary, *, commit: bool) -> None:
    mode = "COMMIT (DB persisted)" if commit else "DRY-RUN (no DB writes)"
    print(f"Backtest - {mode}")
    print(f"  strategy_name                 : {summary.strategy_name}")
    print(f"  strategy_version              : {summary.strategy_version}")
    print(f"  run_date                      : {summary.run_date}")
    print(f"  start_date                    : {summary.start_date}")
    print(f"  end_date                      : {summary.end_date}")
    print(f"  evaluated_recommendation_count: {summary.evaluated_recommendation_count}")
    print(f"  signal_count                  : {summary.signal_count}")
    print(f"  buy_count                     : {summary.buy_count}")
    print(f"  pass_count                    : {summary.pass_count}")
    print(f"  avoid_count                   : {summary.avoid_count}")
    for horizon in (1, 3, 5, 20):
        wr = getattr(summary, f"win_rate_{horizon}d")
        ar = getattr(summary, f"avg_return_{horizon}d")
        print(
            f"  {horizon:>3}d                          : "
            f"win_rate={_fmt(wr)}  avg_return={_fmt(ar)}",
        )
    print(f"  max_drawdown                  : {_fmt(summary.max_drawdown)}")
    print(f"  cost_model_version            : {summary.cost_model_version}")
    print(f"  total_cost (fraction)         : {_fmt(summary.total_cost)}")
    print(f"  cost_adjusted_avg_return_5d   : {_fmt(summary.cost_adjusted_avg_return_5d)}")
    if summary.regime_breakdown:
        print("  regime_breakdown              :")
        for entry in summary.regime_breakdown:
            print(
                f"    - {entry.regime:<14}  buy={entry.buy_count:<3}  "
                f"win_rate_5d={_fmt(entry.win_rate_5d)}  "
                f"avg_return_5d={_fmt(entry.avg_return_5d)}  "
                f"cost_adj={_fmt(entry.cost_adjusted_avg_return_5d)}",
            )
    if summary.missing_result_count_per_horizon:
        for horizon, count in sorted(summary.missing_result_count_per_horizon.items()):
            print(f"  missing_result_count[{horizon}d]      : {count}")
    if summary.backtest_run_id is not None:
        print(f"  backtest_run_id               : {summary.backtest_run_id}")
    print(f"  notes                         : {summary.notes}")


def _print_walk_forward_summary(summary: WalkForwardSummary, *, commit: bool) -> None:
    mode = "COMMIT (DB persisted)" if commit else "DRY-RUN (no DB writes)"
    print(f"Walk-Forward Backtest - {mode}")
    print(f"  strategy_name       : {summary.strategy_name}")
    print(f"  strategy_version    : {summary.strategy_version}")
    print(f"  run_date            : {summary.run_date}")
    print(f"  start_date          : {summary.start_date}")
    print(f"  end_date            : {summary.end_date}")
    print(f"  train_window_days   : {summary.train_window_days}")
    print(f"  validate_window_days: {summary.validate_window_days}")
    print(f"  gap_days            : {summary.gap_days}")
    print(f"  total_folds         : {summary.total_folds}")
    print(f"  avg_oos_win_rate_5d : {_fmt(summary.avg_oos_win_rate_5d)}")
    print(f"  avg_oos_avg_ret_5d  : {_fmt(summary.avg_oos_avg_return_5d)}")
    if summary.fold_results:
        print("  folds               :")
        for fold in summary.fold_results:
            print(
                f"    [{fold.fold_index}] "
                f"IS {fold.train_start}..{fold.train_end}  "
                f"OOS {fold.validate_start}..{fold.validate_end}  "
                f"gap={fold.is_oos_gap}  "
                f"oos_buys={fold.buy_count}  "
                f"oos_wr5d={_fmt(fold.oos_metrics.win_rate_5d)}  "
                f"oos_ar5d={_fmt(fold.oos_metrics.avg_return_5d)}",
            )
    if summary.backtest_run_id is not None:
        print(f"  backtest_run_id     : {summary.backtest_run_id}")


def _print_multi_comparison(comparison: MultiStrategyComparison, *, commit: bool) -> None:
    mode = "COMMIT (DB persisted)" if commit else "DRY-RUN (no DB writes)"
    print(f"Multi-Strategy Comparison - {mode}")
    print(f"  start_date                  : {comparison.start_date}")
    print(f"  end_date                    : {comparison.end_date}")
    print(f"  run_date                    : {comparison.run_date}")
    print(f"  total_strategies            : {comparison.total_strategies}")
    print(f"  best_by_win_rate_5d         : {_fmt(comparison.best_strategy_by_win_rate_5d)}")
    print(f"  best_by_avg_return_5d       : {_fmt(comparison.best_strategy_by_avg_return_5d)}")
    print("  strategies                  :")
    for r in comparison.strategy_results:
        print(
            f"    {r.strategy_name:<22}  sig={r.signal_count:<4}  buy={r.buy_count:<4}  "
            f"wr5d={_fmt(r.win_rate_5d)}  ar5d={_fmt(r.avg_return_5d)}  "
            f"cost_adj={_fmt(r.cost_adjusted_avg_return_5d)}"
        )
        if r.regime_breakdown:
            for entry in r.regime_breakdown:
                print(
                    f"      regime {entry.regime:<14}  buy={entry.buy_count:<3}  "
                    f"wr5d={_fmt(entry.win_rate_5d)}  ar5d={_fmt(entry.avg_return_5d)}"
                )
        if r.sector_breakdown:
            for entry in r.sector_breakdown:
                print(
                    f"      sector {entry.sector:<20}  sig={entry.signal_count:<3}  "
                    f"buy={entry.buy_count:<3}  wr5d={_fmt(entry.win_rate_5d)}"
                )
    if comparison.backtest_run_id is not None:
        print(f"  backtest_run_id             : {comparison.backtest_run_id}")


def _fmt(value: Any) -> str:
    return "—" if value is None else str(value)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.multi:
        if args.from_date is None or args.to_date is None:
            print(
                "error: --multi requires both --from-date and --to-date",
                file=sys.stderr,
            )
            return 2

        raw_strategies = args.strategies
        if raw_strategies:
            strategy_names = [s.strip() for s in raw_strategies.split(",") if s.strip()]
        else:
            strategy_names = list(KNOWN_STRATEGIES)

        try:
            comparison = run_multi_strategy_backtest(
                strategy_names=strategy_names,
                commit=args.commit,
                from_date=args.from_date,
                to_date=args.to_date,
                limit=args.limit,
                with_regime_breakdown=not args.no_regime_breakdown,
                with_sector_breakdown=not args.no_sector_breakdown,
                database_url=args.db_url,
            )
        except UnknownStrategyError as exc:
            print(f"Strategy error: {exc}", file=sys.stderr)
            return 2

        _print_multi_comparison(comparison, commit=args.commit)

    elif args.walk_forward:
        if args.from_date is None or args.to_date is None:
            print(
                "error: --walk-forward requires both --from-date and --to-date",
                file=sys.stderr,
            )
            return 2
        if args.strategy is None:
            print("error: --walk-forward requires --strategy", file=sys.stderr)
            return 2

        try:
            summary = run_walk_forward_backtest(
                strategy_name=args.strategy,
                commit=args.commit,
                from_date=args.from_date,
                to_date=args.to_date,
                train_window_days=args.train_window_days,
                validate_window_days=args.validate_window_days,
                gap_days=args.gap_days,
                database_url=args.db_url,
            )
        except UnknownStrategyError as exc:
            print(f"Strategy error: {exc}", file=sys.stderr)
            return 2

        _print_walk_forward_summary(summary, commit=args.commit)

    else:
        if args.strategy is None:
            print("error: --strategy is required (or use --multi / --walk-forward)", file=sys.stderr)
            return 2

        try:
            summary = run_backtest(
                strategy_name=args.strategy,
                commit=args.commit,
                from_date=args.from_date,
                to_date=args.to_date,
                limit=args.limit,
                database_url=args.db_url,
            )
        except UnknownStrategyError as exc:
            print(f"Strategy error: {exc}", file=sys.stderr)
            return 2

        _print_summary(summary, commit=args.commit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
