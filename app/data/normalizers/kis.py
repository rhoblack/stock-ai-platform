from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.data.dtos import KisCurrentPrice, KisDailyPrice, KisMarketCapRanking


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _required_decimal(value: Any, field_name: str) -> Decimal:
    parsed = _decimal(value)
    if parsed is None:
        raise ValueError(f"Missing required decimal field: {field_name}")
    return parsed


def _int(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    return int(text.replace(",", ""))


def _required_int(value: Any, field_name: str) -> int:
    parsed = _int(value)
    if parsed is None:
        raise ValueError(f"Missing required integer field: {field_name}")
    return parsed


def _date(value: Any) -> date:
    text = _clean_text(value)
    if text is None:
        raise ValueError("Missing required date value")
    return datetime.strptime(text, "%Y%m%d").date()


def normalize_current_price(raw: dict[str, Any], captured_at: datetime | None = None) -> KisCurrentPrice:
    output = raw.get("output", raw)
    symbol = _clean_text(output.get("stck_shrn_iscd") or output.get("symbol"))
    if symbol is None:
        raise ValueError("Missing current price symbol")

    return KisCurrentPrice(
        symbol=symbol,
        name=_clean_text(output.get("hts_kor_isnm") or output.get("name")),
        market=_clean_text(output.get("rprs_mrkt_kor_name") or output.get("market")),
        current_price=_required_decimal(output.get("stck_prpr") or output.get("current_price"), "current_price"),
        change_rate=_decimal(output.get("prdy_ctrt") or output.get("change_rate")),
        volume=_int(output.get("acml_vol") or output.get("volume")),
        trading_value=_decimal(output.get("acml_tr_pbmn") or output.get("trading_value")),
        captured_at=captured_at,
    )


def normalize_daily_prices(raw: dict[str, Any], symbol: str) -> list[KisDailyPrice]:
    rows = raw.get("output2") or raw.get("output") or raw.get("prices") or []
    normalized: list[KisDailyPrice] = []
    for row in rows:
        normalized.append(
            KisDailyPrice(
                symbol=symbol,
                date=_date(row.get("stck_bsop_date") or row.get("date")),
                open=_required_decimal(row.get("stck_oprc") or row.get("open"), "open"),
                high=_required_decimal(row.get("stck_hgpr") or row.get("high"), "high"),
                low=_required_decimal(row.get("stck_lwpr") or row.get("low"), "low"),
                close=_required_decimal(row.get("stck_clpr") or row.get("close"), "close"),
                volume=_required_int(row.get("acml_vol") or row.get("volume"), "volume"),
                trading_value=_decimal(row.get("acml_tr_pbmn") or row.get("trading_value")),
            ),
        )
    return normalized


def normalize_market_cap_rankings(
    raw: dict[str, Any],
    ranking_date: date,
    market: str,
) -> list[KisMarketCapRanking]:
    rows = raw.get("output") or raw.get("rankings") or []
    normalized: list[KisMarketCapRanking] = []
    for row in rows:
        symbol = _clean_text(row.get("mksc_shrn_iscd") or row.get("stck_shrn_iscd") or row.get("symbol"))
        name = _clean_text(row.get("hts_kor_isnm") or row.get("name"))
        if symbol is None or name is None:
            raise ValueError("Missing market cap ranking symbol or name")

        normalized.append(
            KisMarketCapRanking(
                rank_date=ranking_date,
                market=market,
                rank=_required_int(row.get("data_rank") or row.get("rank"), "rank"),
                symbol=symbol,
                name=name,
                market_cap=_decimal(row.get("stck_avls") or row.get("market_cap")),
                close_price=_decimal(row.get("stck_prpr") or row.get("close_price")),
                listed_shares=_int(row.get("lstn_stcn") or row.get("listed_shares")),
                sector=_clean_text(row.get("bstp_kor_isnm") or row.get("sector")),
                trading_value=_decimal(row.get("acml_tr_pbmn") or row.get("trading_value")),
            ),
        )
    return normalized

