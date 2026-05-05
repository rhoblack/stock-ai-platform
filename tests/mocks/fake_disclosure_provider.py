"""In-memory deterministic DisclosureProviderInterface for v0.5 Phase B tests.

Mirrors :class:`tests.mocks.fake_news_provider.FakeNewsProvider` — frozen list
of :class:`DisclosureItemDTO` rows plus simple ``symbols`` / ``since`` /
``limit`` filtering. No DART / KRX / external HTTP. The default sample exercises
all 5 classification buckets (EARNINGS / OWNERSHIP / RISK / GOVERNANCE / OTHER).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.data.dtos import DisclosureItemDTO
from app.data.interfaces import DisclosureProviderInterface


_DETERMINISTIC_SAMPLE: tuple[DisclosureItemDTO, ...] = (
    DisclosureItemDTO(
        title="삼성전자 2026년 1분기 잠정 실적 발표",
        url="https://example.com/disclosures/005930-earnings-2026Q1",
        provider="fake_disclosure",
        published_at=datetime(2026, 4, 30, 16, 0, tzinfo=timezone.utc),
        symbol="005930",
        company_name="삼성전자",
        disclosure_type="실적공시",
        summary="2026년 1분기 영업이익 잠정 집계 (sample data)",
    ),
    DisclosureItemDTO(
        title="SK하이닉스 최대주주 등의 주식 등의 대량보유 변동",
        url="https://example.com/disclosures/000660-ownership-2026-04-25",
        provider="fake_disclosure",
        published_at=datetime(2026, 4, 25, 9, 30, tzinfo=timezone.utc),
        symbol="000660",
        company_name="SK하이닉스",
        disclosure_type="대량보유변동",
        summary="최대주주 지분 0.3%p 증가 (sample data)",
    ),
    DisclosureItemDTO(
        title="A사, 거래정지 및 감사의견 거절",
        url="https://example.com/disclosures/100000-trading-halt-2026-05-02",
        provider="fake_disclosure",
        published_at=datetime(2026, 5, 2, 8, 5, tzinfo=timezone.utc),
        symbol="100000",
        company_name="A사",
        disclosure_type="거래정지",
        summary="감사의견 거절로 거래정지 (sample data)",
    ),
    DisclosureItemDTO(
        title="B사 정기 주주총회 및 사외이사 선임 안건",
        url="https://example.com/disclosures/200000-governance-2026-04-20",
        provider="fake_disclosure",
        published_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        symbol="200000",
        company_name="B사",
        disclosure_type="주주총회",
        summary="이사회 결의 — 사외이사 신규 선임 (sample data)",
    ),
)


class FakeDisclosureProvider(DisclosureProviderInterface):
    """Deterministic fixture-backed provider used by collector / job tests."""

    def __init__(
        self,
        items: tuple[DisclosureItemDTO, ...] | None = None,
    ) -> None:
        self._items = items if items is not None else _DETERMINISTIC_SAMPLE
        self.calls: list[
            tuple[list[str] | None, datetime | None, int]
        ] = []

    def fetch_recent_disclosures(
        self,
        *,
        symbols: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[DisclosureItemDTO]:
        self.calls.append((list(symbols) if symbols else None, since, limit))
        results: list[DisclosureItemDTO] = []
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
    "FakeDisclosureProvider",
]
