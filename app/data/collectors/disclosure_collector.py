"""Pull DisclosureItemDTOs from a DisclosureProviderInterface and persist them.

Boundary rules (v0.5 Phase B):
    * No DART / KRX / external HTTP calls. Provider is injected; default
      ``Settings.disclosure_collection_enabled=False`` means the scheduler
      never even looks for one in production until an operator opts in.
    * Only metadata is persisted (title / url / published_at / category /
      related_symbols). DTO carries an optional summary that the collector
      validates ≤ 500 chars; original disclosure body / paragraph / raw HTML
      are explicitly out of scope and the DTO does not even define such fields.
    * Disclosures are written to the existing ``news_items`` table with their
      classified ``category`` populated (Phase A added the column). v0.5 stays
      with one table for both News and Disclosure metadata; a dedicated
      ``disclosures`` table is a v0.6+ candidate if volume / schema diverges.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.data.dtos import DisclosureItemDTO
from app.data.interfaces import DisclosureProviderInterface
from app.data.repositories.news_items import NewsItemRepository

_SUMMARY_MAX_LEN = 500


# ---------------------------------------------------------------------------
# Classification rules (v0.5 Phase B)
#
# Priority order (top → bottom): RISK > EARNINGS > OWNERSHIP > GOVERNANCE >
# OTHER. RISK is checked first so that mixed-keyword disclosures (e.g. an
# earnings announcement that also references 횡령 / 소송) surface as risk —
# safety > sentiment.
#
# Keywords are stored in lowercase and matched against the lowercased
# concatenation of (title, disclosure_type, summary). Korean characters
# survive ``str.lower()`` unchanged so 한글 / English mixed phrases match
# uniformly.
# ---------------------------------------------------------------------------

RISK_KEYWORDS = (
    "소송", "횡령", "배임", "거래정지", "감사의견", "회생", "파산",
    "lawsuit", "litigation", "fraud", "embezzlement",
)
EARNINGS_KEYWORDS = (
    "실적", "잠정", "영업이익", "당기순이익", "earnings", "guidance",
)
OWNERSHIP_KEYWORDS = (
    "최대주주", "지분", "보유주식", "주식 등의 대량보유", "주식보유",
    "ownership",
)
GOVERNANCE_KEYWORDS = (
    "이사회", "사외이사", "감사위원회", "주주총회", "정관 변경",
    "governance", "board",
)

CATEGORY_RISK = "RISK_DISCLOSURE"
CATEGORY_EARNINGS = "EARNINGS_REPORT"
CATEGORY_OWNERSHIP = "OWNERSHIP_CHANGE"
CATEGORY_GOVERNANCE = "GOVERNANCE"
CATEGORY_OTHER = "OTHER"


def _haystack(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).lower()


def classify_disclosure(
    *,
    title: str,
    disclosure_type: str | None = None,
    summary: str | None = None,
) -> str:
    """Return one of the 5 disclosure categories based on keyword matching.

    Pure function — no DB access, no I/O. Tests cover Korean keywords + English
    keywords + priority order + OTHER fallback.
    """
    haystack = _haystack(title, disclosure_type, summary)
    for kw in RISK_KEYWORDS:
        if kw in haystack:
            return CATEGORY_RISK
    for kw in EARNINGS_KEYWORDS:
        if kw in haystack:
            return CATEGORY_EARNINGS
    for kw in OWNERSHIP_KEYWORDS:
        if kw in haystack:
            return CATEGORY_OWNERSHIP
    for kw in GOVERNANCE_KEYWORDS:
        if kw in haystack:
            return CATEGORY_GOVERNANCE
    return CATEGORY_OTHER


@dataclass(frozen=True)
class DisclosureCollectorResult:
    fetched: int
    inserted: int
    skipped_duplicates: int
    truncated_summaries: int
    classified_counts: dict[str, int] = field(default_factory=dict)


class DisclosureCollector:
    """Fetch disclosure metadata from a provider, classify, and idempotently store.

    The classifier overrides any ``dto.category`` the provider may have set —
    we want a single canonical taxonomy regardless of upstream conventions.
    """

    def __init__(
        self,
        provider: DisclosureProviderInterface,
        repository: NewsItemRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def collect_recent(
        self,
        *,
        symbols: list[str] | None = None,
        since=None,
        limit: int = 50,
    ) -> DisclosureCollectorResult:
        items = self._provider.fetch_recent_disclosures(
            symbols=symbols,
            since=since,
            limit=limit,
        )
        inserted = 0
        skipped = 0
        truncated = 0
        classified: dict[str, int] = {
            CATEGORY_RISK: 0,
            CATEGORY_EARNINGS: 0,
            CATEGORY_OWNERSHIP: 0,
            CATEGORY_GOVERNANCE: 0,
            CATEGORY_OTHER: 0,
        }

        for dto in items:
            category = classify_disclosure(
                title=dto.title,
                disclosure_type=dto.disclosure_type,
                summary=dto.summary,
            )
            if dto.summary is not None and len(dto.summary) > _SUMMARY_MAX_LEN:
                truncated += 1

            related = [dto.symbol] if dto.symbol else None
            # NewsItem.source is non-nullable; fall back to provider name.
            source = dto.provider

            _, was_inserted = self._repository.upsert_by_url(
                url=dto.url,
                published_at=dto.published_at,
                source=source,
                title=dto.title,
                related_symbols=related,
                category=category,
            )
            if was_inserted:
                inserted += 1
                classified[category] += 1
            else:
                skipped += 1

        return DisclosureCollectorResult(
            fetched=len(items),
            inserted=inserted,
            skipped_duplicates=skipped,
            truncated_summaries=truncated,
            classified_counts=classified,
        )


__all__ = [
    "CATEGORY_EARNINGS",
    "CATEGORY_GOVERNANCE",
    "CATEGORY_OTHER",
    "CATEGORY_OWNERSHIP",
    "CATEGORY_RISK",
    "DisclosureCollector",
    "DisclosureCollectorResult",
    "classify_disclosure",
]
