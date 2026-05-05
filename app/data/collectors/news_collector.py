"""Pull NewsItemDTOs from a NewsProviderInterface and persist them via repository upsert.

Boundary rules (v0.5 Phase A):
    * No KIS API calls, no Telegram, no order placement.
    * No automatic external fetch — provider is injected; FakeNewsProvider in
      tests + opt-in real providers in v0.5 Phase A second PR (scheduler job)
      will keep ``news_collection_enabled=False`` as the default.
    * Only metadata is persisted. ``NewsItemDTO.summary`` may carry a short
      synopsis, but full article body / paragraph / raw HTML are explicitly
      out of scope and the DTO does not even define those fields. The
      integration test guards against future regressions.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.data.dtos import NewsItemDTO
from app.data.interfaces import NewsProviderInterface
from app.data.repositories.news_items import NewsItemRepository

# Per v0.5 PROJECT_STATUS.md §0 정책: summary 는 짧은 텍스트만 허용. 길이를
# 초과한 입력은 truncate 하고 result 카운터로 추적한다 (operator 가
# import 이후 짧게 다듬을 수 있도록).
_SUMMARY_MAX_LEN = 500


@dataclass(frozen=True)
class NewsCollectorResult:
    fetched: int
    inserted: int
    skipped_duplicates: int
    truncated_summaries: int


class NewsCollector:
    """Fetch news metadata from a provider and idempotently store it.

    The collector intentionally has zero scoring / classification logic —
    that lives in :mod:`app.analysis.score_producers` (Phase C). Phase A's
    role is just data plumbing.
    """

    def __init__(
        self,
        provider: NewsProviderInterface,
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
    ) -> NewsCollectorResult:
        items = self._provider.fetch_recent_news(
            symbols=symbols,
            since=since,
            limit=limit,
        )
        inserted = 0
        skipped = 0
        truncated = 0

        for dto in items:
            # source falls back to provider name when the upstream source is
            # unknown; NewsItem.source is non-nullable in the DB.
            source = dto.source or dto.provider

            related = [dto.symbol] if dto.symbol else None

            # summary length policy — truncate, never reject. The DTO is
            # immutable so the truncation count is tracked but the truncated
            # summary itself is dropped (no summary column on NewsItem yet —
            # v0.6+ may add one).
            if dto.summary is not None and len(dto.summary) > _SUMMARY_MAX_LEN:
                truncated += 1

            _, was_inserted = self._repository.upsert_by_url(
                url=dto.url,
                published_at=dto.published_at,
                source=source,
                title=dto.title,
                related_symbols=related,
                sentiment=dto.sentiment_label,
                category=dto.category,
            )
            if was_inserted:
                inserted += 1
            else:
                skipped += 1

        return NewsCollectorResult(
            fetched=len(items),
            inserted=inserted,
            skipped_duplicates=skipped,
            truncated_summaries=truncated,
        )


__all__ = [
    "NewsCollector",
    "NewsCollectorResult",
]
