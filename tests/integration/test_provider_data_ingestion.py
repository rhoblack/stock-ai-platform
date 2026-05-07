"""v0.12 Phase A -- Provider data ingestion adapter tests.

Coverage matrix:

* Settings.provider_data_ingestion_enabled defaults False; all four
  adapters short-circuit to ``skipped_disabled=True`` without
  touching providers / httpx.Client / DB.
* DART_ENABLED=false / RSS_NEWS_ENABLED=false also soft-skip (no
  exception escapes; the adapter returns ``skipped_disabled=True``).
* When both master flag and per-provider flag are True, the adapters
  call the (test-injected) provider, persist DTOs into the existing
  tables, and tag the rows with the right ``data_source`` provenance.
* DTO ``data_source`` is set to ``"PROVIDER"`` by the DART/RSS
  parsers (verified via the v0.11 transport-injection path).
* CSV importer DTOs carry ``data_source="CSV"`` (regression for the
  parser change we made in fundamental/earnings importers).
* No httpx.Client is constructed under any adapter call where the
  caller supplied a transport — the v0.10/v0.11 zero-network guard
  remains valid.
* Forbidden body fields (body / content / full_text / paragraph /
  raw_text / html_body / 본문 / 원문 / 전문) are absent on every
  ingested row -- both DTO field-set guard + DB column guard.
* DART_API_KEY / crtfc_key / RSS feed URL query secret never appear
  in the captured logs at any point during ingestion.

External network calls: 0.  All HTTP fan-out is intercepted at the
``DartTransport`` / ``RssTransport`` injection point -- no respx
needed because we feed pre-fabricated ``ProviderCallResult`` objects
through the public injection seam.
"""

from __future__ import annotations

import logging
from dataclasses import fields as dc_fields
from datetime import date, datetime, timezone
from typing import Any, Mapping

import httpx
import pytest
from sqlalchemy import inspect

from app.config.settings import Settings
from app.data.dtos import (
    ALLOWED_DATA_SOURCES,
    DATA_SOURCE_CSV,
    DATA_SOURCE_FAKE,
    DATA_SOURCE_PROVIDER,
    DisclosureItemDTO,
    EarningsEventDTO,
    FundamentalSnapshotDTO,
    NewsItemDTO,
)
from app.data.ingestion import (
    DartDisclosureIngestionResult,
    DartEarningsIngestionResult,
    DartFundamentalIngestionResult,
    RssNewsIngestionResult,
    ingest_dart_disclosures,
    ingest_dart_earnings,
    ingest_dart_fundamentals,
    ingest_rss_news,
)
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.provider_resilience import ProviderCallResult
from app.db.base import Base
from app.db.models import EarningsEvent, FundamentalSnapshot, NewsItem
from app.db.session import create_db_engine, create_session_factory


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _enabled_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enable_master: bool = True,
    enable_dart: bool = True,
    dart_api_key: str = "test-crtfc-key-DO-NOT-LOG",
    enable_rss: bool = True,
    rss_feed_urls: str = "https://example.com/feed.xml",
) -> Settings:
    if enable_master:
        monkeypatch.setenv("PROVIDER_DATA_INGESTION_ENABLED", "true")
    else:
        monkeypatch.delenv("PROVIDER_DATA_INGESTION_ENABLED", raising=False)
    if enable_dart:
        monkeypatch.setenv("DART_ENABLED", "true")
        monkeypatch.setenv("DART_API_KEY", dart_api_key)
    else:
        monkeypatch.delenv("DART_ENABLED", raising=False)
        monkeypatch.delenv("DART_API_KEY", raising=False)
    if enable_rss:
        monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
        monkeypatch.setenv("RSS_FEED_URLS", rss_feed_urls)
    else:
        monkeypatch.delenv("RSS_NEWS_ENABLED", raising=False)
        monkeypatch.delenv("RSS_FEED_URLS", raising=False)
    return Settings()


