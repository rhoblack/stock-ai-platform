"""Integration tests for v0.5 Phase B Disclosure layer.

Scope:
  * DisclosureItemDTO has metadata only — no body / content / full_text fields
  * classify_disclosure: 5 categories + priority ordering + Korean keywords
  * FakeDisclosureProvider determinism + symbol/since filters
  * DisclosureCollector: insert / idempotency / classification persisted to
    news_items.category / summary truncation count
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone

import pytest

from app.data.collectors import (
    CATEGORY_EARNINGS,
    CATEGORY_GOVERNANCE,
    CATEGORY_OTHER,
    CATEGORY_OWNERSHIP,
    CATEGORY_RISK,
    DisclosureCollector,
    DisclosureCollectorResult,
    classify_disclosure,
)
from app.data.dtos import DisclosureItemDTO
from app.data.interfaces import DisclosureProviderInterface
from app.data.repositories import NewsItemRepository
from app.db import Base
from app.db.models import NewsItem
from app.db.session import create_db_engine, create_session_factory
from tests.mocks.fake_disclosure_provider import (
    FakeDisclosureProvider,
    _DETERMINISTIC_SAMPLE,
)


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


# ---------- DTO field guards ----------

_FORBIDDEN_BODY_FIELDS = {
    "body",
    "content",
    "full_text",
    "fulltext",
    "raw_text",
    "rawtext",
    "paragraph_text",
    "paragraphs",
    "article_body",
    "html_body",
    "report_body",
    "original_text",
}


def test_disclosure_dto_has_no_body_fields():
    """v0.5 정책: 공시 본문 paragraph 저장 금지. DTO 자체에 필드가 없어야 한다."""
    dto_field_names = {f.name for f in dataclass_fields(DisclosureItemDTO)}
    leaked = dto_field_names & _FORBIDDEN_BODY_FIELDS
    assert leaked == set(), f"DisclosureItemDTO leaked body fields: {leaked}"


def test_disclosure_dto_has_expected_fields():
    """Spec 의 9 + v0.12 Phase A 의 data_source 필드가 모두 존재 + 추가 필드 없음."""
    dto_field_names = {f.name for f in dataclass_fields(DisclosureItemDTO)}
    expected = {
        "title",
        "url",
        "provider",
        "published_at",
        "symbol",
        "company_name",
        "disclosure_type",
        "category",
        "summary",
        # v0.12 Phase A — runtime-only provenance tag.
        "data_source",
    }
    assert dto_field_names == expected


# ---------- classify_disclosure ----------

@pytest.mark.parametrize(
    "title,expected",
    [
        ("1분기 잠정 실적 발표", CATEGORY_EARNINGS),
        ("영업이익 컨센서스 부합", CATEGORY_EARNINGS),
        ("Q1 earnings guidance update", CATEGORY_EARNINGS),
        ("최대주주 등의 주식 등의 대량보유 변동", CATEGORY_OWNERSHIP),
        ("지분 0.5%p 증가", CATEGORY_OWNERSHIP),
        ("소송 제기 안내", CATEGORY_RISK),
        ("횡령 혐의 발생", CATEGORY_RISK),
        ("배임 의혹 보도", CATEGORY_RISK),
        ("거래정지 및 감사의견 거절", CATEGORY_RISK),
        ("주주총회 — 사외이사 신규 선임", CATEGORY_GOVERNANCE),
        ("이사회 결의 안건", CATEGORY_GOVERNANCE),
        ("회사명 변경 공시", CATEGORY_OTHER),
    ],
)
def test_classify_disclosure_korean_keywords(title, expected):
    assert classify_disclosure(title=title) == expected


def test_classify_disclosure_priority_risk_over_earnings():
    """RISK 키워드가 EARNINGS 와 동시에 나오면 RISK 가 우선 (안전 > 단순 점수)."""
    assert (
        classify_disclosure(title="실적 발표 및 소송 제기")
        == CATEGORY_RISK
    )


def test_classify_disclosure_priority_risk_over_governance():
    assert (
        classify_disclosure(title="이사회 결의 + 횡령 혐의")
        == CATEGORY_RISK
    )


def test_classify_disclosure_uses_disclosure_type_field():
    """title 에 keyword 가 없어도 disclosure_type 에 있으면 매칭."""
    assert (
        classify_disclosure(
            title="Sample disclosure",
            disclosure_type="실적공시",
        )
        == CATEGORY_EARNINGS
    )


def test_classify_disclosure_uses_summary_field():
    assert (
        classify_disclosure(
            title="Sample disclosure",
            summary="감사의견 거절 — 거래정지 통보",
        )
        == CATEGORY_RISK
    )


def test_classify_disclosure_other_fallback():
    assert classify_disclosure(title="company event") == CATEGORY_OTHER


# ---------- FakeDisclosureProvider ----------

def test_fake_disclosure_provider_deterministic():
    a = FakeDisclosureProvider().fetch_recent_disclosures()
    b = FakeDisclosureProvider().fetch_recent_disclosures()
    assert a == b
    assert len(a) == len(_DETERMINISTIC_SAMPLE)


def test_fake_disclosure_provider_filters_by_symbols():
    only_005930 = FakeDisclosureProvider().fetch_recent_disclosures(symbols=["005930"])
    assert len(only_005930) == 1 and only_005930[0].symbol == "005930"


def test_fake_disclosure_provider_filters_by_since():
    cutoff = datetime(2026, 5, 1, tzinfo=timezone.utc)
    recent = FakeDisclosureProvider().fetch_recent_disclosures(since=cutoff)
    assert all(item.published_at >= cutoff for item in recent)


def test_fake_disclosure_provider_implements_interface():
    assert isinstance(FakeDisclosureProvider(), DisclosureProviderInterface)


# ---------- DisclosureCollector flow ----------

def test_collector_inserts_four_rows_with_classified_categories(session):
    collector = DisclosureCollector(FakeDisclosureProvider(), NewsItemRepository(session))
    result = collector.collect_recent(limit=10)
    session.commit()

    assert isinstance(result, DisclosureCollectorResult)
    assert result.fetched == 4
    assert result.inserted == 4
    assert result.skipped_duplicates == 0
    # 1 each of EARNINGS / OWNERSHIP / RISK / GOVERNANCE per FakeDisclosureProvider sample
    assert result.classified_counts[CATEGORY_EARNINGS] == 1
    assert result.classified_counts[CATEGORY_OWNERSHIP] == 1
    assert result.classified_counts[CATEGORY_RISK] == 1
    assert result.classified_counts[CATEGORY_GOVERNANCE] == 1
    assert result.classified_counts[CATEGORY_OTHER] == 0
    # All rows persisted
    assert session.query(NewsItem).count() == 4


def test_collector_idempotent_re_run(session):
    collector = DisclosureCollector(FakeDisclosureProvider(), NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    second = collector.collect_recent(limit=10)
    session.commit()
    assert second.fetched == 4
    assert second.inserted == 0
    assert second.skipped_duplicates == 4
    # classified_counts only counts inserted rows on second pass
    assert sum(second.classified_counts.values()) == 0
    assert session.query(NewsItem).count() == 4


def test_collector_persists_category_classification_to_news_items(session):
    collector = DisclosureCollector(FakeDisclosureProvider(), NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    repo = NewsItemRepository(session)
    risk = repo.list_recent_by_category(CATEGORY_RISK)
    earnings = repo.list_recent_by_category(CATEGORY_EARNINGS)
    governance = repo.list_recent_by_category(CATEGORY_GOVERNANCE)
    ownership = repo.list_recent_by_category(CATEGORY_OWNERSHIP)
    assert len(risk) == 1 and "거래정지" in risk[0].title
    assert len(earnings) == 1 and "실적" in earnings[0].title
    assert len(governance) == 1
    assert len(ownership) == 1


def test_collector_truncation_counter_for_long_summary(session):
    long_dto = DisclosureItemDTO(
        title="긴 공시",
        url="https://example.com/disclosures/long",
        provider="truncation_test",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        summary="가" * 600,
    )
    short_dto = DisclosureItemDTO(
        title="짧은 공시",
        url="https://example.com/disclosures/short",
        provider="truncation_test",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        summary="짧은 요약",
    )
    provider = FakeDisclosureProvider(items=(long_dto, short_dto))
    collector = DisclosureCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(limit=10)
    session.commit()
    assert result.truncated_summaries == 1
    assert result.inserted == 2


def test_collector_handles_empty_provider(session):
    provider = FakeDisclosureProvider(items=())
    collector = DisclosureCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(limit=10)
    session.commit()
    assert result.fetched == 0
    assert result.inserted == 0
    assert sum(result.classified_counts.values()) == 0


def test_collector_persists_related_symbols(session):
    collector = DisclosureCollector(FakeDisclosureProvider(), NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    repo = NewsItemRepository(session)
    samsung = repo.list_recent_by_symbol("005930")
    assert len(samsung) == 1
    assert samsung[0].related_symbols == ["005930"]
    assert samsung[0].category == CATEGORY_EARNINGS
