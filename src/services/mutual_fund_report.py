# -*- coding: utf-8 -*-
"""渲染印度共同基金（MF_LIST）报告小节，独立于股票决策仪表盘。

共同基金没有买卖信号、技术面或 LLM 分析，只展示 NAV 与区间涨跌幅，
因此不复用 AnalysisResult/决策仪表盘渲染路径，单独成一个 markdown 小节，
由调用方（pipeline._generate_aggregate_report）拼接到日报末尾。
"""

from typing import List, Optional

from data_provider.mfapi_fetcher import MFQuote, fetch_scheme_quotes
from src.report_language import get_mutual_fund_labels, get_mutual_fund_section_title


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "--"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value}%"


def _format_quote_line(quote: MFQuote, labels: dict) -> str:
    return (
        f"**{quote.scheme_name}** ({quote.scheme_code})\n"
        f"{quote.fund_house} | {quote.scheme_category}\n"
        f"{labels['nav_label']}: ₹{quote.latest_nav:.4f} "
        f"({labels['as_of_label']} {quote.latest_date.strftime('%Y-%m-%d')})\n"
        f"{labels['day_label']} {_format_pct(quote.change_1d_pct)} | "
        f"{labels['week_label']} {_format_pct(quote.change_1w_pct)} | "
        f"{labels['month_label']} {_format_pct(quote.change_1m_pct)} | "
        f"{labels['quarter_label']} {_format_pct(quote.change_3m_pct)} | "
        f"{labels['half_year_label']} {_format_pct(quote.change_6m_pct)} | "
        f"{labels['year_label']} {_format_pct(quote.change_1y_pct)}"
    )


def build_mutual_fund_section(scheme_codes: List[str], report_language: str) -> str:
    """返回完整 markdown 小节文本；scheme_codes 为空时返回空字符串（调用方不应拼接）。

    Fail-open：单支基金拉取失败不影响其余；全部失败时仍返回小节标题
    + 无数据提示，而不是静默消失（与既有新闻面空态披露原则一致）。
    """
    if not scheme_codes:
        return ""

    labels = get_mutual_fund_labels(report_language)
    title = get_mutual_fund_section_title(report_language)
    quotes = fetch_scheme_quotes(scheme_codes)

    lines = ["", "---", "", f"## {title}", ""]
    if not quotes:
        lines.append(f"_{labels['no_data_label']}_")
        return "\n".join(lines)

    for quote in quotes:
        lines.append(_format_quote_line(quote, labels))
        lines.append("")

    return "\n".join(lines).rstrip()