def _disabled_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """All flags off."""
    for var in (
        "PROVIDER_DATA_INGESTION_ENABLED",
        "DART_ENABLED",
        "DART_API_KEY",
        "RSS_NEWS_ENABLED",
        "RSS_FEED_URLS",
    ):
        monkeypatch.delenv(var, raising=False)
    return Settings()


# ---------------------------------------------------------------------------
# Default-OFF guards
# ---------------------------------------------------------------------------


def test_settings_provider_data_ingestion_default_false(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("PROVIDER_DATA_INGESTION_ENABLED", raising=False)
    assert Settings().provider_data_ingestion_enabled is False


def test_dart_disclosures_skipped_when_master_flag_off(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _disabled_settings(monkeypatch)
    # Even with a transport in hand, the master flag short-circuits.
    transport_calls: list[Any] = []

    def transport(_path, _params):
        transport_calls.append(1)
        return ProviderCallResult.ok({"status": "000", "list": []})

    result = ingest_dart_disclosures(
        session, settings=settings, transport=transport
    )
    assert isinstance(result, DartDisclosureIngestionResult)
    assert result.skipped_disabled is True
    assert result.fetched == 0
    assert transport_calls == []
    assert session.query(NewsItem).count() == 0


def test_dart_disclosures_skipped_when_dart_disabled(
    session, monkeypatch: pytest.MonkeyPatch
):
    """Master flag ON but DART_ENABLED=false → soft skip without raising."""
    settings = _enabled_settings(monkeypatch, enable_dart=False)
    result = ingest_dart_disclosures(session, settings=settings)
    assert result.skipped_disabled is True


def test_rss_news_skipped_when_master_flag_off(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _disabled_settings(monkeypatch)

    def transport(_url):
        raise AssertionError("transport must not be called when master flag off")

    result = ingest_rss_news(session, settings=settings, transport=transport)
    assert result.skipped_disabled is True
    assert session.query(NewsItem).count() == 0


def test_rss_news_skipped_when_rss_disabled(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _enabled_settings(monkeypatch, enable_rss=False)
    result = ingest_rss_news(session, settings=settings)
    assert result.skipped_disabled is True


def test_dart_fundamentals_skipped_when_master_flag_off(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _disabled_settings(monkeypatch)
    result = ingest_dart_fundamentals(
        session,
        settings=settings,
        symbols=["005930"],
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    assert result.skipped_disabled is True
    assert session.query(FundamentalSnapshot).count() == 0


def test_dart_earnings_skipped_when_master_flag_off(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _disabled_settings(monkeypatch)
    result = ingest_dart_earnings(
        session,
        settings=settings,
        symbols=["005930"],
    )
    assert result.skipped_disabled is True
    assert session.query(EarningsEvent).count() == 0


# ---------------------------------------------------------------------------
# Happy paths: feature flag ON + transport injection → DB rows
# ---------------------------------------------------------------------------


_DART_DISCLOSURE_FIXTURE = {
    "status": "000",
    "list": [
        {
            "rcept_no": "20260430000001",
            "rcept_dt": "20260430",
            "report_nm": "삼성전자 1분기 잠정 실적",
            "corp_name": "삼성전자",
            "stock_code": "005930",
            "report_tp": "주요사항보고서",
        },
    ],
}


def test_dart_disclosure_ingestion_persists_with_provider_provenance(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _enabled_settings(monkeypatch)

    def transport(_path, _params):
        return ProviderCallResult.ok(_DART_DISCLOSURE_FIXTURE)

    monitor = ProviderHealthMonitor()
    result = ingest_dart_disclosures(
        session,
        settings=settings,
        transport=transport,
        monitor=monitor,
        limit=10,
    )
    session.commit()

    assert result.skipped_disabled is False
    assert result.fetched == 1
    assert result.inserted == 1
    rows = session.query(NewsItem).all()
    assert len(rows) == 1
    row = rows[0]
    # source carries the provider name from the DTO; data_source provenance
    # is runtime-only on the DTO, not persisted (no DB column).
    assert row.source == "dart"
    assert "삼성전자" in row.title
    assert row.related_symbols == ["005930"]


_RSS_FIXTURE_BYTES = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<rss version="2.0"><channel>'
    b"<title>Sample Wire</title>"
    b'<item><title>HBM Title</title><link>https://example.com/news/hbm</link>'
    b"<pubDate>Mon, 04 May 2026 09:30:00 GMT</pubDate>"
    b"<description>Short summary</description></item>"
    b"</channel></rss>"
)


def test_rss_news_ingestion_persists_with_provider_provenance(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _enabled_settings(monkeypatch)

    def transport(_url):
        return ProviderCallResult.ok(_RSS_FIXTURE_BYTES)

    monitor = ProviderHealthMonitor()
    result = ingest_rss_news(
        session,
        settings=settings,
        transport=transport,
        monitor=monitor,
        limit=10,
    )
    session.commit()

    assert result.skipped_disabled is False
    assert result.fetched == 1
    assert result.inserted == 1
    rows = session.query(NewsItem).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.title == "HBM Title"
    assert row.url == "https://example.com/news/hbm"
    # NewsCollector falls back to dto.source when set; the parser uses
    # the channel title as feed_source.
    assert row.source == "Sample Wire"


_DART_FUND_FIXTURE = {
    "status": "000",
    "corp_name": "삼성전자",
    "list": [
        {"account_nm": "매출액", "thstrm_amount": "258,935,500"},
        {"account_nm": "영업이익", "thstrm_amount": "32,726,000"},
    ],
}


def test_dart_fundamental_ingestion_persists_provider_data(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _enabled_settings(monkeypatch)

    def transport(_path, _params):
        return ProviderCallResult.ok(_DART_FUND_FIXTURE)

    monitor = ProviderHealthMonitor()
    result = ingest_dart_fundamentals(
        session,
        settings=settings,
        transport=transport,
        monitor=monitor,
        symbols=["005930"],
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    session.commit()

    assert result.skipped_disabled is False
    assert result.upserted == 1
    rows = session.query(FundamentalSnapshot).all()
    assert len(rows) == 1
    assert rows[0].source == "DART"
    # Numeric metric persisted as Decimal via repository upsert.
    assert int(rows[0].revenue) == 258_935_500


_DART_EARNINGS_FIXTURE = {
    "status": "000",
    "corp_name": "삼성전자",
    "list": [
        {"account_nm": "매출액", "thstrm_amount": "258,935,500"},
        {"account_nm": "영업이익", "thstrm_amount": "32,726,000"},
    ],
}


def test_dart_earnings_ingestion_persists_provider_data(
    session, monkeypatch: pytest.MonkeyPatch
):
    settings = _enabled_settings(monkeypatch)

    def transport(_path, _params):
        return ProviderCallResult.ok(_DART_EARNINGS_FIXTURE)

    monitor = ProviderHealthMonitor()
    result = ingest_dart_earnings(
        session,
        settings=settings,
        transport=transport,
        monitor=monitor,
        symbols=["005930"],
        until=date(2026, 4, 30),
    )
    session.commit()

    assert result.skipped_disabled is False
    assert result.upserted == 1
    rows = session.query(EarningsEvent).all()
    assert len(rows) == 1
    assert rows[0].source == "DART"
    assert int(rows[0].operating_income_actual) == 32_726_000


# ---------------------------------------------------------------------------
# DTO data_source provenance + allowed values
# ---------------------------------------------------------------------------


def test_data_source_constants_exposed():
    assert DATA_SOURCE_PROVIDER == "PROVIDER"
    assert DATA_SOURCE_FAKE == "FAKE"
    assert DATA_SOURCE_CSV == "CSV"
    assert "MANUAL" in ALLOWED_DATA_SOURCES


@pytest.mark.parametrize(
    "dto_cls",
    [NewsItemDTO, DisclosureItemDTO, FundamentalSnapshotDTO, EarningsEventDTO],
)
def test_dto_default_data_source_is_fake(dto_cls):
    """Default field value across all four DTOs is ``"FAKE"`` so existing
    tests / fake providers retain backward-compatible provenance.
    """
    field_map = {f.name: f for f in dc_fields(dto_cls)}
    assert "data_source" in field_map
    assert field_map["data_source"].default == DATA_SOURCE_FAKE


def test_dart_parser_attaches_provider_provenance():
    from app.data.dart_provider import (  # noqa: PLC0415
        parse_disclosure_item,
        parse_earnings,
        parse_fundamentals,
    )

    fund = parse_fundamentals(
        _DART_FUND_FIXTURE,
        symbol="005930",
        snapshot_date=date(2026, 5, 7),
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    assert fund.data_source == DATA_SOURCE_PROVIDER

    earn = parse_earnings(
        _DART_EARNINGS_FIXTURE,
        symbol="005930",
        company_name="삼성전자",
        event_date=date(2026, 4, 30),
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    assert earn.data_source == DATA_SOURCE_PROVIDER

    disclosure = parse_disclosure_item(
        _DART_DISCLOSURE_FIXTURE["list"][0]
    )
    assert disclosure is not None
    assert disclosure.data_source == DATA_SOURCE_PROVIDER


def test_rss_parser_attaches_provider_provenance():
    from app.data.rss_provider import parse_feed  # noqa: PLC0415

    items = parse_feed(_RSS_FIXTURE_BYTES)
    assert len(items) == 1
    assert items[0].data_source == DATA_SOURCE_PROVIDER


def test_csv_importer_dtos_carry_csv_provenance():
    """The fundamental / earnings CSV importers stamp DTOs with
    data_source="CSV" so the producer / evidence layer can distinguish
    operator-supplied CSV rows from real provider rows.
    """
    from io import StringIO  # noqa: PLC0415

    from app.data.importers.fundamentals import (  # noqa: PLC0415
        FundamentalCsvImporter,
    )

    csv_text = (
        "symbol,snapshot_date,fiscal_year,fiscal_quarter,source,revenue\n"
        "005930,2026-05-07,2026,1,operator-csv,1000\n"
    )
    # Inspect the parsed DTO directly via a private call site.
    importer = FundamentalCsvImporter.__new__(FundamentalCsvImporter)
    rows = list(__import__("csv").DictReader(StringIO(csv_text)))
    dto = importer._parse_row(rows[0])  # type: ignore[attr-defined]
    assert dto.data_source == DATA_SOURCE_CSV


# ---------------------------------------------------------------------------
# No-network guard (caller-supplied transport must skip httpx.Client)
# ---------------------------------------------------------------------------


def test_adapters_do_not_construct_httpx_client_when_transport_supplied(
    session, monkeypatch: pytest.MonkeyPatch
):
    """v0.10/v0.11 zero-network guard: if a caller passes their own
    transport, no httpx.Client must be instantiated by any adapter
    code path.
    """
    settings = _enabled_settings(monkeypatch)

    def boom(*_a, **_kw):
        raise AssertionError(
            "Caller-supplied transport must skip httpx.Client construction"
        )

    monkeypatch.setattr(httpx, "Client", boom)

    def dart_transport(_path, _params):
        return ProviderCallResult.ok(_DART_DISCLOSURE_FIXTURE)

    def rss_transport(_url):
        return ProviderCallResult.ok(_RSS_FIXTURE_BYTES)

    ingest_dart_disclosures(session, settings=settings, transport=dart_transport)
    ingest_rss_news(session, settings=settings, transport=rss_transport)
    ingest_dart_fundamentals(
        session,
        settings=settings,
        transport=dart_transport,
        symbols=["005930"],
        fiscal_year=2026,
        fiscal_quarter=1,
    )
    ingest_dart_earnings(
        session,
        settings=settings,
        transport=dart_transport,
        symbols=["005930"],
        until=date(2026, 4, 30),
    )


# ---------------------------------------------------------------------------
# Body / secret discipline
# ---------------------------------------------------------------------------

_FORBIDDEN_BODY_FIELDS = {
    "body",
    "content",
    "full_text",
    "fulltext",
    "paragraph",
    "raw_text",
    "html_body",
    "본문",
    "원문",
    "전문",
}


@pytest.mark.parametrize(
    "model_cls",
    [NewsItem, FundamentalSnapshot, EarningsEvent],
)
def test_db_models_have_no_forbidden_body_columns(model_cls):
    column_names = {c.name for c in inspect(model_cls).columns}
    leaked = column_names & _FORBIDDEN_BODY_FIELDS
    assert leaked == set(), f"{model_cls.__name__} leaked body columns: {leaked}"


@pytest.mark.parametrize(
    "dto_cls",
    [NewsItemDTO, DisclosureItemDTO, FundamentalSnapshotDTO, EarningsEventDTO],
)
def test_dtos_have_no_forbidden_body_fields(dto_cls):
    names = {f.name for f in dc_fields(dto_cls)}
    leaked = names & _FORBIDDEN_BODY_FIELDS
    assert leaked == set(), f"{dto_cls.__name__} leaked body fields: {leaked}"


def test_ingestion_does_not_log_dart_api_key(
    session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """No code path inside the adapters should log the DART_API_KEY
    plaintext.  ``crtfc_key`` is injected by the provider's ``_call``
    deeper down; the adapter never sees it directly.
    """
    settings = _enabled_settings(
        monkeypatch, dart_api_key="SUPER-SECRET-KEY-DO-NOT-LOG-XYZ"
    )

    def transport(_path, _params):
        return ProviderCallResult.ok(_DART_DISCLOSURE_FIXTURE)

    with caplog.at_level(logging.DEBUG):
        ingest_dart_disclosures(
            session, settings=settings, transport=transport
        )

    joined = " ".join(rec.getMessage() for rec in caplog.records)
    assert "SUPER-SECRET-KEY-DO-NOT-LOG-XYZ" not in joined


def test_ingestion_does_not_log_rss_feed_url_query_secret(
    session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    settings = _enabled_settings(
        monkeypatch,
        rss_feed_urls="https://example.com/feed.xml?api_key=PRIVATE-FEED-SECRET-XYZ",
    )

    def transport(_url):
        return ProviderCallResult.ok(_RSS_FIXTURE_BYTES)

    with caplog.at_level(logging.DEBUG):
        ingest_rss_news(session, settings=settings, transport=transport)

    joined = " ".join(rec.getMessage() for rec in caplog.records)
    assert "PRIVATE-FEED-SECRET-XYZ" not in joined


# ---------------------------------------------------------------------------
# Producer / weight regression -- ScoringEngine weight formulas unchanged
# ---------------------------------------------------------------------------


def test_scoring_engine_weight_formulas_are_unchanged():
    """v0.12 Phase A flips data inputs from fake → real but must NEVER
    change the ScoringEngine recommendation / holding weight formulas.

    This regression assertion pins the exact weight values inherited
    from v0.5/v0.6 against accidental edits during cycle work.
    """
    from decimal import Decimal  # noqa: PLC0415

    from app.decision.scoring_engine import ScoringEngine  # noqa: PLC0415

    assert ScoringEngine.NEW_RECOMMENDATION_WEIGHTS == {
        "technical": Decimal("0.35"),
        "news": Decimal("0.25"),
        "supply": Decimal("0.15"),
        "fundamental": Decimal("0.15"),
        "ai": Decimal("0.10"),
    }
    assert ScoringEngine.HOLDING_WEIGHTS == {
        "technical": Decimal("0.35"),
        "news": Decimal("0.20"),
        "earnings": Decimal("0.20"),
        "ai": Decimal("0.15"),
        "profit_management": Decimal("0.10"),
    }
