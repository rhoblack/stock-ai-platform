from datetime import date
from decimal import Decimal

from app.data.dtos import KisDailyPrice, KisMarketCapRanking
from app.data.validators import DataQualityChecker


def test_daily_price_quality_checker_accepts_valid_prices():
    checker = DataQualityChecker()
    prices = [
        KisDailyPrice(
            symbol="005930",
            date=date(2026, 5, 4),
            open=Decimal("70000"),
            high=Decimal("71000"),
            low=Decimal("69000"),
            close=Decimal("70500"),
            volume=1000000,
        ),
    ]

    assert checker.check_daily_prices(prices) == []


def test_daily_price_quality_checker_reports_duplicate_and_zero_volume():
    checker = DataQualityChecker()
    price = KisDailyPrice(
        symbol="005930",
        date=date(2026, 5, 4),
        open=Decimal("70000"),
        high=Decimal("71000"),
        low=Decimal("69000"),
        close=Decimal("70500"),
        volume=0,
    )

    issues = checker.check_daily_prices([price, price])
    codes = {issue.code for issue in issues}

    assert "ZERO_VOLUME" in codes
    assert "DUPLICATE_DAILY_PRICE" in codes


def test_daily_price_quality_checker_reports_invalid_ohlc_range():
    checker = DataQualityChecker()
    prices = [
        KisDailyPrice(
            symbol="005930",
            date=date(2026, 5, 4),
            open=Decimal("70000"),
            high=Decimal("69000"),
            low=Decimal("71000"),
            close=Decimal("70500"),
            volume=100,
        ),
    ]

    codes = {issue.code for issue in checker.check_daily_prices(prices)}

    assert "INVALID_HIGH_LOW_RANGE" in codes


def test_market_cap_ranking_quality_checker_reports_duplicates_and_short_count():
    checker = DataQualityChecker()
    rankings = [
        KisMarketCapRanking(
            rank_date=date(2026, 5, 4),
            market="KOSPI",
            rank=1,
            symbol="005930",
            name="삼성전자",
        ),
        KisMarketCapRanking(
            rank_date=date(2026, 5, 4),
            market="KOSPI",
            rank=1,
            symbol="005930",
            name="삼성전자",
        ),
    ]

    issues = checker.check_market_cap_rankings(rankings, expected_limit=3)
    codes = {issue.code for issue in issues}

    assert "RANKING_COUNT_SHORT" in codes
    assert "DUPLICATE_RANKING_SYMBOL" in codes
    assert "DUPLICATE_RANK" in codes
