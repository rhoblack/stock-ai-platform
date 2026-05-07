from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


# ---------------------------------------------------------------------------
# v0.12 Phase A -- DTO data_source provenance tag.
#
# Categorical metadata-only field added to every provider-shaped DTO so
# downstream code (Phase D evidence chip / observability) can distinguish
# whether a record arrived via:
#
#   "PROVIDER" -- ingested through a v0.11 HTTP transport (DART/RSS)
#   "FAKE"     -- emitted by a deterministic Fake* provider (tests)
#   "CSV"      -- imported from operator-supplied CSV (v0.4 / v0.6)
#   "MANUAL"   -- direct DB seed / scripts/seed_mock_data.py
#
# Default value across all DTOs is ``"FAKE"`` so existing tests / fixtures
# remain backward-compatible without a touch.  The field is **runtime-only**
# (DTO metadata) -- no DB column is added.  When Phase D needs to surface
# the provenance through the API, it derives it at projection time from
# the existing ``source`` column or via a runtime registry.
# ---------------------------------------------------------------------------

DATA_SOURCE_PROVIDER = "PROVIDER"
DATA_SOURCE_FAKE = "FAKE"
DATA_SOURCE_CSV = "CSV"
DATA_SOURCE_MANUAL = "MANUAL"

ALLOWED_DATA_SOURCES: frozenset[str] = frozenset(
    {
        DATA_SOURCE_PROVIDER,
        DATA_SOURCE_FAKE,
        DATA_SOURCE_CSV,
        DATA_SOURCE_MANUAL,
    }
)


@dataclass(frozen=True)
class KisCurrentPrice:
    symbol: str
    name: str | None
    market: str | None
    current_price: Decimal
    change_rate: Decimal | None = None
    volume: int | None = None
    trading_value: Decimal | None = None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class KisDailyPrice:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trading_value: Decimal | None = None


@dataclass(frozen=True)
class KisMarketCapRanking:
    rank_date: date
    market: str
    rank: int
    symbol: str
    name: str
    market_cap: Decimal | None = None
    close_price: Decimal | None = None
    listed_shares: int | None = None
    sector: str | None = None
    trading_value: Decimal | None = None
    is_analysis_target: bool = True


# ---------------------------------------------------------------------------
# v0.5 — News collection (Phase A)
#
# NewsItemDTO is the typed payload every NewsProviderInterface returns. It
# carries metadata only — original article body / paragraph / full text MUST
# NOT be added to this dataclass. The integration test in
# ``tests/integration/test_news_collector.py`` enforces this guard.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NewsItemDTO:
    title: str
    url: str
    provider: str
    published_at: datetime
    symbol: str | None = None
    source: str | None = None
    category: str | None = None
    sentiment_label: str | None = None
    summary: str | None = None
    # v0.12 Phase A -- runtime-only provenance tag.  See DATA_SOURCE_* above.
    data_source: str = DATA_SOURCE_FAKE


# ---------------------------------------------------------------------------
# v0.5 Phase B — Disclosure collection
#
# DisclosureItemDTO 는 DART / KRX 스타일 공시 메타데이터의 typed payload 다.
# NewsItemDTO 와 마찬가지로 본문 paragraph / full_text / raw_html 등은
# 절대 추가하지 않는다 — 통합 테스트가 ``dataclass.fields`` 로 가드한다.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DisclosureItemDTO:
    title: str
    url: str
    provider: str
    published_at: datetime
    symbol: str | None = None
    company_name: str | None = None
    disclosure_type: str | None = None
    category: str | None = None
    summary: str | None = None
    # v0.12 Phase A -- runtime-only provenance tag.  See DATA_SOURCE_* above.
    data_source: str = DATA_SOURCE_FAKE


# ---------------------------------------------------------------------------
# v0.6 Phase A -- Fundamental CSV/provider payload
#
# FundamentalSnapshotDTO carries normalized financial metrics only. Do not add
# body/content/full_text/paragraph/raw_text/html_body or Korean equivalents.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FundamentalSnapshotDTO:
    symbol: str
    snapshot_date: date
    fiscal_year: int
    fiscal_quarter: int | None
    revenue: Decimal | None = None
    operating_income: Decimal | None = None
    net_income: Decimal | None = None
    total_assets: Decimal | None = None
    total_liabilities: Decimal | None = None
    total_equity: Decimal | None = None
    eps: Decimal | None = None
    bps: Decimal | None = None
    per: Decimal | None = None
    pbr: Decimal | None = None
    roe: Decimal | None = None
    debt_ratio: Decimal | None = None
    dividend_yield: Decimal | None = None
    revenue_growth_yoy: Decimal | None = None
    operating_income_growth_yoy: Decimal | None = None
    source: str | None = None
    # v0.12 Phase A -- runtime-only provenance tag.  See DATA_SOURCE_* above.
    data_source: str = DATA_SOURCE_FAKE


@dataclass(frozen=True)
class EarningsEventDTO:
    symbol: str
    event_date: date
    fiscal_year: int
    event_type: str
    company_name: str | None = None
    fiscal_quarter: int | None = None
    revenue_actual: Decimal | None = None
    revenue_consensus: Decimal | None = None
    operating_income_actual: Decimal | None = None
    operating_income_consensus: Decimal | None = None
    net_income_actual: Decimal | None = None
    net_income_consensus: Decimal | None = None
    eps_actual: Decimal | None = None
    eps_consensus: Decimal | None = None
    surprise_type: str | None = None
    surprise_pct: Decimal | None = None
    source: str | None = None
    memo: str | None = None
    # v0.12 Phase A -- runtime-only provenance tag.  See DATA_SOURCE_* above.
    data_source: str = DATA_SOURCE_FAKE
