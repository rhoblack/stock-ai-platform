from datetime import date
from decimal import Decimal

import pytest

from app.data.collectors import (
    DailyPriceCollector,
    DailyPriceCollectorResult,
    MarketCapRankingCollector,
    MarketCapRankingCollectorResult,
)
from app.data.repositories import (
    DailyPriceRepository,
    MarketCapRankingRepository,
    StockRepository,
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.db import Base
from app.db.session import create_db_engine, create_session_factory
from tests.mocks.fake_kis_client import FakeKisDataProvider
from tests.mocks.kis_responses import DAILY_PRICE_RESPONSE, MARKET_CAP_RANKING_RESPONSE


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


def _daily_price_rows() -> list[dict]:
    return list(DAILY_PRICE_RESPONSE["output2"])


def _market_cap_rows() -> list[dict]:
    return list(MARKET_CAP_RANKING_RESPONSE["output"])


def test_daily_price_collector_normalizes_and_upserts(session):
    provider = FakeKisDataProvider(daily_price_responses={"005930": _daily_price_rows()})
    collector = DailyPriceCollector(
        client=provider,
        repository=DailyPriceRepository(session),
    )

    result = collector.collect(
        symbol="005930",
        start_date=date(2026, 5, 3),
        end_date=date(2026, 5, 4),
    )
    session.commit()

    assert isinstance(result, DailyPriceCollectorResult)
    assert result.symbol == "005930"
    assert result.saved_count == 2
    assert result.quality_issues == []

    repo = DailyPriceRepository(session)
    persisted = repo.get_by_symbol_date("005930", date(2026, 5, 4))
    assert persisted is not None
    assert persisted.close == Decimal("70500.0000")
    assert persisted.volume == 1000000

    assert provider.calls[0][0] == "fetch_daily_prices"
    assert provider.calls[0][1] == ("005930", date(2026, 5, 3), date(2026, 5, 4))


def test_daily_price_collector_is_idempotent_on_rerun(session):
    provider = FakeKisDataProvider(daily_price_responses={"005930": _daily_price_rows()})
    collector = DailyPriceCollector(
        client=provider,
        repository=DailyPriceRepository(session),
    )

    collector.collect(symbol="005930", start_date=date(2026, 5, 3), end_date=date(2026, 5, 4))
    session.commit()
    second = collector.collect(
        symbol="005930",
        start_date=date(2026, 5, 3),
        end_date=date(2026, 5, 4),
    )
    session.commit()

    assert second.saved_count == 2

    rows = DailyPriceRepository(session).list()
    assert len(rows) == 2  # symbol+date upsert prevents duplicates


def test_daily_price_collector_overwrites_existing_row_on_corrected_data(session):
    repository = DailyPriceRepository(session)
    initial_rows = [
        {
            "stck_bsop_date": "20260504",
            "stck_oprc": "70000",
            "stck_hgpr": "71000",
            "stck_lwpr": "69000",
            "stck_clpr": "70500",
            "acml_vol": "1000000",
            "acml_tr_pbmn": "70500000000",
        },
    ]
    corrected_rows = [
        {
            "stck_bsop_date": "20260504",
            "stck_oprc": "70100",
            "stck_hgpr": "72500",
            "stck_lwpr": "70000",
            "stck_clpr": "72000",
            "acml_vol": "1500000",
            "acml_tr_pbmn": "108000000000",
        },
    ]

    DailyPriceCollector(
        client=FakeKisDataProvider(daily_price_responses={"005930": initial_rows}),
        repository=repository,
    ).collect(symbol="005930", start_date=date(2026, 5, 4), end_date=date(2026, 5, 4))
    session.commit()

    DailyPriceCollector(
        client=FakeKisDataProvider(daily_price_responses={"005930": corrected_rows}),
        repository=repository,
    ).collect(symbol="005930", start_date=date(2026, 5, 4), end_date=date(2026, 5, 4))
    session.commit()

    persisted = repository.get_by_symbol_date("005930", date(2026, 5, 4))
    assert persisted is not None
    assert persisted.close == Decimal("72000.0000")
    assert persisted.volume == 1500000


def test_daily_price_collector_reports_quality_issues(session):
    provider = FakeKisDataProvider(
        daily_price_responses={
            "005930": [
                {
                    "stck_bsop_date": "20260504",
                    "stck_oprc": "70000",
                    "stck_hgpr": "71000",
                    "stck_lwpr": "69000",
                    "stck_clpr": "70500",
                    "acml_vol": "0",
                    "acml_tr_pbmn": "0",
                },
            ],
        },
    )
    collector = DailyPriceCollector(
        client=provider,
        repository=DailyPriceRepository(session),
    )

    result = collector.collect(
        symbol="005930",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 4),
    )
    session.commit()

    assert result.saved_count == 1
    assert any(issue.code == "ZERO_VOLUME" for issue in result.quality_issues)


