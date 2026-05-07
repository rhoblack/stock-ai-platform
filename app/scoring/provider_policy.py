"""ProviderScorePolicy: data_source reliability factor for v0.13 Phase A.

Multiplies a raw component score by a reliability factor that reflects
how much the system trusts each data_source provenance label.

Design invariants:
  - ScoringEngine weights are NEVER modified (technical 35% / news 25% /
    supply 15% / fundamental 15% / ai 10% remain unchanged).
  - data_source="FAKE" always bypasses the factor (score returned as-is).
  - Policy OFF (default, PROVIDER_SCORE_POLICY_ENABLED=False) makes every
    call a transparent no-op.
  - Unknown / None / blank data_source falls back to factor 1.00 so that
    new provenance labels added in the future do not silently zero-out scores.
  - No DB access. No HTTP calls. No external I/O.
  - Results are deterministically quantized to 4 decimal places (ROUND_HALF_UP)
    when a factor is applied; raw score is returned unchanged otherwise.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

_QUANT: Final = Decimal("0.0001")
_FALLBACK_FACTOR: Final = Decimal("1.00")

DATA_SOURCE_RELIABILITY: Final[dict[str, Decimal]] = {
    "PROVIDER": Decimal("1.00"),
    "CSV":      Decimal("0.90"),
    "MANUAL":   Decimal("0.80"),
}

_BYPASS_SOURCES: Final = frozenset({"FAKE"})


def _to_decimal(value: float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class ProviderScorePolicy:
    """Apply a data_source reliability factor to a component score.

    When ``enabled=False`` (default) the instance is a transparent pass-through
    for every data_source value, including FAKE.  When ``enabled=True`` the
    reliability factor from DATA_SOURCE_RELIABILITY is multiplied in; sources
    listed in _BYPASS_SOURCES (FAKE) and unknown/blank sources all bypass the
    factor and return the original score.
    """

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def apply_policy(
        self,
        score: float | Decimal,
        data_source: str | None,
    ) -> Decimal:
        """Return score * reliability_factor.

        Bypass (score returned unchanged):
          - Policy disabled (``enabled=False``).
          - ``data_source`` in _BYPASS_SOURCES ("FAKE").

        Factor resolution (policy enabled only):
          - ``None`` / blank string → FALLBACK (1.00, no attenuation).
          - Unrecognised string → FALLBACK (safe forward-compatible default).
          - Known entry → factor from DATA_SOURCE_RELIABILITY.

        The result is quantized to 4 decimal places with ROUND_HALF_UP only
        when a factor multiplication is performed.  In bypass paths the exact
        Decimal value of the input is returned without further rounding.
        """
        raw = _to_decimal(score)

        if not self._enabled:
            return raw

        if data_source in _BYPASS_SOURCES:
            return raw

        key = data_source or ""
        factor = DATA_SOURCE_RELIABILITY.get(key, _FALLBACK_FACTOR)
        return (raw * factor).quantize(_QUANT, rounding=ROUND_HALF_UP)
