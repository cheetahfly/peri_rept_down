# -*- coding: utf-8 -*-
"""
回归测试配置

用于CI/CD回归测试的股票列表和预期值
当提取结果发生变化时会自动检测

注意：预期值使用子串匹配，可应对CID字体PDF中科目名的部分乱码。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


REGRESSION_TEST_STOCKS = [
    {
        "stock_code": "000001",
        "pdf_file": "000001_平安银行_平安银行：2025年年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.80, "IS": 0.80, "CF": 0.65},
        "expected_items": {
            "BS": {"资产总计": (4000000, 8000000), "负债合计": (4000000, 7000000)},
            "IS": {"营业收入": (80000, 180000), "净利润": (30000, 60000)},
            "CF": {},
        },
        "note": "平安银行 - 银行，提取稳定",
    },
    {
        "stock_code": "601318",
        "pdf_file": "601318_中国平安_中国平安：中国平安2025年年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.80, "IS": 0.90, "CF": 0.65},
        "expected_items": {
            "BS": {"资产总计": (10000000, 18000000), "负债合计": (9000000, 16000000)},
            "IS": {"营业收入": (800000, 1300000), "净利润": (100000, 170000)},
            "CF": {},
        },
        "note": "中国平安 - 保险，CID字体但提取稳定",
    },
    {
        "stock_code": "600887",
        "pdf_file": "600887_伊利股份_伊利股份：内蒙古伊利实业集团股份有限公司2025年年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.80, "IS": 0.80, "CF": 0.60},
        "expected_items": {
            "BS": {"资产总计": (100000000000, 200000000000)},
            "IS": {"营业收入": (80000000000, 150000000000), "净利润": (8000000000, 15000000000)},
            "CF": {},
        },
        "note": "伊利股份 - 食品饮料",
    },
    {
        "stock_code": "600036",
        "pdf_file": "600036_招商银行_招商银行：招商银行股份有限公司2025年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.80, "IS": 0.80, "CF": 0.65},
        "expected_items": {
            "BS": {"资产总计": (10000000, 16000000), "负债合计": (9000000, 14000000)},
            "IS": {"营业收入": (250000, 420000), "净利润": (110000, 190000)},
            "CF": {},
        },
        "note": "招商银行 - 银行",
    },
    {
        "stock_code": "002475",
        "pdf_file": "002475_立讯精密_2025_年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.70, "IS": 0.70, "CF": 0.50},
        "expected_items": {
            "BS": {},
            "IS": {},
            "CF": {},
        },
        "note": "立讯精密 - 电子制造，CID字体",
    },
]

EXTENDED_REGRESSION_STOCKS = [
    {
        "stock_code": "000002",
        "pdf_file": "000002_万科A_万科A：2025年年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.70, "IS": 0.70, "CF": 0.50},
        "expected_items": {"BS": {}, "IS": {}, "CF": {}},
        "note": "万科A - 房地产，CID字体",
    },
    {
        "stock_code": "600031",
        "pdf_file": "600031_三一重工_三一重工：三一重工股份有限公司2025年年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.70, "IS": 0.70, "CF": 0.50},
        "expected_items": {"BS": {}, "IS": {}, "CF": {}},
        "note": "三一重工 - 工程机械",
    },
    {
        "stock_code": "600585",
        "pdf_file": "600585_海螺水泥_海螺水泥：2025年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.50, "IS": 0.50, "CF": 0.50},
        "expected_items": {"BS": {}, "IS": {}, "CF": {}},
        "note": "海螺水泥 - 建材，CID字体",
    },
    {
        "stock_code": "600519",
        "pdf_file": "600519_贵州茅台_贵州茅台：贵州茅台2025年年度报告.PDF",
        "year": 2025,
        "min_confidence": {"BS": 0.40, "IS": 0.40, "CF": 0.40},
        "expected_items": {"BS": {}, "IS": {}, "CF": {}},
        "note": "贵州茅台 - 白酒，CID字体严重",
    },
]


def get_regression_tests(extended: bool = False):
    tests = REGRESSION_TEST_STOCKS.copy()
    if extended:
        tests.extend(EXTENDED_REGRESSION_STOCKS)
    return tests


def validate_items(extracted_data: dict, expected: dict) -> dict:
    """
    验证提取值是否在预期范围内（子串匹配处理CID乱码）

    Returns:
        {"passed": bool, "checked": int, "errors": [(name, actual, min, max)], "warnings": [str]}
    """
    result = {"passed": True, "checked": 0, "errors": [], "warnings": []}

    for item_name, (min_val, max_val) in expected.items():
        # 子串匹配
        matched = None
        matched_key = None
        for k in extracted_data:
            if item_name in k or k in item_name:
                matched = extracted_data[k]
                matched_key = k
                break

        if matched is None:
            result["warnings"].append(f"未匹配到科目: {item_name}")
            continue

        result["checked"] += 1
        if matched < min_val or matched > max_val:
            result["errors"].append((item_name, matched_key, matched, min_val, max_val))
            result["passed"] = False

    return result


import pytest


@pytest.fixture(params=REGRESSION_TEST_STOCKS, ids=lambda x: f"{x['stock_code']}_{x['year']}")
def regression_test_case(request):
    return request.param
