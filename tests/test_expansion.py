# -*- coding: utf-8 -*-
"""
扩展测试 - 测试更多股票

支持股票列表:
- 000001 平安银行 (银行)
- 000002 万科A (房地产)
- 600000 浦发银行 (银行)
- 600036 招商银行 (银行)
- 600098 广州发展 (公用事业)
- 600111 北方稀土 (有色金属)
- 600550 保变电气 (电气设备)
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor


# 扩展测试配置
EXPANSION_TEST_STOCKS = {
    "000001": {
        "name": "平安银行",
        "industry": "银行",
        "pdf_2024": "000001_平安银行_2024_年报.pdf",
        "pdf_2025": "000001_平安银行_2025_年报.pdf",
        "expected_confidence": 1.0,
        "key_values": {
            "资产总计": 57692700000,
            "净利润": 445080000,
        }
    },
    "000002": {
        "name": "万科A",
        "industry": "房地产",
        "pdf_2024": None,  # 暂无2024年报
        "pdf_2025": "000002_万科A_2025_年报.pdf",
        "expected_confidence": 0.8,  # 期望80%以上
        "key_values": {
            "资产总计": None,  # 待验证
        }
    },
    "600000": {
        "name": "浦发银行",
        "industry": "银行",
        "pdf_2024": "600000_浦发银行_2024_年报.pdf",
        "pdf_2025": "600000_浦发银行_2025_年报.pdf",
        "expected_confidence": 1.0,
        "key_values": {
            "资产总计": 909077000000,
            "净利润": 45835000,
        }
    },
    "600036": {
        "name": "招商银行",
        "industry": "银行",
        "pdf_2024": None,
        "pdf_2025": "600036_招商银行_2025_年报.pdf",
        "expected_confidence": 0.8,  # LibreOffice模式
        "key_values": {
            "资产总计": 12657151000000,
        },
        "parser_mode": "libreoffice"  # 使用LibreOffice解析
    },
    "600098": {
        "name": "广州发展",
        "industry": "公用事业",
        "pdf_2024": None,
        "pdf_2025": "600098_广州发展_unknown_年报.pdf",
        "expected_confidence": 0.7,  # 未知格式
        "key_values": {}
    },
    "600111": {
        "name": "北方稀土",
        "industry": "有色金属",
        "pdf_2024": None,
        "pdf_2025": "600111_北方稀土_2025_年报.pdf",
        "expected_confidence": 0.8,
        "key_values": {
            "资产总计": 47317652807,
        },
        "parser_mode": "libreoffice"
    },
    "600550": {
        "name": "保变电气",
        "industry": "电气设备",
        "pdf_2024": None,
        "pdf_2025": "600550_保变电气_unknown_年报.pdf",
        "expected_confidence": 0.7,
        "key_values": {}
    },
}

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "by_code"
)
RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "expansion_results"
)


def ensure_dir(path: str):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)


def find_pdf(stock_code: str, pdf_file: str) -> Optional[str]:
    """查找PDF文件"""
    if not pdf_file:
        return None
    
    stock_dir = os.path.join(DATA_DIR, stock_code)
    if not os.exists(stock_dir):
        return None
    
    pdf_path = os.path.join(stock_dir, pdf_file)
    return pdf_path if os.path.exists(pdf_path) else None


def run_extractor(pdf_path: str, extractor_class) -> Dict:
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
                "found": result.get("found", True),
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "confidence": {"overall": 0.0},
            "items_count": 0,
            "data": {},
            "found": False,
        }


def test_stock(stock_code: str, config: Dict) -> Dict:
    """测试单只股票"""
    results = {
        "stock_code": stock_code,
        "name": config["name"],
        "industry": config["industry"],
        "expected_confidence": config["expected_confidence"],
        "tests": {},
        "overall_confidence": 0.0,
        "status": "pending",
        "errors": [],
    }
    
    extractors = [
        ("BS", BalanceSheetExtractor),
        ("IS", IncomeStatementExtractor),
        ("CF", CashFlowExtractor),
    ]
    
    for year_suffix, pdf_file in [("2024", config.get("pdf_2024")), ("2025", config.get("pdf_2025"))]:
        if not pdf_file:
            continue
        
        pdf_path = find_pdf(stock_code, pdf_file)
        if not pdf_path:
            results["errors"].append(f"{year_suffix}: PDF文件不存在 - {pdf_file}")
            continue
        
        year_results = {}
        
        for ext_name, ext_class in extractors:
            key = f"{year_suffix}_{ext_name}"
            print(f"  Testing {stock_code} {year_suffix} {ext_name}...")
            
            result = run_extractor(pdf_path, ext_class)
            year_results[ext_name] = {
                "success": result["success"],
                "confidence": result["confidence"]["overall"],
                "items_count": result["items_count"],
                "found": result.get("found", False),
                "error": result.get("error"),
            }
            
            if not result["success"]:
                results["errors"].append(f"{key}: {result.get('error')}")
        
        results["tests"][year_suffix] = year_results
    
    # 计算总体置信度
    confidences = []
    for year_results in results["tests"].values():
        for ext_result in year_results.values():
            if ext_result["success"] and ext_result["found"]:
                confidences.append(ext_result["confidence"])
    
    if confidences:
        results["overall_confidence"] = sum(confidences) / len(confidences)
    
    # 判断状态
    if results["overall_confidence"] >= results["expected_confidence"]:
        results["status"] = "PASS"
    elif results["overall_confidence"] >= results["expected_confidence"] * 0.8:
        results["status"] = "WARN"
    else:
        results["status"] = "FAIL"
    
    return results


def run_expansion_tests() -> Dict:
    """运行扩展测试"""
    print("=" * 70)
    print("扩展测试 - 支持更多股票")
    print("=" * 70)
    
    ensure_dir(RESULTS_DIR)
    
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_stocks": 0,
            "passed": 0,
            "warned": 0,
            "failed": 0,
            "no_pdf": 0,
        },
        "results": {}
    }
    
    for stock_code, config in EXPANSION_TEST_STOCKS.items():
        print(f"\n测试 {stock_code} {config['name']} ({config['industry']})...")
        
        # 检查是否有PDF
        has_pdf = any(find_pdf(stock_code, f) for f in [config.get("pdf_2024"), config.get("pdf_2025")] if f)
        
        if not has_pdf:
            print(f"  跳过: 没有可用的PDF文件")
            all_results["summary"]["no_pdf"] += 1
            all_results["results"][stock_code] = {
                "name": config["name"],
                "status": "NO_PDF",
                "reason": "没有可用的PDF文件"
            }
            continue
        
        all_results["summary"]["total_stocks"] += 1
        
        result = test_stock(stock_code, config)
        all_results["results"][stock_code] = result
        
        # 统计
        if result["status"] == "PASS":
            all_results["summary"]["passed"] += 1
        elif result["status"] == "WARN":
            all_results["summary"]["warned"] += 1
        else:
            all_results["summary"]["failed"] += 1
        
        print(f"  状态: {result['status']}")
        print(f"  置信度: {result['overall_confidence']*100:.1f}%")
        
        if result["errors"]:
            print(f"  错误: {result['errors'][:2]}")  # 只显示前2个
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"expansion_{timestamp}.json")
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("扩展测试结果摘要")
    print("=" * 70)
    s = all_results["summary"]
    print(f"总股票数: {s['total_stocks']}")
    print(f"通过 (≥{0}期望): {s['passed']}")
    print(f"警告 (≥80%期望): {s['warned']}")
    print(f"失败 (<80%期望): {s['failed']}")
    print(f"无PDF: {s['no_pdf']}")
    print(f"\n详细结果: {result_file}")
    
    return all_results


def generate_summary_report(all_results: Dict) -> str:
    """生成摘要报告"""
    lines = [
        "# 扩展测试报告",
        f"\n生成时间: {all_results['timestamp']}",
        "\n## 测试股票列表",
        "",
        "| 股票代码 | 公司名称 | 行业 | 状态 | 置信度 |",
        "|----------|----------|------|------|--------|",
    ]
    
    for stock_code, result in all_results["results"].items():
        status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "NO_PDF": "➖"}.get(result["status"], "➖")
        conf = result.get("overall_confidence", 0) * 100
        name = result.get("name", "-")
        industry = EXPANSION_TEST_STOCKS.get(stock_code, {}).get("industry", "-")
        lines.append(f"| {stock_code} | {name} | {industry} | {status_icon} {result['status']} | {conf:.1f}% |")
    
    lines.extend([
        "",
        "## 状态说明",
        "- ✅ PASS: 达到期望置信度",
        "- ⚠️ WARN: 达到期望的80%以上",
        "- ❌ FAIL: 未达到期望的80%",
        "- ➖ NO_PDF: 没有可用的PDF文件",
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    results = run_expansion_tests()
    
    # 生成Markdown报告
    report = generate_summary_report(results)
    print("\n" + report)
    
    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(RESULTS_DIR, f"expansion_report_{timestamp}.md")
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n报告已保存: {report_file}")
