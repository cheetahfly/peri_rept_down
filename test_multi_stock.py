"""Quick extraction test for multiple stocks"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraction.cli import extract_single_pdf

stocks = {
    "002230": r"F:\ai_fin_proj\peri_rept_down\data\by_code\002230\002230_科大讯飞_科大讯飞：2025年年度报告.PDF",
    "002475": r"F:\ai_fin_proj\peri_rept_down\data\by_code\002475\002475_立讯精密_2025_年度报告.PDF",
    "600585": r"F:\ai_fin_proj\peri_rept_down\data\by_code\600585\600585_海螺水泥_海螺水泥：2025年度报告.PDF",
    "601318": r"F:\ai_fin_proj\peri_rept_down\data\by_code\601318\601318_中国平安_中国平安：中国平安2025年年度报告.PDF",
}

for code, path in stocks.items():
    if not os.path.exists(path):
        print(f"\n{'='*60}")
        print(f"  {code}: PDF NOT FOUND at {path}")
        continue

    print(f"\n{'='*60}")
    print(f"  Testing: {code}")
    print(f"{'='*60}")

    try:
        result = extract_single_pdf(path, save_json=False, save_db=False)
        if not result.get("success"):
            print(f"  FAILED: {result.get('error')}")
            continue

        results = result["results"]
        for stmt_type in ["balance_sheet", "income_statement", "cash_flow"]:
            r = results.get(stmt_type, {})
            data = r.get("data", {})
            pages = r.get("pages", [])
            confidence = r.get("confidence", {})

            if isinstance(confidence, dict):
                c = confidence.get("overall", 0)
            else:
                c = confidence

            status = "OK" if r.get("found") else "FAIL"
            print(f"  {stmt_type:20s}: {status} pages={pages} items={len(data):2d} conf={c:.1%}")

            if r.get("errors"):
                print(f"    errors: {r['errors'][:2]}")

            if "balance_equation" in r:
                b = r["balance_equation"]
                print(f"    balance: {b.get('status')} (diff={b.get('diff', 'N/A')})")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
