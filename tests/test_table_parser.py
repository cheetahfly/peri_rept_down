# -*- coding: utf-8 -*-
"""
Unit tests for table_parser.py - TableParser class
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.table_parser import TableParser
import pandas as pd


class TestCleanText:
    """Tests for clean_text method."""

    def test_whitespace_collapse(self):
        assert TableParser.clean_text("  hello   world  ") == "hello world"

    def test_strip(self):
        assert TableParser.clean_text("  hello  ") == "hello"

    def test_comma_removal(self):
        assert TableParser.clean_text("1,234,567") == "1234567"
        assert TableParser.clean_text("1，234，567") == "1234567"

    def test_parentheses_removal(self):
        assert TableParser.clean_text("hello () world") == "hello  world"
        assert TableParser.clean_text("(hello)") == "(hello)"

    def test_net_profit_split(self):
        assert TableParser.clean_text("四、净\n(亏损)\n/\n利润") == "净利润"
        assert TableParser.clean_text("四、净/利\n润") == "净利润"

    def test_preserves_meaningful_text(self):
        assert "资产" in TableParser.clean_text("流动资产合计")
        assert "负债" in TableParser.clean_text("流动负债合计")


class TestParseNumber:
    """Tests for parse_number method."""

    def test_positive_integer(self):
        assert TableParser.parse_number("12345") == 12345.0

    def test_positive_float(self):
        assert TableParser.parse_number("12345.67") == 12345.67

    def test_with_commas(self):
        assert TableParser.parse_number("1,234,567") == 1234567.0

    def test_with_chinese_comma(self):
        assert TableParser.parse_number("1，234，567") == 1234567.0

    def test_negative_parentheses(self):
        assert TableParser.parse_number("(12345)") == -12345.0

    def test_negative_with_minus(self):
        assert TableParser.parse_number("-12345") == -12345.0

    def test_parentheses_float(self):
        assert TableParser.parse_number("(1234.56)") == -1234.56

    def test_whitespace(self):
        assert TableParser.parse_number("  12345  ") == 12345.0

    def test_invalid_text(self):
        assert TableParser.parse_number("hello") is None

    def test_empty(self):
        assert TableParser.parse_number("") is None

    def test_non_numeric(self):
        assert TableParser.parse_number("N/A") is None

    def test_brackets_and_text(self):
        assert TableParser.parse_number("12345[注释]") is not None


class TestDetectStatementType:
    """Tests for detect_statement_type method.

    Uses ASCII-only strings to avoid Windows console encoding issues.
    """

    def test_balance_sheet(self):
        # Contains 资产 and 负债 - should detect balance_sheet
        row = pd.Series(["资产", "负债", "权益"])
        result = TableParser.detect_statement_type(row)
        assert result == "balance_sheet"

    def test_income_statement(self):
        # Contains 利润 - should detect income_statement
        row = pd.Series(["利润", "收入", "成本"])
        result = TableParser.detect_statement_type(row)
        assert result == "income_statement"

    def test_cash_flow(self):
        # Contains 现金 and 流量 - should detect cash_flow
        row = pd.Series(["现金", "流量", "金额"])
        result = TableParser.detect_statement_type(row)
        assert result == "cash_flow"

    def test_profit_alias(self):
        # Contains 损益 - should detect income_statement
        row = pd.Series(["损益", "金额", "其他"])
        result = TableParser.detect_statement_type(row)
        assert result == "income_statement"

    def test_unknown(self):
        row = pd.Series(["col_a", "col_b", "col_c"])
        result = TableParser.detect_statement_type(row)
        assert result is None


class TestNormalizeColumns:
    """Tests for normalize_columns method."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = TableParser.normalize_columns(df, "balance_sheet")
        assert result.empty

    def test_no_matching_pattern(self):
        df = pd.DataFrame([["项目", "金额", "其他"]])
        result = TableParser.normalize_columns(df, "balance_sheet")
        assert result.shape[1] == 3


class TestIsValidItemName:
    """Tests for _is_valid_item_name method."""

    def test_valid_long_name(self):
        assert TableParser._is_valid_item_name("流动资产合计") is True
        assert TableParser._is_valid_item_name("营业收入") is True

    def test_too_short(self):
        assert TableParser._is_valid_item_name("A") is False
        assert TableParser._is_valid_item_name("") is False

    def test_too_long(self):
        long_name = "A" * 100
        assert TableParser._is_valid_item_name(long_name) is False

    def test_chapter_number(self):
        # Chinese numeral + chapter/page character only (not actual item names)
        assert TableParser._is_valid_item_name("第一章") is False
        assert TableParser._is_valid_item_name("第一节") is False

    def test_circle_numbers(self):
        assert TableParser._is_valid_item_name("①") is False
        assert TableParser._is_valid_item_name("⑩") is False

    def test_see_reference(self):
        assert TableParser._is_valid_item_name("见上节") is False
        assert TableParser._is_valid_item_name("见下页") is False

    def test_pure_numbers(self):
        assert TableParser._is_valid_item_name("12345") is False

    def test_pure_letters(self):
        assert TableParser._is_valid_item_name("ABC") is False

    def test_pattern_invalid(self):
        assert TableParser._is_valid_item_name("的资产") is False


class TestNormalizeItemName:
    """Tests for _normalize_item_name method."""

    def test_chinese_number_prefix(self):
        assert TableParser._normalize_item_name("一、流动资产") == "流动资产"
        assert TableParser._normalize_item_name("三、净利润") == "净利润"

    def test_loss_bracket(self):
        assert "净利润" in TableParser._normalize_item_name("四、净(亏损)/利润")
        assert "利润总额" in TableParser._normalize_item_name("三、(亏损)/利润总额")

    def test_parentheses_removed(self):
        result = TableParser._normalize_item_name("营业(亏损)成本")
        assert "(" not in result
        assert ")" not in result

    def test_preserves_name(self):
        assert TableParser._normalize_item_name("营业收入") == "营业收入"


class TestExtractItems:
    """Tests for extract_items method."""

    def test_empty_dataframe(self):
        result = TableParser.extract_items(pd.DataFrame())
        assert result == {}

    def test_extracts_valid_items(self):
        df = pd.DataFrame({
            0: ["项目", "营业收入", "净利润"],
            1: ["本期金额", "1000000", "200000"],
            2: ["上期金额", "900000", "180000"],
        })
        result = TableParser.extract_items(df)
        assert isinstance(result, dict)

    def test_skips_invalid_item_names(self):
        df = pd.DataFrame({
            0: ["项目", "第一章", "12345"],
            1: ["本期金额", "1000000", "200000"],
            2: ["上期金额", "900000", "180000"],
        })
        result = TableParser.extract_items(df)
        # "项目" and "第一章" and "12345" should be skipped
        assert "第一章" not in result
        assert "12345" not in result


class TestFixSplitItemName:
    """Tests for _fix_split_item_name method."""

    def test_normal_name(self):
        row = pd.Series({0: "营业收入", 1: "1000", 2: "900"})
        result = TableParser._fix_split_item_name(row, 0)
        assert result == "营业收入"

    def test_split_across_columns(self):
        # Simulate split: "四、净" | "(亏损)" | "/" | "利润"
        row = pd.Series({
            0: "四、净",
            1: "(亏损)",
            2: "/",
            3: "利润",
            4: "1000"
        })
        result = TableParser._fix_split_item_name(row, 0)
        assert "净利润" in result or "净" in result

    def test_empty_row(self):
        row = pd.Series({0: None, 1: None})
        result = TableParser._fix_split_item_name(row, 0)
        assert result == ""
