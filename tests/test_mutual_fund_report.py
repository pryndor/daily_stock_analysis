# -*- coding: utf-8 -*-
"""共同基金报告小节渲染单测（build_mutual_fund_section）。

覆盖：空列表不渲染小节、全部失败时仍显式披露无数据（而非静默消失，
呼应 tests/test_notification_empty_news_disclosure.py 的空态披露原则）、
正常渲染包含关键字段。
"""

import os
import sys
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.mfapi_fetcher import MFQuote
from src.services.mutual_fund_report import build_mutual_fund_section


def _make_quote(**overrides):
    defaults = dict(
        scheme_code="120503",
        scheme_name="Test ELSS Fund - Direct Plan - Growth Option",
        fund_house="Test Fund House",
        scheme_category="Equity Schemes - Test",
        latest_nav=112.63,
        latest_date=datetime(2026, 8, 28),
        change_1d_pct=0.12,
        change_1w_pct=1.5,
        change_1m_pct=3.2,
        change_3m_pct=8.1,
        change_6m_pct=15.4,
        change_1y_pct=22.0,
    )
    defaults.update(overrides)
    return MFQuote(**defaults)


class BuildMutualFundSectionTestCase(unittest.TestCase):
    def test_empty_scheme_list_returns_empty_string(self):
        self.assertEqual(build_mutual_fund_section([], "en"), "")

    def test_renders_scheme_name_nav_and_returns(self):
        with mock.patch(
            "src.services.mutual_fund_report.fetch_scheme_quotes",
            return_value=[_make_quote()],
        ):
            section = build_mutual_fund_section(["120503"], "en")

        self.assertIn("India Mutual Funds", section)
        self.assertIn("Test ELSS Fund - Direct Plan - Growth Option", section)
        self.assertIn("120503", section)
        self.assertIn("Test Fund House", section)
        self.assertIn("112.6300", section)
        self.assertIn("+22.0%", section)

    def test_all_failed_shows_explicit_no_data_disclosure_not_silent(self):
        with mock.patch(
            "src.services.mutual_fund_report.fetch_scheme_quotes",
            return_value=[],
        ):
            section = build_mutual_fund_section(["999999"], "en")

        self.assertIn("India Mutual Funds", section)
        self.assertIn("No data could be retrieved this run", section)

    def test_localizes_labels_for_zh_and_ko(self):
        with mock.patch(
            "src.services.mutual_fund_report.fetch_scheme_quotes",
            return_value=[_make_quote()],
        ):
            zh_section = build_mutual_fund_section(["120503"], "zh")
            ko_section = build_mutual_fund_section(["120503"], "ko")

        self.assertIn("印度共同基金", zh_section)
        self.assertIn("净值", zh_section)
        self.assertIn("인도 뮤추얼 펀드", ko_section)
        self.assertIn("기준가", ko_section)

    def test_negative_change_renders_without_double_sign(self):
        with mock.patch(
            "src.services.mutual_fund_report.fetch_scheme_quotes",
            return_value=[_make_quote(change_1d_pct=-1.23)],
        ):
            section = build_mutual_fund_section(["120503"], "en")
        self.assertIn("-1.23%", section)
        self.assertNotIn("+-1.23%", section)


if __name__ == "__main__":
    unittest.main()
