"""In-memory deterministic NewsProviderInterface for v0.5 collector tests.

Tests must never reach a real news API (RSS / Naver / DART). This fake holds
a frozen list of :class:`NewsItemDTO` rows and returns subsets based on the
``symbols`` / ``since`` / ``limit`` filters the collector passes through. All
returned DTOs are guaranteed to carry **metadata only** — no body / paragraph
/ full_text fields exist on :class:`NewsItemDTO`, and this fake has no
opportunity to introduce them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.data.dtos import NewsItemDTO
from app.data.interfaces import NewsProviderInterface


_DETERMINISTIC_SAMPLE: tuple[NewsItemDTO, ...] = (
    NewsItemDTO(
        title="삼성전자, HBM 공급 확대 발표",
        url="https://example.com/news/005930-hbm-2026-05-04",
        provider="fake_news",
        published_at=datetime(2026, 5, 4, 9, 30, tzinfo=timezone.utc),
        symbol="005930",
        source="Sample Wire",
        category="NEWS",
        sentiment_label="POSITIVE",
        summary="HBM 메모리 공급 확대로 매출 가시성 개선 (sample data)",
    ),
    NewsItemDTO(
        title="SK하이닉스 1분기 실적 발표",
        url="https://example.com/disclosures/000660-earnings-2026-04-30",
        provider="fake_news",
        published_at=datetime(2026, 4, 30, 16, 0, tzinfo=timezone.utc),
        symbol="000660",
        source="Sample Disclosure",
        category="EARNINGS_REPORT",
        sentiment_label="NEUTRAL",
        summary="2026년 1분기 영업이익 컨센서스 부합 (sample data)",
    ),
    NewsItemDTO(
        title="A사 거래정지 공시",
        url="https://example.com/disclosures/100000-trading-halt-2026-05-02",
        provider="fake_news",
        published_at=datetime(2026, 5, 2, 8, 5, tzinfo=timezone.utc),
        symbol="100000",
        source="Sample Disclosure",
        category="RISK_DISCLOSURE",
        sentiment_label="NEGATIVE",
        summary="감사의견 거절로 거래정지 (sample data)",
    ),
)


class FakeNewsProvider(NewsProviderInterface):
    """Deterministic fixture-backed provider used by collector tests.

    The default constructor exposes the canonical 3-row sample (one per
    category bucket the collector cares about). Callers may pass a custom
    ``items`` tuple for edge-case tests (e.g., empty list, duplicate URLs).
    """

    def __init__(
        self,
        items: tuple[NewsItemDTO, ...] | None = None,
    ) -> None:
        self._items = items if items is not None else _DETERMINISTIC_SAMPLE
        self.calls: list[
            tuple[list[str] | None, datetime | None, int]
        ] = []

    def fetch_recent_news(
        self,
        *,
        symbols: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItemDTO]:
        self.calls.append((list(symbols) if symbols else None, since, limit))
        results: list[NewsItemDTO] = []
        for item in self._items:
            if since is not None and item.published_at < since:
                continue
            if symbols and item.symbol not in symbols:
                continue
            results.append(item)
            if len(results) >= limit:
                break
        return results


__all__ = [
    "FakeNewsProvider",
]
