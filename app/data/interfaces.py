from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

from app.data.dtos import DisclosureItemDTO, FundamentalSnapshotDTO, NewsItemDTO


class DataProviderInterface(ABC):
    """Read-only external data provider contract for v0.1 collection flows."""

    @abstractmethod
    def fetch_current_price(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_market_cap_rankings(
        self,
        market: str,
        ranking_date: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_news(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_disclosures(
        self,
        symbols: list[str],
        target_date: date,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class NewsProviderInterface(ABC):
    """v0.5 — typed news provider contract.

    Implementations return :class:`NewsItemDTO` lists carrying *metadata only*
    (title / url / source / sentiment_label / category / short summary). Full
    article bodies / paragraphs / raw HTML must NEVER appear in either the
    DTO or the underlying provider's return value — see PROJECT_STATUS.md
    §0 v0.5 정책.

    The legacy ``DataProviderInterface.fetch_news`` (raw-dict signature) stays
    in place as a KIS-shaped placeholder; v0.5 collectors target this newer,
    typed interface instead.
    """

    @abstractmethod
    def fetch_recent_news(
        self,
        *,
        symbols: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItemDTO]:
        raise NotImplementedError


class DisclosureProviderInterface(ABC):
    """v0.5 Phase B — typed disclosure provider contract.

    Implementations (FakeDisclosureProvider in tests, real DART / KRX adapters
    in v0.6+) return :class:`DisclosureItemDTO` lists carrying *metadata only*.
    Original disclosure body / paragraph text MUST NEVER appear in either the
    DTO or the underlying provider's return value — see PROJECT_STATUS.md
    §0 v0.5 정책. Auto-fetching is opt-in via
    ``Settings.disclosure_collection_enabled`` (default False).
    """

    @abstractmethod
    def fetch_recent_disclosures(
        self,
        *,
        symbols: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[DisclosureItemDTO]:
        raise NotImplementedError


class FundamentalProviderInterface(ABC):
    """v0.6 typed fundamental provider contract.

    This is an interface only in Phase A PR2. Real DART adapters are out of
    scope; tests use a deterministic fake provider. Implementations must return
    normalized metrics only and must not expose original financial statement
    bodies, paragraphs, raw HTML, PDF/Excel blobs, or local file paths.
    """

    @abstractmethod
    def fetch_fundamentals(
        self,
        symbols: list[str],
        fiscal_year: int,
        fiscal_quarter: int | None = None,
    ) -> list[FundamentalSnapshotDTO]:
        raise NotImplementedError
