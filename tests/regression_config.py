# -*- coding: utf-8 -*-
"""
回归测试配置

用于CI/CD回归测试的股票列表和预期值
当提取结果发生变化时会自动检测
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 回归测试股票列表（每次CI必测）
REGRESSION_TEST_STOCKS = [
    {
        "stock_code": "000001",
        "pdf_file": "000001_平安银行_2024_年报.pdf",
        "year": 2024,
        "expected_items": {
            # 资产负债表关键项
            "资产总计": {"min": 55000000000, "max": 60000000000},
            "负债合计": {"min": 50000000000, "max": 55000000000},
            # 利润表关键项
            "净利润": {"min": 400000000, "max": 500000000},
        },
        "min_confidence": 0.95,
    },
    {
        "stock_code": "600000",
        "pdf_file": "600000_浦发银行_2024_年报.pdf",
        "year": 2024,
        "expected_items": {
            "资产总计": {"min": 800000000000, "max": 1000000000000},
            "净利润": {"min": 40000000, "max": 50000000},
        },
        "min_confidence": 0.95,
    },
]

# 扩展回归测试（可选，每次CI不运行）
EXTENDED_REGRESSION_STOCKS = [
    {
        "stock_code": "600036",
        "pdf_file": "600036_招商银行_2025_年报.pdf",
        "year": 2025,
        "expected_items": {
            "资产总计": {"min": 12000000000000, "max": 13000000000000},
        },
        "min_confidence": 0.80,
        "note": "LibreOffice模式",
    },
    {
        "stock_code": "600111",
        "pdf_file": "600111_北方稀土_2025_年报.pdf",
        "year": 2025,
        "expected_items": {
            "资产总计": {"min": 40000000000, "max": 50000000000},
        },
        "min_confidence": 0.80,
        "note": "LibreOffice模式",
    },
]


def get_regression_tests(extended: bool = False):
    """获取回归测试列表"""
    tests = REGRESSION_TEST_STOCKS.copy()
    if extended:
        tests.extend(EXTENDED_REGRESSION_STOCKS)
    return tests


def validate_extraction(stock_code: str, extracted_data: dict, test_config: dict) -> dict:
    """
    验证提取结果是否符合预期
    
    Args:
        stock_code: 股票代码
        extracted_data: 提取的数据 {科目名: 数值}
        test_config: 测试配置
    
    Returns:
        验证结果 {passed: bool, errors: [], warnings: []}
    """
    result = {
        "passed": True,
        "errors": [],
        "warnings": [],
        "checked_items": 0,
        "failed_items": 0,
    }
    
    expected_items = test_config.get("expected_items", {})
    
    for item_name, expected_range in expected_items.items():
        if item_name not in extracted_data:
            result["warnings"].append(f"缺失科目: {item_name}")
            result["failed_items"] += 1
            result["passed"] = False
            continue
        
        actual_value = extracted_data[item_name]
        min_val = expected_range.get("min", float("-inf"))
        max_val = expected_range.get("max", float("inf"))
        
        result["checked_items"] += 1
        
        if actual_value < min_val or actual_value > max_val:
            result["errors"].append(
                f"{item_name}: 实际值 {actual_value:,.0f} "
                f"不在预期范围 [{min_val:,.0f}, {max_val:,.0f}]"
            )
            result["failed_items"] += 1
            result["passed"] = False
    
    return result


# 用于pytest的fixture
import pytest


@pytest.fixture(params=REGRESSION_TEST_STOCKS, ids=lambda x: f"{x['stock_code']}_{x['year']}")
def regression_test_case(request):
    """回归测试fixture"""
    return request.param


if __name__ == "__main__":
    # 测试配置
    print("回归测试配置")
    print("=" * 50)
    
    tests = get_regression_tests(extended=False)
    print(f"快速回归测试: {len(tests)} 只股票")
    for t in tests:
        print(f"  - {t['stock_code']}: {t['pdf_file']}")
    
    print()
    tests_ext = get_regression_tests(extended=True)
    print(f"扩展回归测试: {len(tests_ext)} 只股票")
    
    print("\n验证函数示例:")
    sample_data = {"资产总计": 57692700000, "净利润": 445080000}
    test_config = REGRESSION_TEST_STOCKS[0]
    result = validate_extraction("000001", sample_data, test_config)
    print(f"  000001 验证结果: {result}")
