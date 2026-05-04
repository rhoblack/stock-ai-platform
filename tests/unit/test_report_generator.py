from datetime import date, datetime
from decimal import Decimal

from app.db.models import (
    DataSnapshot,
    HoldingCheck,
    Recommendation,
    RecommendationRun,
)
from app.decision.risk_engine import (
    RISK_FLAG_MA20_BREAKDOWN,
    RISK_FLAG_SCORE_DROP,
    RISK_FLAG_STOP_LOSS_NEAR,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
)
from app.notification.report_generator import (
    HoldingLine,
    RecommendationLine,
    ReportGenerator,
    extract_risk_summary,
)


def _recommendation_row(
    *,
    rank: int,
    symbol: str,
    name: str,
    grade: str = "A",
    total_score: Decimal = Decimal("75.0000"),
    reason: str = "관찰 후보 · 기술점수 80",
    market: str = "KOSPI",
) -> Recommendation:
    return Recommendation(
        run_id=1,
        rank=rank,
        market=market,
        symbol=symbol,
        name=name,
        grade=grade,
        total_score=total_score,
        technical_score=total_score,
        reason=reason,
    )


def _run() -> RecommendationRun:
    return RecommendationRun(
        run_id=1,
        run_date=date(2026, 5, 4),
        started_at=datetime(2026, 5, 4, 6, 0),
        finished_at=datetime(2026, 5, 4, 6, 1),
        status="SUCCESS",
        market_summary={
            "universe": "MARKET_CAP_TOP_500",
            "candidate_count": 7,
            "saved_count": 2,
        },
    )


def _holding_check(
    *,
    symbol: str,
    grade: str = "A",
    decision: str = "HOLD",
    total_score: Decimal = Decimal("75.0000"),
    return_rate: Decimal | None = Decimal("4.8000"),
) -> HoldingCheck:
    return HoldingCheck(
        check_date=date(2026, 5, 4),
        check_type="PRE_MARKET",
        symbol=symbol,
        current_price=Decimal("105"),
        avg_buy_price=Decimal("100"),
        return_rate=return_rate,
        total_score=total_score,
        grade=grade,
        decision=decision,
        reason=f"{decision} reason",
        alert=False,
    )


# ---------- extract_risk_summary ----------

def test_extract_risk_summary_returns_low_default_for_missing_snapshot():
    assert extract_risk_summary(None) == (RISK_LEVEL_LOW, [])


def test_extract_risk_summary_returns_low_default_when_market_context_empty():
    snapshot = DataSnapshot(
        snapshot_time=datetime(2026, 5, 4, 8, 30),
        symbol="005930",
        snapshot_type="HOLDING_CHECK",
        market_context_json=None,
    )
    assert extract_risk_summary(snapshot) == (RISK_LEVEL_LOW, [])


def test_extract_risk_summary_reads_level_and_flags():
    snapshot = DataSnapshot(
        snapshot_time=datetime(2026, 5, 4, 8, 30),
        symbol="005930",
        snapshot_type="HOLDING_CHECK",
        market_context_json={
            "risk_summary": {
                "level": RISK_LEVEL_HIGH,
                "flags": [RISK_FLAG_MA20_BREAKDOWN, RISK_FLAG_STOP_LOSS_NEAR],
                "penalty": "23.0000",
            },
        },
    )
    level, flags = extract_risk_summary(snapshot)
    assert level == RISK_LEVEL_HIGH
    assert flags == [RISK_FLAG_MA20_BREAKDOWN, RISK_FLAG_STOP_LOSS_NEAR]


# ---------- recommendation report ----------

def test_recommendation_report_renders_title_and_summary():
    gen = ReportGenerator()
    text = gen.recommendation_report(run=_run(), lines=[])
    assert "[AI 주식 리포트] 2026-05-04" in text
    assert "▶ 시장 요약" in text
    assert "universe: MARKET_CAP_TOP_500" in text
    assert "관찰 후보가 없습니다" in text


def test_recommendation_report_lists_candidates_with_risk_text():
    gen = ReportGenerator()
    lines = [
        RecommendationLine(
            recommendation=_recommendation_row(
                rank=1, symbol="005930", name="삼성전자",
                grade="S", total_score=Decimal("87.0000"),
                reason="관찰 후보 · 기술점수 82 · MA정렬 PERFECT_BULL",
            ),
            risk_level=RISK_LEVEL_LOW,
            risk_flags=[],
        ),
        RecommendationLine(
            recommendation=_recommendation_row(
                rank=2, symbol="000660", name="SK하이닉스",
                grade="B", total_score=Decimal("60.0000"),
                reason="관찰 후보 · 기술점수 50",
            ),
            risk_level=RISK_LEVEL_MEDIUM,
            risk_flags=["LOW_TECHNICAL_SCORE"],
        ),
    ]
    text = gen.recommendation_report(run=_run(), lines=lines)
    assert "1. 삼성전자 (005930) / S / 87.00점" in text
    assert "MA정렬 PERFECT_BULL" in text
    assert "리스크: LOW" in text
    assert "2. SK하이닉스 (000660) / B / 60.00점" in text
    assert "리스크: MEDIUM (기술 점수 낮음)" in text
    assert "관찰 후보 · 기술점수 50" in text


