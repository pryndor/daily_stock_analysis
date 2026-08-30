# -*- coding: utf-8 -*-
"""
===================================
MFApiFetcher - 印度共同基金 NAV 数据源
===================================

数据来源：mfapi.in（免费、无需 key，聚合 AMFI 官方 NAV 数据）
定位：独立于股票分析主流程，仅用于 MF_LIST 中配置的 AMFI scheme code

关键说明：
- 共同基金没有交易所行情（无 OHLC/K 线/技术指标），因此不复用
  data_provider/base.py 的 BaseFetcher 股票路由体系，独立成模块。
- fail-open：任何网络/解析失败均返回 None 并记录日志，不抛出异常，
  不中断股票分析主流程。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

MFAPI_BASE_URL = "https://api.mfapi.in/mf"
_REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class MFNavPoint:
    date: datetime
    nav: float


@dataclass(frozen=True)
class MFQuote:
    """一支基金的最新 NAV 与区间涨跌幅（百分比，保留 2 位小数）。"""

    scheme_code: str
    scheme_name: str
    fund_house: str
    scheme_category: str
    latest_nav: float
    latest_date: datetime
    change_1d_pct: Optional[float]
    change_1w_pct: Optional[float]
    change_1m_pct: Optional[float]
    change_3m_pct: Optional[float]
    change_6m_pct: Optional[float]
    change_1y_pct: Optional[float]


def _parse_history(raw_data: List[Dict]) -> List[MFNavPoint]:
    """解析 mfapi.in 的 data 数组（新→旧排序），跳过无法解析的行。"""
    points: List[MFNavPoint] = []
    for row in raw_data:
        try:
            date = datetime.strptime(row["date"], "%d-%m-%Y")
            nav = float(row["nav"])
        except (KeyError, ValueError, TypeError):
            continue
        points.append(MFNavPoint(date=date, nav=nav))
    return points


def _nav_at_or_before(points: List[MFNavPoint], target_date: datetime) -> Optional[MFNavPoint]:
    """points 按新→旧排序；返回第一个日期 <= target_date 的点。"""
    for point in points:
        if point.date <= target_date:
            return point
    return None


def _pct_change(latest: float, previous: Optional[float]) -> Optional[float]:
    if previous is None or previous == 0:
        return None
    return round((latest - previous) / previous * 100, 2)


def fetch_scheme_quote(scheme_code: str) -> Optional[MFQuote]:
    """获取单支基金（AMFI scheme code）的最新 NAV 及 1D/1W/1M/3M/6M/1Y 涨跌幅。

    Fail-open：网络异常、非 200、JSON 解析失败或无有效 NAV 历史时返回 None，
    调用方应据此跳过该基金，不影响其余基金或股票分析流程。
    """
    scheme_code = str(scheme_code).strip()
    if not scheme_code:
        return None

    url = f"{MFAPI_BASE_URL}/{scheme_code}"
    try:
        response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        logger.warning("[MFApi] 获取基金 %s 数据失败: %s", scheme_code, e)
        return None

    meta = payload.get("meta") or {}
    points = _parse_history(payload.get("data") or [])
    if not points:
        logger.warning("[MFApi] 基金 %s 无有效 NAV 历史数据", scheme_code)
        return None

    latest = points[0]
    prev_nav = points[1].nav if len(points) > 1 else None

    def ref_nav(days: int) -> Optional[float]:
        point = _nav_at_or_before(points, latest.date - timedelta(days=days))
        return point.nav if point else None

    return MFQuote(
        scheme_code=scheme_code,
        scheme_name=str(meta.get("scheme_name") or scheme_code),
        fund_house=str(meta.get("fund_house") or ""),
        scheme_category=str(meta.get("scheme_category") or ""),
        latest_nav=latest.nav,
        latest_date=latest.date,
        change_1d_pct=_pct_change(latest.nav, prev_nav),
        change_1w_pct=_pct_change(latest.nav, ref_nav(7)),
        change_1m_pct=_pct_change(latest.nav, ref_nav(30)),
        change_3m_pct=_pct_change(latest.nav, ref_nav(91)),
        change_6m_pct=_pct_change(latest.nav, ref_nav(182)),
        change_1y_pct=_pct_change(latest.nav, ref_nav(365)),
    )


def fetch_scheme_quotes(scheme_codes: List[str]) -> List[MFQuote]:
    """批量获取，单个失败不影响其余（fail-open），按输入顺序返回成功项。"""
    quotes: List[MFQuote] = []
    for code in scheme_codes:
        quote = fetch_scheme_quote(code)
        if quote is not None:
            quotes.append(quote)
    return quotes
