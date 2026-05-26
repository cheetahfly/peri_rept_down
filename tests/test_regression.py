# -*- coding: utf-8 -*-
"""
回归测试 - 使用pytest运行

用法:
    pytest tests/test_regression.py                    # 运行所有回归测试
    pytest tests/test_regression.py -v                 # 详细输出
    pytest tests/test_regression.py -k "000001"       # 只测试指定股票
    pytest tests/test_regression.py --extended         # 运行扩展测试
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor
from tests.regression_config import get_regression_tests, validate_items

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "by_code"
)


def find_pdf_path(stock_code, pdf_file):
    stock_dir = os.path.join(DATA_DIR, stock_code)
    if not os.path.exists(stock_dir):
        return None
    pdf_path = os.path.join(stock_dir, pdf_file)
    return pdf_path if os.path.exists(pdf_path) else None


def run_extractor(pdf_path, extractor_class):
    try:
        with PdfParser(pdf_path) as parser:
            extractor = extractor_class(parser)
            result = extractor.extract()
            confidence = extractor.calculate_confidence(result)
            return {
                "success": True,
                "data": result.get("data", {}),
                "confidence": confidence["overall"],
                "items_count": len(result.get("data", {})),
            }
    except Exception as e:
        return {
            "success": False, "data": {},
            "confidence": 0.0, "items_count": 0,
            "error": str(e),
        }


def run_statement_test(test_case, extractor_class, stmt_key):
    """Run a single statement regression test."""
    stock_code = test_case["stock_code"]
    pdf_file = test_case["pdf_file"]
    min_confidence = test_case["min_confidence"].get(stmt_key, 0.5)
    expected = test_case.get("expected_items", {}).get(stmt_key, {})

    pdf_path = find_pdf_path(stock_code, pdf_file)
    if pdf_path is None:
        pytest.skip(f"PDF文件不存在: {stock_code}/{pdf_file}")

    result = run_extractor(pdf_path, extractor_class)
    assert result["success"], f"提取失败: {result.get('error', '未知错误')}"

    # 置信度检查
    assert result["confidence"] >= min_confidence, \
        f"{stock_code} {stmt_key} 置信度 {result['confidence']:.2%} 低于预期 {min_confidence:.2%}"

    # 关键数值检查（仅在有预期值时执行，避免CID乱码误报）
    if expected:
        validation = validate_items(result["data"], expected)
        if not validation["passed"]:
            err_msgs = []
            for name, key, actual, lo, hi in validation["errors"]:
                err_msgs.append(
                    f"{name}(匹配: {key}): {actual:,.2f} 不在 [{lo:,.2f}, {hi:,.2f}]"
                )
            pytest.fail(f"{stock_code} {stmt_key} 数值验证失败: {'; '.join(err_msgs)}")


class TestRegression:
    """回归测试类"""

    @pytest.mark.parametrize("test_case", get_regression_tests(extended=False),
                             ids=lambda x: f"{x['stock_code']}_{x['year']}")
    def test_balance_sheet_regression(self, test_case):
        run_statement_test(test_case, BalanceSheetExtractor, "BS")

    @pytest.mark.parametrize("test_case", get_regression_tests(extended=False),
                             ids=lambda x: f"{x['stock_code']}_{x['year']}")
    def test_income_statement_regression(self, test_case):
        run_statement_test(test_case, IncomeStatementExtractor, "IS")

    @pytest.mark.parametrize("test_case", get_regression_tests(extended=False),
                             ids=lambda x: f"{x['stock_code']}_{x['year']}")
    def test_cash_flow_regression(self, test_case):
        run_statement_test(test_case, CashFlowExtractor, "CF")
