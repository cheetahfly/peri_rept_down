# -*- coding: utf-8 -*-
"""
从立讯精密2025年年报PDF中提取三大财务报表的完整细项
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "by_code", "002475")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

pdf_path = os.path.join(DATA_DIR, "002475_立讯精密_2025_年度报告.PDF")

from extraction.parsers.hybrid_parser import HybridParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor

with HybridParser(pdf_path) as parser:
    print(f"Parser mode: {parser.parsing_method}")
    print(f"Pages: {parser.page_count}")

    extractors = {
        "利润表": IncomeStatementExtractor(parser),
        "资产负债表": BalanceSheetExtractor(parser),
        "现金流量表": CashFlowExtractor(parser),
    }

    all_results = {}

    for stmt_name, ext in extractors.items():
        print(f"\n{'='*70}")
        print(f"  {stmt_name}")
        print(f"{'='*70}")

        result = ext.extract()
        data = result.get("data", {})
        conf = ext.calculate_confidence(result)
        found = result.get("found", False)

        print(f"Found: {found}, Items: {len(data)}, Confidence: {conf.get('overall', 'N/A')}")

        # Validation
        if hasattr(ext, 'validate'):
            valid, err_msg = ext.validate(result)
            print(f"Valid: {valid}" + (f", {err_msg}" if err_msg else ""))

        items_sorted = sorted(data.items(), key=lambda x: x[0])
        for k, v in items_sorted:
            if isinstance(v, (int, float)):
                if abs(v) >= 1e8:
                    print(f"  {k:45s} {v:>20.2f} ({v/1e8:.2f}亿)")
                else:
                    print(f"  {k:45s} {v:>20.2f}")
            else:
                print(f"  {k:45s} {str(v):>20s}")

        all_results[stmt_name] = data

        # Save per-statement JSON
        out_path = os.path.join(OUT_DIR, f"pdf_{ext.STATEMENT_TYPE}_all_items.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # Save combined
    combined_path = os.path.join(OUT_DIR, "luxun_precision_2025_pdf_full.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nAll data saved to: {combined_path}")
