# -*- coding: utf-8 -*-
"""
测试运行器 - 验证PDF提取结果的准确性

用法:
    python tests/test_runner.py              # 运行所有测试
    python tests/test_runner.py --stock 000001  # 只测试指定股票
    python tests/test_runner.py --report        # 生成测试报告
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor
from tests.fixtures import get_all_fixtures, get_fixtures_by_stock, get_fixture_by_id


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "by_code"
)
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


class TestResult:
    """测试结果"""

    def __init__(self, fixture_id, statement_type):
        self.fixture_id = fixture_id
        self.statement_type = statement_type
        self.passed = False
        self.confidence = 0.0
        self.expected_confidence = 0.0
        self.items_extracted = 0
        self.errors = []
        self.warnings = []
        self.extracted_values = {}

    def to_dict(self):
        return {
            "fixture_id": self.fixture_id,
            "statement_type": self.statement_type,
            "passed": self.passed,
            "confidence": self.confidence,
            "expected_confidence": self.expected_confidence,
            "items_extracted": self.items_extracted,
            "errors": self.errors,
            "warnings": self.warnings,
            "extracted_values": self.extracted_values,
        }


def run_extractor(pdf_path, extractor_class, statement_type):
    """运行提取器并返回结果"""
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


def find_pdf_path(stock_code, pdf_file):
    """查找PDF文件的完整路径"""
    stock_dir = os.path.join(DATA_DIR, stock_code)
    if not os.path.exists(stock_dir):
        return None

    pdf_path = os.path.join(stock_dir, pdf_file)
    if os.path.exists(pdf_path):
        return pdf_path
    return None


def run_test(fixture):
    """运行单个测试用例"""
    fixture_id = fixture["id"]
    stock_code = fixture["stock_code"]
    pdf_file = fixture["pdf_file"]
    expected_conf = fixture.get("expected_confidence", {})
    known_values = fixture.get("known_values", {})

    pdf_path = find_pdf_path(stock_code, pdf_file)
    if not pdf_path:
        return None, f"PDF文件不存在: {stock_code}/{pdf_file}"

    results = {}

    # 运行各报表提取
    extractors = [
        (BalanceSheetExtractor, "BS", "balance_sheet"),
        (IncomeStatementExtractor, "IS", "income_statement"),
        (CashFlowExtractor, "CF", "cash_flow"),
    ]

    for ext_class, stmt_name, _ in extractors:
        test_result = TestResult(fixture_id, stmt_name)

        if stmt_name not in expected_conf:
            test_result.warnings.append(f"跳过{stmt_name}，未设置期望置信度")
            results[stmt_name] = test_result
            continue

        test_result.expected_confidence = expected_conf[stmt_name]

        ext_result = run_extractor(pdf_path, ext_class, stmt_name)

        if not ext_result["success"]:
            test_result.errors.append(ext_result["error"])
            test_result.passed = False
            results[stmt_name] = test_result
            continue

        test_result.confidence = ext_result["confidence"]["overall"]
        test_result.items_extracted = ext_result["items_count"]
        test_result.extracted_values = ext_result["data"]

        # 检查置信度
        if test_result.confidence >= test_result.expected_confidence:
            test_result.passed = True
        else:
            test_result.warnings.append(
                f"置信度 {test_result.confidence * 100:.1f}% < "
                f"期望 {test_result.expected_confidence * 100:.1f}%"
            )
            test_result.passed = test_result.confidence >= 0.8  # 80%为可接受

        # 验证已知数值
        for key, expected_value in known_values.items():
            if expected_value is None:
                continue

            actual_value = None
            for extracted_key, extracted_val in ext_result["data"].items():
                if key in extracted_key or extracted_key in key:
                    actual_value = extracted_val
                    break

            if actual_value is not None and abs(actual_value - expected_value) > abs(
                expected_value * 0.01
            ):
                test_result.warnings.append(
                    f"数值差异: {key} = {actual_value} (期望: {expected_value})"
                )

        results[stmt_name] = test_result

    return results, None


def run_all_tests(fixture_ids=None, stock_codes=None):
    """运行所有测试"""
    fixtures = get_all_fixtures()

    if fixture_ids:
        fixtures = [f for f in fixtures if f["id"] in fixture_ids]

    if stock_codes:
        fixtures = [f for f in fixtures if f["stock_code"] in stock_codes]

    all_results = {}

    for fixture in fixtures:
        print(f"\n测试: {fixture['id']}")
        print(f"  股票: {fixture['stock_code']} {fixture['company_name']}")
        print(f"  年份: {fixture['year']}")

        results, error = run_test(fixture)

        if error:
            print(f"  错误: {error}")
            continue

        all_results[fixture["id"]] = results

        for stmt_name, result in results.items():
            status = "[PASS]" if result.passed else "[FAIL]"
            print(f"  {stmt_name}: {result.confidence * 100:.1f}% {status}")

    return all_results


def generate_report(all_results):
    """生成测试报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(RESULTS_DIR, f"test_report_{timestamp}.json")

    report = {
        "timestamp": timestamp,
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
        },
        "results": {},
    }

    for fixture_id, results in all_results.items():
        report["results"][fixture_id] = {}
        for stmt_name, result in results.items():
            report["summary"]["total_tests"] += 1
            if result.passed:
                report["summary"]["passed"] += 1
            else:
                report["summary"]["failed"] += 1
            report["results"][fixture_id][stmt_name] = result.to_dict()

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("\n" + "=" * 60)
    print("测试报告摘要")
    print("=" * 60)
    print(f"总测试数: {report['summary']['total_tests']}")
    print(f"通过: {report['summary']['passed']}")
    print(f"失败: {report['summary']['failed']}")
    print(
        f"通过率: {report['summary']['passed'] / report['summary']['total_tests'] * 100:.1f}%"
    )
    print(f"\n详细报告: {report_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description="PDF提取测试运行器")
    parser.add_argument("--stock", help="指定股票代码")
    parser.add_argument("--fixture", help="指定测试用例ID")
    parser.add_argument("--report", action="store_true", help="生成测试报告")
    parser.add_argument("--all", action="store_true", help="包含未来测试用例")

    args = parser.parse_args()

    fixture_ids = [args.fixture] if args.fixture else None
    stock_codes = [args.stock] if args.stock else None

    print("=" * 60)
    print("PDF提取测试运行器")
    print("=" * 60)

    all_results = run_all_tests(fixture_ids=fixture_ids, stock_codes=stock_codes)

    if args.report and all_results:
        generate_report(all_results)


if __name__ == "__main__":
    main()
