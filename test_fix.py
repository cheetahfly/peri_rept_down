# -*- coding: utf-8 -*-
"""Test the _is_appendix_page and _find_section_pages fixes on 000858 PDF"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor

pdf_path = r"F:\ai_fin_proj\peri_rept_down\data\by_code\000858\000858_五粮液_五_粮_液：2025年半年度报告（更新后）.PDF"
print(f"Testing: {pdf_path}")

with PdfParser(pdf_path) as parser:
    print(f"Pages: {parser.page_count}")

    extractors = {
        "balance_sheet": BalanceSheetExtractor(parser),
        "income_statement": IncomeStatementExtractor(parser),
        "cash_flow": CashFlowExtractor(parser),
    }

    for name, ext in extractors.items():
        print(f"\n=== {name} ===")
        # Debug: scan all pages for appendix/section_header info
        for p in range(1, parser.page_count + 1):
            text = parser.extract_text(p)
            if not text or len(text.strip()) < 50:
                continue
            appendix = ext._is_appendix_page(text)
            has_header = ext._text_has_section_header(text)

            # Show pages that are interesting (not trivially non-appendix, non-header)
            first_line = text.strip().split('\n')[0][:80]
            has_bs_kw = any(kw in text[:500] for kw in ['资产负债表', '合并资产'])
            has_is_kw = any(kw in text[:500] for kw in ['利润表', '合并利润'])
            has_cf_kw = any(kw in text[:500] for kw in ['现金流量表', '合并现金流'])

            if appendix or has_header or has_bs_kw or has_is_kw or has_cf_kw:
                print(f"  p{p:3d}: appendix={appendix} header={has_header}", end="")
                if has_bs_kw: print(" BS_kw", end="")
                if has_is_kw: print(" IS_kw", end="")
                if has_cf_kw: print(" CF_kw", end="")
                print(f"  | {first_line}")

        # Now test the actual page finding
        t0 = time.time()
        pages = ext._find_section_pages(parser)
        dt = time.time() - t0
        print(f"\n  Found pages: {pages} ({dt:.1f}s)")
