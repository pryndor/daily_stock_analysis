# -*- coding: utf-8 -*-
"""MFApiFetcher（印度共同基金 NAV 数据源）单测。

mfapi.in 是免费公共 API，无 key；网络请求经 mock，避免测试依赖外网可用性
（离线回归约束，参见 AGENTS.md 网络相关改动章节）。真实响应结构已人工核验：
GET https://api.mfapi.in/mf/120503 -> {"meta": {...}, "data": [{"date": "DD-MM-YYYY", "nav": "..."}]}
（date 新→旧排序）。
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.mfapi_fetcher import fetch_scheme_quote, fetch_scheme_quotes


def _make_payload(latest_date: datetime, latest_nav: float, prev_nav: float):
    """构造一份可控的 mfapi.in 响应：每日一条，最新在前，覆盖 1 年以上。"""
    data = []
    nav = latest_nav
    for i in range(400):
        d = latest_date - timedelta(days=i)
        if i == 0:
            v = latest_nav
        elif i == 1:
            v = prev_nav
        else:
            v = latest_nav - i * 0.01  # 单调递减，便于断言区间涨跌方向
        data.append({"date": d.strftime("%d-%m-%Y"), "nav": f"{v:.4f}"})
    return {
        "meta": {
            "fund_house": "Test Fund House",
            "scheme_type": "Open Ended Schemes",
            "scheme_category": "Equity Schemes - Test",
            "scheme_code": 120503,
            "scheme_name": "Test ELSS Fund - Direct Plan - Growth Option",
        },
        "data": data,
    }


def _mock_response(payload, status_code=200):
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


class FetchSchemeQuoteTestCase(unittest.TestCase):
    def test_parses_meta_and_computes_trailing_returns(self):
        latest_date = datetime(2026, 8, 28)
        payload = _make_payload(latest_date, latest_nav=112.63, prev_nav=112.50)

        with mock.patch("data_provider.mfapi_fetcher.requests.get", return_value=_mock_response(payload)):
            quote = fetch_scheme_quote("120503")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.scheme_code, "120503")
        self.assertEqual(quote.scheme_name, "Test ELSS Fund - Direct Plan - Growth Option")
        self.assertEqual(quote.fund_house, "Test Fund House")
        self.assertAlmostEqual(quote.latest_nav, 112.63)
        self.assertEqual(quote.latest_date, latest_date)
        # NAV monotonically decreasing further back => all trailing windows show positive change
        self.assertGreater(quote.change_1d_pct, 0)
        self.assertGreater(quote.change_1w_pct, 0)
        self.assertGreater(quote.change_1m_pct, 0)
        self.assertGreater(quote.change_1y_pct, 0)

    def test_returns_none_on_network_error(self):
        with mock.patch("data_provider.mfapi_fetcher.requests.get", side_effect=ConnectionError("boom")):
            quote = fetch_scheme_quote("120503")
        self.assertIsNone(quote)

    def test_returns_none_on_empty_history(self):
        payload = {"meta": {"scheme_name": "Empty"}, "data": []}
        with mock.patch("data_provider.mfapi_fetcher.requests.get", return_value=_mock_response(payload)):
            quote = fetch_scheme_quote("999999")
        self.assertIsNone(quote)

    def test_returns_none_for_blank_scheme_code(self):
        self.assertIsNone(fetch_scheme_quote(""))
        self.assertIsNone(fetch_scheme_quote("   "))

    def test_fetch_scheme_quotes_skips_failed_entries(self):
        good_payload = _make_payload(datetime(2026, 8, 28), 112.63, 112.50)

        def side_effect(url, timeout):
            if "120503" in url:
                return _mock_response(good_payload)
            raise ConnectionError("boom")

        with mock.patch("data_provider.mfapi_fetcher.requests.get", side_effect=side_effect):
            quotes = fetch_scheme_quotes(["120503", "000000"])

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].scheme_code, "120503")


if __name__ == "__main__":
    unittest.main()
