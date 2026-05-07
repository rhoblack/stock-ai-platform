"""ScoreDelta: policy-before/after score difference recorder for v0.13 Phase B.

Computes per-component and aggregate score differences that result from
applying ProviderScorePolicy.  Pure function — no DB access, no HTTP calls,
no ScoringEngine weight changes.

Design invariants:
  - Policy OFF → every component before == after, aggregate delta == "0.0000".
  - FAKE data_source → bypass; component before == after, factor recorded as
    "1.00" (conceptually no attenuation).
  - Unknown / None data_source → factor 1.00 fallback; no attenuation.
  - All Decimal values quantized to 4 decimal places (ROUND_HALF_UP) for
    deterministic JSON output.
  - ``as_dict()`` produces a JSON-serialisable structure with only safe fields
    (no body / secret / raw-text content).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

from app.scoring.provider_policy import DATA_SOURCE_RELIABILITY, ProviderScorePolicy

_QUANT: Final = Decimal("0.0001")
_FACTOR_ONE: Final = Decimal("1.00")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _to_decimal(value: float | Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _effective_factor(*, policy: ProviderScorePolicy, data_source: str | None) -> Decimal:
    """Return the factor that *would* be / was applied, for recording purposes.

    When policy is disabled or data_source is in the bypass set, no factor is
    applied; we record 1.00 to signal "no attenuation".
    """
    if not policy.enabled:
        return _FACTOR_ONE
    if data_source in ("FAKE",) or not data_source:
        return _FACTOR_ONE
    return DATA_SOURCE_RELIABILITY.get(data_source, _FACTOR_ONE)


@dataclass(frozen=True)
class ComponentDelta:
    """Per-component score difference after applying ProviderScorePolicy."""

    name: str
    data_source: str | None
    factor: Decimal
    before: Decimal
    after: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data_source": self.data_source,
            "factor": str(self.factor),
            "before": str(self.before),
            "after": str(self.after),
        }


@dataclass(frozen=True)
class ScoreDeltaResult:
    """Aggregate + per-component score delta from ProviderScorePolicy application.

    ``score_before`` and ``score_after`` are the arithmetic sums of
    ``component.before`` / ``component.after`` across all components (not
    weighted totals — those require ScoringEngine weights not available here).
    Use ``delta`` to see the aggregate raw attenuation.
    """

    policy_enabled: bool
    score_before: Decimal
    score_after: Decimal
    delta: Decimal
    components: list[ComponentDelta] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_enabled": self.policy_enabled,
            "score_before": str(self.score_before),
            "score_after": str(self.score_after),
            "delta": str(self.delta),
            "components": [c.as_dict() for c in self.components],
        }


def compute_score_delta(
    *,
    components: list[tuple[str, Decimal | float | None, str | None]],
    policy: ProviderScorePolicy,
) -> ScoreDeltaResult:
    """Compute per-component and aggregate score delta from policy application.

    Args:
        components: Sequence of ``(name, score, data_source)`` tuples.  Pass
            the producer component scores directly; technical_score is
            typically excluded (it is not a producer output).
        policy:  The configured ``ProviderScorePolicy`` instance.

    Returns:
        ``ScoreDeltaResult`` with ``score_before``, ``score_after``,
        ``delta``, and per-``ComponentDelta`` breakdown.

    Guarantees:
        - Policy OFF → delta == "0.0000" for every component and aggregate.
        - FAKE data_source → bypass; before == after for that component.
        - None / blank data_source → factor 1.00; before == after.
        - All Decimal values are quantized to 4 dp (ROUND_HALF_UP).
    """
    comp_deltas: list[ComponentDelta] = []
    total_before = Decimal("0")
    total_after = Decimal("0")

    for name, raw_score, data_source in components:
        score = _to_decimal(raw_score)
        before = _q(score)
        after_raw = policy.apply_policy(score, data_source)
        after = _q(after_raw)
        factor = _effective_factor(policy=policy, data_source=data_source)

        comp_deltas.append(
            ComponentDelta(
                name=name,
                data_source=data_source,
                factor=factor,
                before=before,
                after=after,
            )
        )
        total_before += before
        total_after += after

    sb = _q(total_before)
    sa = _q(total_after)
    return ScoreDeltaResult(
        policy_enabled=policy.enabled,
        score_before=sb,
        score_after=sa,
        delta=_q(sa - sb),
        components=comp_deltas,
    )
