"""Integration tests for the v0.5 Phase A first-PR News data layer.

Scope:
  * NewsItemDTO has metadata only — no body / content / full_text fields
  * NewsItem ORM model has no body / content / full_text columns
  * NewsItem.category column was added (Phase A migration)
  * FakeNewsProvider returns deterministic output (tests must not rely on
    real RSS / KIS / external feeds)
  * NewsCollector inserts new rows + skips duplicates by url
  * NewsCollector falls back to provider name when DTO source is None
  * NewsCollector counts truncated long summaries (policy gate)
  * NewsItemRepository: upsert_by_url / list_recent_by_symbol /
    list_recent_by_category

Out of scope (next PR):
  * Scheduler job ``collect_news`` registration (19:00 KST slot)
  * Settings flag ``news_collection_enabled``
  * report-score / news-score formula (v0.5 Phase C)
"""

from __future__ import annotations

from dataclasses import fields as dataclass_fields
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect

from app.data.collectors import NewsCollector, NewsCollectorResult
from app.data.dtos import NewsItemDTO
from app.data.interfaces import NewsProviderInterface
from app.data.repositories import NewsItemRepository
from app.db import Base
from app.db.models import NewsItem
from app.db.session import create_db_engine, create_session_factory
from tests.mocks.fake_news_provider import FakeNewsProvider, _DETERMINISTIC_SAMPLE


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


# ---------- copyright / scope guards ----------

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


def test_news_item_dto_has_no_body_fields():
    """v0.5 정책: 본문 paragraph 저장 금지. DTO 자체에 필드가 없어야 한다."""
    dto_field_names = {f.name for f in dataclass_fields(NewsItemDTO)}
    leaked = dto_field_names & _FORBIDDEN_BODY_FIELDS
    assert leaked == set(), f"NewsItemDTO leaked body fields: {leaked}"


def test_news_item_dto_has_expected_fields():
    """Spec 의 9 + v0.12 Phase A 의 data_source 필드가 모두 존재 + 추가 필드 없음."""
    dto_field_names = {f.name for f in dataclass_fields(NewsItemDTO)}
    expected = {
        "title",
        "url",
        "provider",
        "published_at",
        "symbol",
        "source",
        "category",
        "sentiment_label",
        "summary",
        # v0.12 Phase A — runtime-only provenance tag (PROVIDER/FAKE/CSV/MANUAL)
        "data_source",
    }
    assert dto_field_names == expected


def test_news_item_orm_model_has_no_body_columns():
    """ORM 모델에도 본문 paragraph 컬럼이 없어야 한다."""
    column_names = {c.name for c in inspect(NewsItem).columns}
    leaked = column_names & _FORBIDDEN_BODY_FIELDS
    assert leaked == set(), f"NewsItem ORM leaked body columns: {leaked}"


def test_news_item_orm_model_has_category_column():
    """v0.5 Phase A 마이그레이션: category 컬럼이 존재."""
    column_names = {c.name for c in inspect(NewsItem).columns}
    assert "category" in column_names


# ---------- FakeNewsProvider determinism ----------

def test_fake_news_provider_deterministic_output():
    """동일 호출 → 동일 결과. 테스트 외부 의존성 0건."""
    provider_a = FakeNewsProvider()
    provider_b = FakeNewsProvider()
    out_a = provider_a.fetch_recent_news()
    out_b = provider_b.fetch_recent_news()
    assert out_a == out_b
    # Default sample 은 3건
    assert len(out_a) == len(_DETERMINISTIC_SAMPLE)


def test_fake_news_provider_filters_by_symbols_and_since():
    provider = FakeNewsProvider()
    only_005930 = provider.fetch_recent_news(symbols=["005930"])
    assert len(only_005930) == 1 and only_005930[0].symbol == "005930"

    since_late = datetime(2026, 5, 4, tzinfo=timezone.utc)
    recent = provider.fetch_recent_news(since=since_late)
    assert all(item.published_at >= since_late for item in recent)


def test_fake_news_provider_implements_interface():
    provider = FakeNewsProvider()
    assert isinstance(provider, NewsProviderInterface)


# ---------- NewsCollector flow ----------

def test_news_collector_inserts_three_rows_on_first_run(session):
    collector = NewsCollector(FakeNewsProvider(), NewsItemRepository(session))
    result = collector.collect_recent(limit=10)
    session.commit()
    assert isinstance(result, NewsCollectorResult)
    assert result.fetched == 3
    assert result.inserted == 3
    assert result.skipped_duplicates == 0
    assert result.truncated_summaries == 0
    assert session.query(NewsItem).count() == 3


