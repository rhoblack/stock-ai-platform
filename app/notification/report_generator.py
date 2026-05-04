"""ReportGenerator v0.1 — Phase 6 telegram-text formatter.

Pure-function module: takes ORM rows + risk metadata and returns plain text
suitable for the Telegram BOT API. It does not query the DB, send messages,
recompute scores, or call AI/LLM. It is just a presentation layer.

Boundary rules (Phase 6):
    * No DB writes / queries.
    * No real Telegram send (lives in ``TelegramNotifier``).
    * No score / risk recomputation.
    * No order placement.

The HOLDING reports surface ``risk_level == "HIGH"`` items above the rest.
The recommendation report preserves the engine's rank ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.db.models import (
    DataSnapshot,
    HoldingCheck,
    Recommendation,
    RecommendationRun,
)
from app.decision.risk_engine import (
    RISK_FLAG_BEARISH_MA_ALIGNMENT,
    RISK_FLAG_LOW_TECHNICAL_SCORE,
    RISK_FLAG_MA20_BREAKDOWN,
    RISK_FLAG_SCORE_DROP,
    RISK_FLAG_STOP_LOSS_NEAR,
    RISK_FLAG_VOLUME_RATIO_EXTREME,
    RISK_FLAG_VOLUME_RATIO_MISSING,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
)


_RISK_FLAG_LABEL_KR: dict[str, str] = {
    RISK_FLAG_LOW_TECHNICAL_SCORE: "기술 점수 낮음",
    RISK_FLAG_BEARISH_MA_ALIGNMENT: "역배열 추세",
    RISK_FLAG_VOLUME_RATIO_MISSING: "거래량비 미산출",
    RISK_FLAG_VOLUME_RATIO_EXTREME: "거래량 과열",
    RISK_FLAG_SCORE_DROP: "점수 급락",
    RISK_FLAG_MA20_BREAKDOWN: "20일선 이탈",
    RISK_FLAG_STOP_LOSS_NEAR: "손절 근접",
}

_RISK_LEVEL_RANK: dict[str, int] = {
    RISK_LEVEL_HIGH: 0,
    RISK_LEVEL_MEDIUM: 1,
    RISK_LEVEL_LOW: 2,
}


@dataclass(frozen=True)
class RecommendationLine:
    recommendation: Recommendation
    risk_level: str
    risk_flags: list[str]


@dataclass(frozen=True)
class HoldingLine:
    check: HoldingCheck
    risk_level: str
    risk_flags: list[str]


def extract_risk_summary(snapshot: DataSnapshot | None) -> tuple[str, list[str]]:
    """Pull (risk_level, risk_flags) out of a snapshot's market_context_json.

    Returns ``("LOW", [])`` if the snapshot or its risk_summary is missing.
    """
    if snapshot is None:
        return RISK_LEVEL_LOW, []
    context = snapshot.market_context_json or {}
    risk_summary = context.get("risk_summary") or {}
    level = risk_summary.get("level") or RISK_LEVEL_LOW
    flags = list(risk_summary.get("flags") or [])
    return level, flags


def _format_risk_text(level: str, flags: list[str]) -> str:
    if not flags:
        return level
    labels = ", ".join(_RISK_FLAG_LABEL_KR.get(flag, flag) for flag in flags)
    return f"{level} ({labels})"


def _format_return_rate(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"


def _format_score(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _sort_holding_lines_by_risk(lines: list[HoldingLine]) -> list[HoldingLine]:
    return sorted(
        lines,
        key=lambda line: (
            _RISK_LEVEL_RANK.get(line.risk_level, 99),
            line.check.symbol,
        ),
    )


class ReportGenerator:
    """Builds plain-text Telegram messages from engine results."""

    def recommendation_report(
        self,
        *,
        run: RecommendationRun,
        lines: list[RecommendationLine],
    ) -> str:
        title = f"[AI 주식 리포트] {run.run_date.isoformat()}"
        summary = run.market_summary or {}
        header_lines = [
            title,
            "",
            "▶ 시장 요약",
            f"- 후보 {summary.get('candidate_count', len(lines))}건 / "
            f"저장 {summary.get('saved_count', len(lines))}건",
            f"- universe: {summary.get('universe', 'MARKET_CAP_TOP_500')}",
            "",
        ]
        if not lines:
            header_lines.append("관찰 후보가 없습니다.")
            return "\n".join(header_lines).rstrip()

        header_lines.append(f"▶ 한국 주식 관찰 후보 TOP {len(lines)}")
        header_lines.append("")

        ordered = sorted(lines, key=lambda line: line.recommendation.rank)
        body: list[str] = []
        for line in ordered:
            rec = line.recommendation
            body.append(
                f"{rec.rank}. {rec.name} ({rec.symbol}) / "
                f"{rec.grade or '-'} / {_format_score(rec.total_score)}점"
            )
            body.append(f"   · 사유: {rec.reason or '-'}")
            body.append(
                f"   · 리스크: {_format_risk_text(line.risk_level, line.risk_flags)}"
            )
            body.append("")

        footer = ["자세한 내용은 PC 대시보드에서 확인하세요."]
        return "\n".join(header_lines + body + footer).rstrip()

    def pre_market_holding_report(
        self,
        *,
        check_date: date,
        lines: list[HoldingLine],
    ) -> str:
        return self._holding_report(
            title=f"[보유 종목 장전 점검] {check_date.isoformat()}",
            lines=lines,
        )

    def post_market_holding_report(
        self,
        *,
        check_date: date,
        lines: list[HoldingLine],
    ) -> str:
        return self._holding_report(
            title=f"[보유 종목 장후 점검] {check_date.isoformat()}",
            lines=lines,
        )

    def risk_alert(self, *, line: HoldingLine) -> str:
        check = line.check
        head = f"⚠ [위험 경고] {check.symbol}"
        details = [
            head,
            "",
            f"· 수익률: {_format_return_rate(check.return_rate)}",
            f"· 종합점수: {_format_score(check.total_score)}",
            f"· 판단: {check.decision or '-'}",
            f"· 위험: {_format_risk_text(line.risk_level, line.risk_flags)}",
            "",
            "PC 대시보드에서 즉시 확인 필요.",
        ]
        return "\n".join(details).rstrip()

    def _holding_report(
        self,
        *,
        title: str,
        lines: list[HoldingLine],
    ) -> str:
        sorted_lines = _sort_holding_lines_by_risk(list(lines))
        high_lines = [
            line for line in sorted_lines if line.risk_level == RISK_LEVEL_HIGH
        ]
        other_lines = [
            line for line in sorted_lines if line.risk_level != RISK_LEVEL_HIGH
        ]

        out: list[str] = [title, ""]
        if not sorted_lines:
            out.append("점검 대상 보유 종목이 없습니다.")
            return "\n".join(out).rstrip()

        if high_lines:
            out.append(f"⚠ 위험 경고 종목 ({len(high_lines)}건)")
            out.append("")
            out.extend(self._render_holding_block(high_lines, start_rank=1))
        if other_lines:
            out.append("▶ 일반 점검 종목")
            out.append("")
            out.extend(
                self._render_holding_block(other_lines, start_rank=len(high_lines) + 1),
            )

        out.append("자세한 내용은 PC 대시보드에서 확인하세요.")
        return "\n".join(out).rstrip()

    @staticmethod
    def _render_holding_block(
        lines: list[HoldingLine],
        *,
        start_rank: int,
    ) -> list[str]:
        out: list[str] = []
        for offset, line in enumerate(lines):
            check = line.check
            rank = start_rank + offset
            out.append(
                f"{rank}. {check.symbol} / {check.grade or '-'} / "
                f"{_format_score(check.total_score)}점"
            )
            out.append(f"   · 수익률: {_format_return_rate(check.return_rate)}")
            out.append(f"   · 판단: {check.decision or '-'}")
            out.append(
                f"   · 리스크: {_format_risk_text(line.risk_level, line.risk_flags)}"
            )
            out.append("")
        return out
