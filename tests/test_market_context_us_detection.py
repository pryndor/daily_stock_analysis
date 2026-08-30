# -*- coding: utf-8 -*-
"""detect_market() 对连字符美股代码（如 BRK-B）的识别。

背景：detect_market() 的美股正则此前只接受点号后缀（BRK.B），不接受
Yahoo Finance 实际使用的连字符形式（BRK-B），导致 BRK-B 被误判为 A 股，
触发全链路数据源 404/失败（详见 data_provider/us_index_mapping.py 的
同一修复）。此文件只测 detect_market 的 LLM 语境分类，数据路由部分见
tests/test_us_index_mapping.py。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.market_context import detect_market


class DetectMarketUsHyphenTestCase(unittest.TestCase):
    def test_hyphen_suffixed_multi_class_share_detected_as_us(self):
        self.assertEqual(detect_market("BRK-B"), "us")
        self.assertEqual(detect_market("BRK-A"), "us")

    def test_dot_suffixed_multi_class_share_still_detected_as_us(self):
        self.assertEqual(detect_market("BRK.B"), "us")

    def test_plain_us_tickers_unaffected(self):
        self.assertEqual(detect_market("AAPL"), "us")
        self.assertEqual(detect_market("TSLA"), "us")

    def test_cn_ashare_unaffected(self):
        self.assertEqual(detect_market("600519"), "cn")


if __name__ == "__main__":
    unittest.main()
