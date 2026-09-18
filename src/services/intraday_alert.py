# -*- coding: utf-8 -*-
"""盘中信号提醒：对已有决策仪表盘 + 盘中决策护栏(phase_decision)输出的复用，

不新增分析计算——只在 decision_type=buy/sell 且护栏给出明确 immediate_action
时，从已计算好的 sniper_points/phase_decision 里挑选字段拼一条精简提醒，
通过既有的 route_type="alert" 通道发送（与 src/services/alert_worker.py
的价格告警复用同一条通知路径，互不冲突）。

Opt-in（INTRADAY_ALERT_ENABLED），默认关闭；单股拼装/发送失败不影响其余
股票或主报告推送（fail-open）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from src.report_language import get_report_labels, get_signal_level, normalize_report_language

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult
    from src.notification import NotificationService

logger = logging.getLogger(__name__)

_ACTIONABLE_DECISION_TYPES = {"buy", "sell"}


def _clean_value(value: object) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    return text


def build_intraday_alert_text(result: "AnalysisResult") -> Optional[str]:
    """Return alert markdown for one stock, or None when not actionable/incomplete."""
    if result.decision_type not in _ACTIONABLE_DECISION_TYPES:
        return None

    dashboard = result.dashboard or {}
    phase_decision = dashboard.get("phase_decision") or {}
    immediate_action = _clean_value(phase_decision.get("immediate_action"))
    if not immediate_action:
        return None

    language = normalize_report_language(result.report_language)
    labels = get_report_labels(language)
    signal_text, signal_emoji, _ = get_signal_level(result.operation_advice, result.sentiment_score, language)

    sniper = result.get_sniper_points()
    lines = [f"{signal_emoji} **{result.name} ({result.code})** · {signal_text}", ""]
    lines.append(f"{labels['immediate_action_label']}: {immediate_action}")

    action_window = _clean_value(phase_decision.get("action_window"))
    if action_window:
        lines.append(f"{labels['action_window_label']}: {action_window}")

    for key, label_key in (
        ("ideal_buy", "ideal_buy_label"),
        ("stop_loss", "stop_loss_label"),
        ("take_profit", "take_profit_label"),
        ("expected_high", "expected_high_label"),
        ("expected_low", "expected_low_label"),
    ):
        value = _clean_value(sniper.get(key))
        if value:
            lines.append(f"{labels[label_key]}: {value}")

    next_check_time = _clean_value(phase_decision.get("next_check_time"))
    if next_check_time:
        lines.append(f"{labels['next_check_time_label']}: {next_check_time}")

    lines.append("")
    lines.append(labels["not_investment_advice"])
    return "\n".join(lines)


def send_intraday_alerts(results: List["AnalysisResult"], notifier: "NotificationService") -> int:
    """Send one alert per actionable stock. Returns count of alerts attempted.

    Fail-open: a single stock's formatting/send failure is logged and skipped,
    it never raises out to the caller (the main report pipeline).
    """
    sent = 0
    for result in results:
        try:
            alert_text = build_intraday_alert_text(result)
            if not alert_text:
                continue
            notifier.send_with_results(
                alert_text,
                route_type="alert",
                dedup_key=f"intraday_alert:{result.code}:{result.decision_type}",
                cooldown_key=f"intraday_alert:{result.code}",
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001 - never let one stock break the batch
            logger.warning("[IntradayAlert] Failed to send alert for %s: %s", getattr(result, "code", "?"), exc)
    return sent
