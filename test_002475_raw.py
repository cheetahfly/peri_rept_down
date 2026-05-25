"""Check 002475 IS page raw text"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re
from extraction.parsers.pdf_parser import PdfParser

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\002475\002475_立讯精密_2025_年度报告.PDF"
parser = PdfParser(pdf_path)

for pn in [119, 120]:
    text = parser.extract_text(pn)
    lines = text.split('\n')
    chinese_lines = [(i, l.strip()) for i, l in enumerate(lines) if any('一' <= c <= '鿿' for c in l) and re.search(r'[\d,]{4,}', l)]
    print(f"\n--- Page {pn}: {len(chinese_lines)} data lines ---")
    for i, l in chinese_lines[:30]:
        print(f"  [{i:3d}] {l[:80]}")

    # Check for key items in raw text
    for kw in ['净利润', '利润总额', '营业总收入', '营业利润']:
        if kw in text:
            idx = text.find(kw)
            print(f"\n  '{kw}' found at {idx}: ...{text[max(0,idx-20):idx+40]}...")

parser.close()
