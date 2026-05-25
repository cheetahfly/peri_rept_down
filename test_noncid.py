# -*- coding: utf-8 -*-
"""Test extraction on various PDFs"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extraction.cli import extract_single_pdf

# Test a non-CID PDF (平安银行 2025年报)
pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\000001\000001_平安银行_平安银行：2025年年度报告.PDF"
print(f"{'='*70}")
print(f"Testing: {pdf_path}")
print(f"{'='*70}")

result = extract_single_pdf(pdf_path, save_json=False, save_db=False)

if result.get("success"):
    results = result["results"]
    for stmt_type in ["balance_sheet", "income_statement", "cash_flow"]:
        r = results.get(stmt_type, {})
        data = r.get("data", {})
        items = r.get("items", [])
        print(f"\n=== {stmt_type} ===")
        print(f"  found={r.get('found')} valid={r.get('valid')} items={len(data)} pages={r.get('pages')}")
        if "confidence" in r:
            print(f"  confidence: {r.get('confidence')}")
        if data:
            sample = list(sorted(data.items()))[:10]
            for k, v in sample:
                print(f"    {k}: {v}")
        if r.get("errors"):
            print(f"  errors: {r['errors'][:3]}")
        if "balance_equation" in r:
            b = r["balance_equation"]
            print(f"  balance: {b.get('status')} (diff={b.get('diff')})")
else:
    print(f"FAILED: {result.get('error')}")
