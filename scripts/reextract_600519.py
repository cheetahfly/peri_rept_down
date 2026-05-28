# -*- coding: utf-8 -*-
"""Re-extract 600519 2020 and compare against RDS."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.parsers.pdf_parser import PdfParser
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.cash_flow import CashFlowExtractor
from extraction.ground_truth.rds_loader import RdsLoader
from extraction.ground_truth.comparator import compare_stock, ComparisonResult
from extraction.config import get_aliases

pdf_path = "F:/ai_fin_proj/peri_rept_down/data/pdfs/600519/600519_2020_annual.pdf"
extracted_dir = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code/600519"
rds_dir = "D:/Research/Quant/SETL/cninfo/data_backup"

stock_code = "600519"
year = 2020
report_type = "annual"

# Load RDS data
loader = RdsLoader(rds_dir)
decode_maps_path = "F:/ai_fin_proj/peri_rept_down/data/decode_mappings_by_type.json"
with open(decode_maps_path, "r", encoding="utf-8") as f:
    decode_maps = json.load(f)

# Re-extract each statement type
for st_name, ExtractorClass in [
    ("income_statement", IncomeStatementExtractor),
    ("balance_sheet", BalanceSheetExtractor),
    ("cash_flow", CashFlowExtractor),
]:
    print(f"\n=== Re-extracting {st_name} ===")
    with PdfParser(pdf_path) as parser:
        extractor = ExtractorClass(parser)
        result = extractor.extract()

    items = result.get("data", {})
    print(f"  Pages: {result.get('pages', [])}")
    print(f"  Items: {len(items)}")

    # Save
    out_path = os.path.join(extracted_dir, f"{stock_code}_{year}_{st_name}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "stock_code": stock_code,
            "report_year": year,
            "statement_type": st_name,
            "report_type": report_type,
            "data": {
                "statement_type": st_name,
                "found": result.get("found", False),
                "pages": result.get("pages", []),
                "data": items,
                "extracted_at": result.get("extracted_at", ""),
                "confidence": result.get("confidence", 0.0),
                "recovered": result.get("recovered", False),
                "recovery_method": result.get("recovery_method", ""),
            },
            "saved_at": "2026-05-28T18:00:00",
        }, f, ensure_ascii=False, indent=2)
    print(f"  Saved to {out_path}")

    # Load RDS data
    gt_data = loader.load_stock_data(stock_code, year, st_name)
    print(f"  RDS items: {len(gt_data)}")

    # Compare
    aliases = get_aliases(st_name, report_type)
    decode_map = decode_maps.get(st_name, {})
    comp_result = compare_stock(
        gt_data, items, aliases,
        stock_code=stock_code, year=year,
        statement_type=st_name, decode_map=decode_map,
    )

    summary = comp_result.summary()
    print(f"  Matched: {summary['matched']}, Missing: {summary['missing']}, Unmatched: {summary['unmatched']}")
    print(f"  Coverage: {summary['coverage']:.1%}, Value Accuracy: {summary['value_accuracy']:.1%}")

    # Show missing items
    if comp_result.missing:
        print(f"  Missing items ({len(comp_result.missing)}):")
        for item in comp_result.missing:
            print(f"    {item.ground_truth_name} = {item.ground_truth_value}")
            print(f"      → RDS code: {item.ground_truth_code}")

# Also re-extract IS with debug to confirm 利息收入 fix
print("\n\n=== Verification: 利息收入 in IS extraction ===")
with PdfParser(pdf_path) as parser:
    extractor = IncomeStatementExtractor(parser)
    result = extractor.extract()
items = result.get("data", {})
for k, v in items.items():
    if '利息' in k:
        print(f"  {k} = {v}")
