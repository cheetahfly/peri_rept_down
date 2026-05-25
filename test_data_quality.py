# -*- coding: utf-8 -*-
"""Check data quality of 000858 CID extraction"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extraction.cli import extract_single_pdf

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\000858\000858_五粮液_五_粮_液：2025年半年度报告（更新后）.PDF"
result = extract_single_pdf(pdf_path, save_json=False, save_db=False)

if not result.get("success"):
    print(f"FAILED: {result.get('error')}")
    sys.exit(1)

results = result["results"]

for stmt_type in ["balance_sheet", "income_statement", "cash_flow"]:
    r = results.get(stmt_type, {})
    data = r.get("data", {})
    print(f"\n{'='*60}")
    print(f"  {stmt_type}")
    print(f"{'='*60}")
    print(f"  found={r.get('found')} valid={r.get('valid')} pages={r.get('pages')}")
    print(f"  items: {len(data)}")

    if not data:
        print(f"  NO DATA")
        continue

    # Show ALL items
    for k, v in sorted(data.items()):
        print(f"    {k}: {v}")

    # Check for total rows
    totals = [k for k in data.keys() if '合计' in k or '总计' in k]
    if totals:
        print(f"\n  === Total rows ===")
        for k in totals:
            print(f"    {k}: {data[k]}")

# Check balance equation
bs = results.get("balance_sheet", {}).get("data", {})
if "balance_equation" in results.get("balance_sheet", {}):
    b = results["balance_sheet"]["balance_equation"]
    print(f"\n{'='*60}")
    print(f"  Balance Equation Check")
    print(f"{'='*60}")
    print(f"  Status: {b.get('status')}")
    print(f"  Assets: {b.get('assets')}")
    print(f"  Liab+Equity: {b.get('liab_equity')}")
    print(f"  Diff: {b.get('diff')}")
