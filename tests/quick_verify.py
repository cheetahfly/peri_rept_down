# -*- coding: utf-8 -*-
"""
快速验证脚本 - 快速验证提取结果

用法:
    python tests/quick_verify.py
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "by_code")


def verify_stock(stock_code, company_name):
    """验证单只股票的提取结果"""
    results = {}
    
    pdf_2024 = os.path.join(DATA_DIR, stock_code, f"{stock_code}_{company_name}_2024_年报.pdf")
    pdf_2025 = os.path.join(DATA_DIR, stock_code, f"{stock_code}_{company_name}_2025_年报.pdf")
    
    extractors = [
        (BalanceSheetExtractor, "BS"),
        (IncomeStatementExtractor, "IS"),
        (CashFlowExtractor, "CF"),
    ]
    
    for year, pdf_path in [("2024", pdf_2024), ("2025", pdf_2025)]:
        if not os.path.exists(pdf_path):
            continue
        
        print(f"\n{stock_code} {company_name} {year}:")
        
        with PdfParser(pdf_path) as parser:
            for ext_class, stmt_name in extractors:
                ext = ext_class(parser)
                result = ext.extract()
                conf = ext.calculate_confidence(result)
                status = "PASS" if conf["overall"] >= 1.0 else "WARN"
                print(f"  {stmt_name}: {conf['overall']*100:.1f}% [{status}]")
                results[f"{stock_code}_{year}_{stmt_name}"] = conf["overall"]
    
    return results


def main():
    print("=" * 60)
    print("Quick Verification")
    print("=" * 60)
    
    all_results = {}
    
    # 验证已下载的股票
    stocks = [
        ("000001", "平安银行"),
        ("600000", "浦发银行"),
    ]
    
    for stock_code, company_name in stocks:
        try:
            results = verify_stock(stock_code, company_name)
            all_results.update(results)
        except Exception as e:
            print(f"\nError verifying {stock_code}: {e}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for v in all_results.values() if v >= 1.0)
    total = len(all_results)
    print(f"Total: {total}, Passed: {passed}, Rate: {passed/total*100:.1f}%")
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(os.path.dirname(__file__), "results", f"quick_verify_{timestamp}.json")
    os.makedirs(os.path.dirname(result_file), exist_ok=True)
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "results": all_results,
            "summary": {
                "total": total,
                "passed": passed,
                "rate": passed/total if total > 0 else 0
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nResults saved to: {result_file}")


if __name__ == "__main__":
    main()