def test_recommendation_report_orders_by_rank_even_when_input_unsorted():
    gen = ReportGenerator()
    lines = [
        RecommendationLine(
            recommendation=_recommendation_row(rank=2, symbol="B", name="B"),
            risk_level=RISK_LEVEL_LOW,
            risk_flags=[],
        ),
        RecommendationLine(
            recommendation=_recommendation_row(rank=1, symbol="A", name="A"),
            risk_level=RISK_LEVEL_LOW,
            risk_flags=[],
        ),
    ]
    text = gen.recommendation_report(run=_run(), lines=lines)
    pos_a = text.index("1. A")
    pos_b = text.index("2. B")
    assert pos_a < pos_b


# ---------- holding reports ----------

def test_pre_market_holding_report_empty():
    gen = ReportGenerator()
    text = gen.pre_market_holding_report(check_date=date(2026, 5, 4), lines=[])
    assert "[보유 종목 장전 점검] 2026-05-04" in text
    assert "점검 대상 보유 종목이 없습니다" in text


def test_pre_market_holding_report_high_risk_first():
    gen = ReportGenerator()
    lines = [
        HoldingLine(
            check=_holding_check(
                symbol="005930", grade="A", decision="HOLD",
                total_score=Decimal("75.0000"), return_rate=Decimal("4.80"),
            ),
            risk_level=RISK_LEVEL_LOW,
            risk_flags=[],
        ),
        HoldingLine(
            check=_holding_check(
                symbol="000660", grade="D", decision="SELL_REVIEW",
                total_score=Decimal("0.0000"), return_rate=Decimal("-10.00"),
            ),
            risk_level=RISK_LEVEL_HIGH,
            risk_flags=[
                RISK_FLAG_SCORE_DROP,
                RISK_FLAG_MA20_BREAKDOWN,
                RISK_FLAG_STOP_LOSS_NEAR,
            ],
        ),
        HoldingLine(
            check=_holding_check(
                symbol="207940", grade="C", decision="REDUCE",
                total_score=Decimal("45.0000"), return_rate=Decimal("-2.0"),
            ),
            risk_level=RISK_LEVEL_MEDIUM,
            risk_flags=[RISK_FLAG_MA20_BREAKDOWN],
        ),
    ]
    text = gen.pre_market_holding_report(
        check_date=date(2026, 5, 4),
        lines=lines,
    )
    assert "⚠ 위험 경고 종목 (1건)" in text
    assert "▶ 일반 점검 종목" in text

    pos_high = text.index("000660")
    pos_low = text.index("005930")
    pos_med = text.index("207940")
    assert pos_high < pos_med < pos_low

    assert "1. 000660" in text  # HIGH first, rank 1
    assert "수익률: -10.00%" in text
    assert "20일선 이탈" in text


def test_post_market_holding_report_uses_post_market_title():
    gen = ReportGenerator()
    text = gen.post_market_holding_report(check_date=date(2026, 5, 4), lines=[])
    assert "[보유 종목 장후 점검] 2026-05-04" in text


def test_pre_market_holding_report_skips_high_section_when_no_high_risk():
    gen = ReportGenerator()
    lines = [
        HoldingLine(
            check=_holding_check(symbol="005930"),
            risk_level=RISK_LEVEL_LOW,
            risk_flags=[],
        ),
    ]
    text = gen.pre_market_holding_report(
        check_date=date(2026, 5, 4),
        lines=lines,
    )
    assert "⚠ 위험 경고 종목" not in text
    assert "▶ 일반 점검 종목" in text


# ---------- risk alert ----------

def test_risk_alert_renders_single_line_format():
    gen = ReportGenerator()
    line = HoldingLine(
        check=_holding_check(
            symbol="000660",
            grade="D",
            decision="SELL_REVIEW",
            total_score=Decimal("0.0000"),
            return_rate=Decimal("-10.00"),
        ),
        risk_level=RISK_LEVEL_HIGH,
        risk_flags=[RISK_FLAG_SCORE_DROP, RISK_FLAG_STOP_LOSS_NEAR],
    )
    text = gen.risk_alert(line=line)
    assert text.startswith("⚠ [위험 경고] 000660")
    assert "수익률: -10.00%" in text
    assert "판단: SELL_REVIEW" in text
    assert "위험: HIGH (점수 급락, 손절 근접)" in text
    assert "PC 대시보드에서 즉시 확인 필요" in text


def test_risk_alert_handles_missing_return_rate():
    gen = ReportGenerator()
    line = HoldingLine(
        check=_holding_check(symbol="005930", return_rate=None),
        risk_level=RISK_LEVEL_LOW,
        risk_flags=[],
    )
    text = gen.risk_alert(line=line)
    assert "수익률: N/A" in text
    assert "위험: LOW" in text
