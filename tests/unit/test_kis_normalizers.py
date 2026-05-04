from datetime import date, datetime
from decimal import Decimal

from app.data.normalizers import (
    normalize_current_price,
    normalize_daily_prices,
    normalize_market_cap_rankings,
)
from tests.mocks.kis_responses import (
    CURRENT_PRICE_RESPONSE,
    DAILY_PRICE_RESPONSE,
    MARKET_CAP_RANKING_RESPONSE,
)


def test_normalize_current_price_response():
    captured_at = datetime(2026, 5, 4, 9, 0)

    result = normalize_current_price(CURRENT_PRICE_RESPONSE, captured_at=captured_at)

    assert result.symbol == "005930"
    assert result.name == "삼성전자"
    assert result.market == "KOSPI"
    assert result.current_price == Decimal("70500")
    assert result.change_rate == Decimal("1.23")
    assert result.volume == 1234567
    assert result.captured_at == captured_at


def test_normalize_daily_price_response():
    result = normalize_daily_prices(DAILY_PRICE_RESPONSE, symbol="005930")

    assert len(result) == 2
    assert result[0].symbol == "005930"
    assert result[0].date == date(2026, 5, 4)
    assert result[0].open == Decimal("70000")
    assert result[0].high == Decimal("71000")
    assert result[0].low == Decimal("69000")
    assert result[0].close == Decimal("70500")
    assert result[0].volume == 1000000


def test_normalize_market_cap_ranking_response():
    result = normalize_market_cap_rankings(
        MARKET_CAP_RANKING_RESPONSE,
        ranking_date=date(2026, 5, 4),
        market="KOSPI",
    )

    assert len(result) == 2
    assert result[0].rank == 1
    assert result[0].symbol == "005930"
    assert result[0].name == "삼성전자"
    assert result[0].market_cap == Decimal("500000000000000")
    assert result[1].symbol == "000660"

