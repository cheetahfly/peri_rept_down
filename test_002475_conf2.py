"""Quick confidence check for 002475"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraction.cli import extract_single_pdf

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\002475\002475_立讯精密_2025_年度报告.PDF"
result = extract_single_pdf(pdf_path, save_json=False, save_db=False)

for stmt in ["income_statement", "cash_flow"]:
    r = result["results"].get(stmt, {})
    conf = r.get("confidence", {})
    data = r.get("data", {})
    pages = r.get("pages", [])
    found = r.get("found")
    print(f"{stmt}: found={found}, pages={pages}, items={len(data)}, conf={conf}")
