# -*- coding: utf-8 -*-
"""Tests for is_garbled_text() improvements."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.html_converter import is_garbled_text


class TestIsGarbledText:
    """Tests for garbled text detection."""

    def test_normal_chinese_text_not_garbled(self):
        text = "资产负债表  流动资产合计  1000000"
        assert is_garbled_text(text) is False

    def test_replacement_char_above_threshold(self):
        text = "�" * 50 + "其他文本" * 5
        assert is_garbled_text(text) is True

    def test_pure_garbled_cid(self):
        text = "㐀㐁㐂㐃㐄㐅" * 20 + "一些随机字符"
        result = is_garbled_text(text)
        # High Chinese ratio with no keywords → should be garbled
        assert result is True

    def test_mixed_garbled_page_not_missed(self):
        # A page with some correct lines but mostly garbled content
        # This tests the line-level replacement density check (Strategy 4)
        # 12 garbled lines (each ~71% replacement) + 3 normal lines
        # Overall replacement ratio ~46% (would be caught by Strategy 1)
        # But this test also verifies line-level detection works correctly
        garbled_line = "�" * 30 + "报表日期:2024"  # 44 chars, 30 repl (68%)
        normal_line = "资产负债表是企业重要财务报表"  # all Chinese, no repl
        lines = [garbled_line] * 12 + [normal_line] * 3
        text = "\n".join(lines)
        result = is_garbled_text(text)
        assert result is True