def test_market_cap_ranking_collector_saves_rankings_stocks_and_universe_members(session):
    rank_date = date(2026, 5, 4)
    provider = FakeKisDataProvider(
        market_cap_responses={("KOSPI", rank_date): _market_cap_rows()},
    )
    ranking_repo = MarketCapRankingRepository(session)
    stock_repo = StockRepository(session)
    universe_repo = StockUniverseRepository(session)
    member_repo = StockUniverseMemberRepository(session)

    collector = MarketCapRankingCollector(
        client=provider,
        ranking_repository=ranking_repo,
        stock_repository=stock_repo,
        universe_repository=universe_repo,
        member_repository=member_repo,
    )
    result = collector.collect(market="KOSPI", ranking_date=rank_date, limit=2)
    session.commit()

    assert isinstance(result, MarketCapRankingCollectorResult)
    assert result.saved_rankings == 2
    assert result.new_stocks == 2
    assert result.new_universe_members == 2
    assert result.quality_issues == []

    rankings = ranking_repo.list_by_date_market(rank_date, "KOSPI")
    assert [r.symbol for r in rankings] == ["005930", "000660"]
    assert rankings[0].sector == "전기전자"

    stock = stock_repo.get_by_symbol("005930")
    assert stock is not None
    assert stock.name == "삼성전자"
    assert stock.market == "KOSPI"
    assert stock.sector == "전기전자"

    universe, _ = universe_repo.get_or_create(
        name=MarketCapRankingCollector.DEFAULT_UNIVERSE_NAME,
    )
    members = member_repo.list_by_universe(universe.universe_id)
    assert {m.symbol for m in members} == {"005930", "000660"}


def test_market_cap_ranking_collector_replaces_snapshot_for_same_date_market(session):
    rank_date = date(2026, 5, 4)

    swapped_rows = [
        {
            "data_rank": "1",
            "mksc_shrn_iscd": "000660",
            "hts_kor_isnm": "SK하이닉스",
            "stck_avls": "200000000000000",
            "stck_prpr": "165000",
            "lstn_stcn": "728002365",
            "bstp_kor_isnm": "전기전자",
            "acml_tr_pbmn": "65000000000",
        },
        {
            "data_rank": "2",
            "mksc_shrn_iscd": "005930",
            "hts_kor_isnm": "삼성전자",
            "stck_avls": "150000000000000",
            "stck_prpr": "70500",
            "lstn_stcn": "5969782550",
            "bstp_kor_isnm": "전기전자",
            "acml_tr_pbmn": "87000000000",
        },
    ]

    ranking_repo = MarketCapRankingRepository(session)
    stock_repo = StockRepository(session)
    universe_repo = StockUniverseRepository(session)
    member_repo = StockUniverseMemberRepository(session)

    first_collector = MarketCapRankingCollector(
        client=FakeKisDataProvider(
            market_cap_responses={("KOSPI", rank_date): _market_cap_rows()},
        ),
        ranking_repository=ranking_repo,
        stock_repository=stock_repo,
        universe_repository=universe_repo,
        member_repository=member_repo,
    )
    first_collector.collect(market="KOSPI", ranking_date=rank_date, limit=2)
    session.commit()

    second_collector = MarketCapRankingCollector(
        client=FakeKisDataProvider(
            market_cap_responses={("KOSPI", rank_date): swapped_rows},
        ),
        ranking_repository=ranking_repo,
        stock_repository=stock_repo,
        universe_repository=universe_repo,
        member_repository=member_repo,
    )
    result = second_collector.collect(market="KOSPI", ranking_date=rank_date, limit=2)
    session.commit()

    # Stocks and universe members were already there; no new ones.
    assert result.new_stocks == 0
    assert result.new_universe_members == 0
    assert result.saved_rankings == 2

    rankings = ranking_repo.list_by_date_market(rank_date, "KOSPI")
    assert [r.symbol for r in rankings] == ["000660", "005930"]
    assert rankings[0].rank == 1
    assert rankings[1].rank == 2

    universe, _ = universe_repo.get_or_create(
        name=MarketCapRankingCollector.DEFAULT_UNIVERSE_NAME,
    )
    members = member_repo.list_by_universe(universe.universe_id)
    assert len(members) == 2  # not duplicated


def test_market_cap_ranking_collector_uses_custom_universe_name(session):
    rank_date = date(2026, 5, 4)
    provider = FakeKisDataProvider(
        market_cap_responses={("KOSPI", rank_date): _market_cap_rows()},
    )
    universe_repo = StockUniverseRepository(session)

    collector = MarketCapRankingCollector(
        client=provider,
        ranking_repository=MarketCapRankingRepository(session),
        stock_repository=StockRepository(session),
        universe_repository=universe_repo,
        member_repository=StockUniverseMemberRepository(session),
    )
    result = collector.collect(
        market="KOSPI",
        ranking_date=rank_date,
        limit=2,
        universe_name="KOSPI_TOP_300",
    )
    session.commit()

    assert universe_repo.get_by_name("KOSPI_TOP_300") is not None
    assert universe_repo.get_by_name(MarketCapRankingCollector.DEFAULT_UNIVERSE_NAME) is None
    assert result.universe_id == universe_repo.get_by_name("KOSPI_TOP_300").universe_id


def test_market_cap_ranking_collector_reports_count_short_quality_issue(session):
    rank_date = date(2026, 5, 4)
    provider = FakeKisDataProvider(
        market_cap_responses={("KOSPI", rank_date): _market_cap_rows()},
    )
    collector = MarketCapRankingCollector(
        client=provider,
        ranking_repository=MarketCapRankingRepository(session),
        stock_repository=StockRepository(session),
        universe_repository=StockUniverseRepository(session),
        member_repository=StockUniverseMemberRepository(session),
    )

    result = collector.collect(market="KOSPI", ranking_date=rank_date, limit=10)
    session.commit()

    assert any(issue.code == "RANKING_COUNT_SHORT" for issue in result.quality_issues)
    assert result.saved_rankings == 2
