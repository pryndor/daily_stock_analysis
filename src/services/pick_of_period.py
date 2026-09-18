# -*- coding: utf-8 -*-
"""Pick of the Day / Pick of the Month.

Reuses the existing 0-100 sentiment_score already computed per stock by the
main analysis pipeline (src/analyzer.py) and already persisted per run by
src/services/history_service.py — no new scoring logic, just ranking and a
compact markdown section appended to the daily report (same pattern as
src/services/mutual_fund_report.py's fail-open, additive-only section).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.report_language import get_report_labels, get_signal_level, normalize_report_language

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)

_EXCLUDED_REPORT_TYPES = {"market_review"}


def _format_pick_line(
    rank: int,
    *,
    code: str,
    name: str,
    score: Optional[float],
    advice: Any,
    language: str,
    labels: Dict[str, str],
) -> str:
    signal_text, signal_emoji, _ = get_signal_level(advice, score, language)
    score_text = f"{int(score)}" if isinstance(score, (int, float)) else "--"
    return f"{rank}. {signal_emoji} **{name} ({code})** — {labels['score_label']}: {score_text} · {signal_text}"


def build_pick_of_day_section(results: List["AnalysisResult"], report_language: str, top_n: int = 3) -> str:
    """Top-scoring stocks from THIS run's results. Empty string when nothing qualifies."""
    if not results:
        return ""

    language = normalize_report_language(report_language)
    labels = get_report_labels(language)

    candidates = [r for r in results if getattr(r, "success", True) and isinstance(getattr(r, "sentiment_score", None), (int, float))]
    if not candidates:
        return ""

    top = sorted(candidates, key=lambda r: r.sentiment_score, reverse=True)[:top_n]
    lines = ["", "---", "", f"## 🏆 {labels['pick_of_day_heading']}", ""]
    for rank, result in enumerate(top, 1):
        lines.append(
            _format_pick_line(
                rank,
                code=result.code,
                name=result.name,
                score=result.sentiment_score,
                advice=result.operation_advice,
                language=language,
                labels=labels,
            )
        )
    return "\n".join(lines)


def build_pick_of_month_section(report_language: str, top_n: int = 3) -> str:
    """Best score-per-stock across all runs so far this calendar month.

    Queries existing history storage (HistoryService) rather than computing
    anything new. Fail-open: any query error returns "" so the caller can
    append it unconditionally without risking the main report.
    """
    language = normalize_report_language(report_language)
    labels = get_report_labels(language)

    try:
        from src.services.history_service import HistoryService

        today = date.today()
        month_start = today.replace(day=1).isoformat()
        history = HistoryService()
        page = 1
        best_per_stock: Dict[str, Dict[str, Any]] = {}
        while True:
            result = history.get_history_list(
                start_date=month_start,
                end_date=today.isoformat(),
                page=page,
                limit=200,
            )
            items = result.get("items") or []
            for item in items:
                if item.get("report_type") in _EXCLUDED_REPORT_TYPES:
                    continue
                score = item.get("sentiment_score")
                if not isinstance(score, (int, float)):
                    continue
                code = item.get("stock_code")
                if not code:
                    continue
                current_best = best_per_stock.get(code)
                if current_best is None or score > current_best["sentiment_score"]:
                    best_per_stock[code] = item
            total = result.get("total") or 0
            if page * 200 >= total or not items:
                break
            page += 1
    except Exception as exc:
        logger.warning("[PickOfPeriod] Failed to query month history: %s", exc)
        return ""

    if not best_per_stock:
        return ""

    top = sorted(best_per_stock.values(), key=lambda item: item["sentiment_score"], reverse=True)[:top_n]
    lines = ["", "---", "", f"## 📅 {labels['pick_of_month_heading']}", ""]
    for rank, item in enumerate(top, 1):
        lines.append(
            _format_pick_line(
                rank,
                code=item.get("stock_code", ""),
                name=item.get("stock_name", ""),
                score=item.get("sentiment_score"),
                advice=item.get("operation_advice"),
                language=language,
                labels=labels,
            )
        )
    return "\n".join(lines)
