"""Check 002475 actual item names"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraction.cli import extract_single_pdf

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\002475\002475_立讯精密_2025_年度报告.PDF"
result = extract_single_pdf(pdf_path, save_json=False, save_db=False)

for stmt in ["income_statement", "cash_flow"]:
    r = result["results"].get(stmt, {})
    data = r.get("data", {})
    print(f"\n{'='*60}")
    print(f"  {stmt}: {len(data)} items, pages={r.get('pages')}")
    print(f"  found={r.get('found')}, validation={r.get('validation')}")

    # Print all item names
    for i, (k, v) in enumerate(sorted(data.items())):
        print(f"    [{i:2d}] {repr(k)}: {v}")

    # Check key items
    print(f"\n  Key item check:")
    key_lists = {
        "income_statement": ["营业收入", "利润总额", "净利润", "所得税费用", "营业利润"],
        "cash_flow": ["经营活动产生的现金流量净额", "投资活动", "筹资活动", "现金及现金等价物"],
    }
    for kw in key_lists.get(stmt, []):
        matches = [k for k in data if kw in k]
        if matches:
            print(f"    '{kw}' → {[repr(m) for m in matches]}")
        else:
            # Check partial matches
            partial = [k for k in data if any(c in k for c in kw)]
            if partial:
                print(f"    '{kw}' NOT FOUND, partial matches: {[repr(m) for m in partial[:5]]}")
            else:
                print(f"    '{kw}' → NOT FOUND (no partial matches either)")