def test_news_collector_idempotent_re_run_skips_duplicates(session):
    collector = NewsCollector(FakeNewsProvider(), NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    second = collector.collect_recent(limit=10)
    session.commit()
    assert second.fetched == 3
    assert second.inserted == 0
    assert second.skipped_duplicates == 3
    assert session.query(NewsItem).count() == 3


def test_news_collector_persists_category(session):
    collector = NewsCollector(FakeNewsProvider(), NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    repo = NewsItemRepository(session)
    risk = repo.list_recent_by_category("RISK_DISCLOSURE")
    earnings = repo.list_recent_by_category("EARNINGS_REPORT")
    news = repo.list_recent_by_category("NEWS")
    assert len(risk) == 1 and risk[0].category == "RISK_DISCLOSURE"
    assert len(earnings) == 1 and earnings[0].category == "EARNINGS_REPORT"
    assert len(news) == 1 and news[0].category == "NEWS"


def test_news_collector_persists_related_symbols_and_sentiment(session):
    collector = NewsCollector(FakeNewsProvider(), NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    repo = NewsItemRepository(session)
    samsung = repo.list_recent_by_symbol("005930")
    assert len(samsung) == 1
    assert samsung[0].related_symbols == ["005930"]
    assert samsung[0].sentiment == "POSITIVE"


def test_news_collector_falls_back_to_provider_name_when_source_missing(session):
    """NewsItem.source 는 NOT NULL — DTO source=None 일 때 provider 이름으로 채움."""
    dto = NewsItemDTO(
        title="No source provided",
        url="https://example.com/news/no-source",
        provider="fallback_provider",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source=None,
    )
    provider = FakeNewsProvider(items=(dto,))
    collector = NewsCollector(provider, NewsItemRepository(session))
    collector.collect_recent(limit=10)
    session.commit()

    row = session.query(NewsItem).one()
    assert row.source == "fallback_provider"


def test_news_collector_truncation_counter_for_long_summary(session):
    long_dto = NewsItemDTO(
        title="Long summary",
        url="https://example.com/news/long-summary",
        provider="truncation_test",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        summary="가" * 600,  # 500자 초과
    )
    short_dto = NewsItemDTO(
        title="Short summary",
        url="https://example.com/news/short-summary",
        provider="truncation_test",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        summary="짧은 요약",
    )
    provider = FakeNewsProvider(items=(long_dto, short_dto))
    collector = NewsCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(limit=10)
    session.commit()
    assert result.truncated_summaries == 1
    assert result.inserted == 2


def test_news_collector_handles_empty_provider_response(session):
    provider = FakeNewsProvider(items=())
    collector = NewsCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(limit=10)
    session.commit()
    assert result.fetched == 0
    assert result.inserted == 0
    assert session.query(NewsItem).count() == 0


# ---------- NewsItemRepository ----------

def test_repository_upsert_by_url_returns_inserted_flag(session):
    repo = NewsItemRepository(session)
    item, inserted = repo.upsert_by_url(
        url="https://example.com/x",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source="Sample",
        title="t1",
        category="NEWS",
    )
    session.commit()
    assert inserted is True
    assert item.url == "https://example.com/x"

    item2, inserted2 = repo.upsert_by_url(
        url="https://example.com/x",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source="Sample",
        title="t1-changed",  # NOT applied — upsert keeps existing row
        category="OTHER",
    )
    session.commit()
    assert inserted2 is False
    assert item2.id == item.id
    # Existing row's title NOT overwritten on duplicate URL
    assert item2.title == "t1"


def test_repository_upsert_by_url_rejects_empty_url(session):
    repo = NewsItemRepository(session)
    with pytest.raises(ValueError, match="non-empty url"):
        repo.upsert_by_url(
            url="",
            published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
            source="Sample",
            title="t1",
        )


def test_repository_list_recent_by_symbol_filters_json_array(session):
    repo = NewsItemRepository(session)
    repo.upsert_by_url(
        url="u1",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source="A",
        title="multi",
        related_symbols=["005930", "000660"],
    )
    repo.upsert_by_url(
        url="u2",
        published_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        source="A",
        title="solo",
        related_symbols=["000660"],
    )
    repo.upsert_by_url(
        url="u3",
        published_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
        source="A",
        title="none",
    )
    session.commit()

    samsung = repo.list_recent_by_symbol("005930")
    sk = repo.list_recent_by_symbol("000660")
    assert {n.title for n in samsung} == {"multi"}
    assert {n.title for n in sk} == {"multi", "solo"}


def test_repository_list_recent_by_symbol_respects_since(session):
    repo = NewsItemRepository(session)
    repo.upsert_by_url(
        url="recent",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source="A",
        title="recent",
        related_symbols=["005930"],
    )
    repo.upsert_by_url(
        url="old",
        published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        source="A",
        title="old",
        related_symbols=["005930"],
    )
    session.commit()

    cutoff = datetime(2026, 5, 4, tzinfo=timezone.utc) - timedelta(days=7)
    recent = repo.list_recent_by_symbol("005930", since=cutoff)
    assert {n.title for n in recent} == {"recent"}


def test_repository_list_recent_by_category_orders_desc(session):
    repo = NewsItemRepository(session)
    repo.upsert_by_url(
        url="u-newer",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source="A",
        title="newer",
        category="RISK_DISCLOSURE",
    )
    repo.upsert_by_url(
        url="u-older",
        published_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        source="A",
        title="older",
        category="RISK_DISCLOSURE",
    )
    repo.upsert_by_url(
        url="u-other",
        published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        source="A",
        title="other-cat",
        category="NEWS",
    )
    session.commit()

    risk = repo.list_recent_by_category("RISK_DISCLOSURE")
    assert [r.title for r in risk] == ["newer", "older"]
    news = repo.list_recent_by_category("NEWS")
    assert [r.title for r in news] == ["other-cat"]
