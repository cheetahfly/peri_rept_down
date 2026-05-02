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

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor
from tests.regression_config import get_regression_tests, validate_extraction


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "by_code"
)


def find_pdf_path(stock_code, pdf_file):
    """查找PDF文件"""
    stock_dir = os.path.join(DATA_DIR, stock_code)
    if not os.path.exists(stock_dir):
        return None
    pdf_path = os.path.join(stock_dir, pdf_file)
    return pdf_path if os.path.exists(pdf_path) else None


class TestRegression:
    """回归测试类"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """设置"""
        self.data_dir = DATA_DIR
    
    def _run_extractor(self, pdf_path, extractor_class):
        """运行提取器"""
        try:
            with PdfParser(pdf_path) as parser:
                extractor = extractor_class(parser)
                result = extractor.extract()
                confidence = extractor.calculate_confidence(result)
                return {
                    "success": True,
                    "data": result.get("data", {}),
                    "confidence": confidence,
                    "items_count": len(result.get("data", {})),
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "confidence": {"overall": 0.0},
                "items_count": 0,
                "data": {},
            }
    
    @pytest.mark.parametrize("test_case", get_regression_tests(extended=False),
                             ids=lambda x: f"{x['stock_code']}_{x['year']}")
    def test_balance_sheet_regression(self, test_case):
        """测试资产负债表回归"""
        stock_code = test_case["stock_code"]
        pdf_file = test_case["pdf_file"]
        min_confidence = test_case["min_confidence"]
        expected_items = test_case["expected_items"]
        
        pdf_path = find_pdf_path(stock_code, pdf_file)
        if pdf_path is None:
            pytest.skip(f"PDF文件不存在: {stock_code}/{pdf_file}")
        
        result = self._run_extractor(pdf_path, BalanceSheetExtractor)
        
        assert result["success"], f"提取失败: {result.get('error', '未知错误')}"
        
        confidence = result["confidence"]["overall"]
        assert confidence >= min_confidence, \
            f"{stock_code} 置信度 {confidence:.2%} 低于预期 {min_confidence:.2%}"
        
        # 验证关键数值
        if expected_items:
            validation = validate_extraction(stock_code, result["data"], test_case)
            for item_name, range_spec in expected_items.items():
                if item_name in result["data"]:
                    actual = result["data"][item_name]
                    min_val = range_spec.get("min", float("-inf"))
                    max_val = range_spec.get("max", float("inf"))
                    assert min_val <= actual <= max_val, \
                        f"{stock_code} {item_name}: {actual:,.0f} 不在范围 [{min_val:,.0f}, {max_val:,.0f}]"
    
    @pytest.mark.parametrize("test_case", get_regression_tests(extended=False),
                             ids=lambda x: f"{x['stock_code']}_{x['year']}")
    def test_income_statement_regression(self, test_case):
        """测试利润表回归"""
        stock_code = test_case["stock_code"]
        pdf_file = test_case["pdf_file"]
        
        pdf_path = find_pdf_path(stock_code, pdf_file)
        if pdf_path is None:
            pytest.skip(f"PDF文件不存在: {stock_code}/{pdf_file}")
        
        result = self._run_extractor(pdf_path, IncomeStatementExtractor)
        
        # 利润表置信度检查（宽松一些）
        if result["success"]:
            confidence = result["confidence"]["overall"]
            assert confidence >= 0.7, \
                f"{stock_code} 利润表置信度 {confidence:.2%} 过低"
    
    @pytest.mark.parametrize("test_case", get_regression_tests(extended=False),
                             ids=lambda x: f"{x['stock_code']}_{x['year']}")
    def test_cash_flow_regression(self, test_case):
        """测试现金流量表回归"""
        stock_code = test_case["stock_code"]
        pdf_file = test_case["pdf_file"]
        
        pdf_path = find_pdf_path(stock_code, pdf_file)
        if pdf_path is None:
            pytest.skip(f"PDF文件不存在: {stock_code}/{pdf_file}")
        
        result = self._run_extractor(pdf_path, CashFlowExtractor)
        
        if result["success"]:
            confidence = result["confidence"]["overall"]
            assert confidence >= 0.7, \
                f"{stock_code} 现金流量表置信度 {confidence:.2%} 过低"


def run_regression_tests():
    """直接运行回归测试（不使用pytest）"""
    import json
    from datetime import datetime
    
    tests = get_regression_tests(extended=False)
    results = []
    
    for test_case in tests:
        stock_code = test_case["stock_code"]
        pdf_file = test_case["pdf_file"]
        
        print(f"\n测试 {stock_code} {test_case['year']}...")
        
        pdf_path = find_pdf_path(stock_code, pdf_file)
        if pdf_path is None:
            print(f"  跳过: PDF不存在")
            results.append({
                "stock_code": stock_code,
                "status": "SKIP",
                "reason": "PDF不存在"
            })
            continue
        
        try:
            with PdfParser(pdf_path) as parser:
                # 测试资产负债表
                bs_extractor = BalanceSheetExtractor(parser)
                bs_result = bs_extractor.extract()
                bs_confidence = bs_extractor.calculate_confidence(bs_result)
                
                print(f"  资产负债表: {bs_confidence['overall']:.2%}")
                
                # 验证关键值
                validation = validate_extraction(stock_code, bs_result.get("data", {}), test_case)
                
                results.append({
                    "stock_code": stock_code,
                    "status": "PASS" if validation["passed"] else "FAIL",
                    "confidence": bs_confidence["overall"],
                    "validation": validation,
                })
                
        except Exception as e:
            print(f"  错误: {e}")
            results.append({
                "stock_code": stock_code,
                "status": "ERROR",
                "error": str(e),
            })
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("回归测试摘要")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")
    print(f"错误: {errors}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="回归测试")
    parser.add_argument("--extended", action="store_true", help="运行扩展回归测试")
    parser.add_argument("--pytest", action="store_true", help="使用pytest运行")
    args = parser.parse_args()
    
    if args.pytest:
        pytest.main([__file__, "-v"])
    else:
        run_regression_tests()
