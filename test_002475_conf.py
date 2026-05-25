"""Check 002475 IS/CF items detail"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraction.cli import extract_single_pdf

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\002475\002475_立讯精密_2025_年度报告.PDF"
result = extract_single_pdf(pdf_path, save_json=False, save_db=False)

for stmt in ["income_statement", "cash_flow"]:
    r = result["results"].get(stmt, {})
    data = r.get("data", {})
    print(f"\n{'='*60}")
    print(f"  {stmt}: {len(data)} items, pages={r.get('pages')}")
    v = r.get('validation', {})
    if isinstance(v, dict):
        print(f"  valid={v.get('valid')}, errors={v.get('errors', [])[:3]}")

    # check key items
    for kw in ['营业收入', '营业成本', '净利润', '利润总额', '所得税费用', '营业利润']:
        found = [k for k in data if kw in k]
        if found:
            print(f"  KEY '{kw}': {found}")
        else:
            print(f"  KEY '{kw}': NOT FOUND")

    # show first 10 items
    print(f"\n  First 10 items:")
    for i, (k, v) in enumerate(sorted(data.items())):
        if i >= 10:
            print(f"    ...")
            break
        print(f"    {k}: {v}")
