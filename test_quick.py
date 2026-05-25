# Quick test with exception catch
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\000858\000858_五粮液_五_粮_液：2025年半年度报告（更新后）.PDF"

with PdfParser(pdf_path) as parser:
    ext = BalanceSheetExtractor(parser)
    try:
        pages = ext._find_section_pages(parser)
        print(f"Result: {pages}")
    except Exception:
        traceback.print_exc()
