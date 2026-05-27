# -*- coding: utf-8 -*-
"""
Ground truth comparison CLI.

Compares extracted PDF data against CNINFO RDS ground truth.
Iteratively improves extraction rules through comparison.
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.ground_truth.rds_loader import RdsLoader
from extraction.ground_truth.comparator import compare_stock, load_extracted_json
from extraction.ground_truth.gap_analyzer import analyze_gaps, suggestions_to_json, analyze_value_matches
from extraction.ground_truth.rule_applier import apply_suggestions, preview_changes
from extraction.config import ITEM_ALIAS_MAP, STATEMENT_TYPE_STANDARD_ITEMS, EXTRACTED_BY_CODE_DIR


RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extraction", "config.py")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ground_truth_reports")


def cmd_compare(args):
    loader = RdsLoader(args.rds_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    all_results = []
    stocks = [s.strip() for s in args.stock_codes.split(",")]

    for stock_code in stocks:
        year = args.year
        print(f"\n--- {stock_code} {year} ---")

        for st in ["income_statement", "balance_sheet", "cash_flow"]:
            gt = loader.load_stock_data(stock_code, year, st)
            if not gt:
                print(f"  {st}: no ground truth data")
                continue

            # Find extracted JSON
            json_path = os.path.join(args.extracted_dir, stock_code, f"{stock_code}_{year}_{st}.json")
            if not os.path.exists(json_path):
                print(f"  {st}: no extracted JSON")
                continue

            ext = load_extracted_json(json_path)
            result = compare_stock(gt, ext, ITEM_ALIAS_MAP, stock_code, year, st)
            s = result.summary()
            print(f"  {st}: coverage={s['coverage']:.1%} ({s['matched']}/{s['gt_items']}), unmatched={s['unmatched']}")
            all_results.append(result)

    # Analyze gaps
    if all_results:
        # Text similarity analysis
        analysis = analyze_gaps(all_results, ITEM_ALIAS_MAP, STATEMENT_TYPE_STANDARD_ITEMS)

        # Value matching analysis (new!)
        value_suggestions = analyze_value_matches(all_results, ITEM_ALIAS_MAP, min_stocks=3)

        # Merge suggestions (value matches first, as they're more reliable)
        all_suggestions = value_suggestions + analysis["suggestions"]
        analysis["suggestions"] = all_suggestions

        report = suggestions_to_json(analysis)

        report_path = os.path.join(args.output_dir, f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved: {report_path}")

        # Print value-based suggestions (highest confidence)
        print(f"\n=== Value-matched alias suggestions ({len(value_suggestions)} total) ===")
        for s in value_suggestions[:20]:
            print(f"  [{s.confidence:.2f}] {s.description}")

        # Print top text-similarity suggestions
        print(f"\n=== Text-similarity suggestions ({len(analysis['suggestions']) - len(value_suggestions)} total) ===")
        for s in analysis["suggestions"][len(value_suggestions):len(value_suggestions)+10]:
            print(f"  [{s.confidence:.2f}] {s.description}")


def cmd_apply(args):
    if not os.path.exists(args.suggestions_file):
        print(f"Suggestions file not found: {args.suggestions_file}")
        return

    with open(args.suggestions_file, "r", encoding="utf-8") as f:
        report = json.load(f)

    suggestions = report.get("suggestions", [])
    # Filter by confidence threshold
    suggestions = [s for s in suggestions if s.get("confidence", 0) >= args.min_confidence]
    print(f"Applying {len(suggestions)} suggestions (confidence >= {args.min_confidence})")

    if args.dry_run:
        changes = preview_changes(args.config_path, suggestions)
    else:
        changes = apply_suggestions(args.config_path, suggestions, dry_run=False)

    for c in changes:
        print(f"  {c}")


def cmd_round(args):
    print(f"=== Round: comparing {args.stock_codes} for year {args.year} ===")
    # Step 1: Compare
    cmd_compare(args)
    # Step 2: Apply (dry-run by default)
    print("\n=== Applying improvements (dry-run) ===")
    # Find latest report
    reports = sorted([f for f in os.listdir(args.output_dir) if f.startswith("comparison_")])
    if reports:
        args.suggestions_file = os.path.join(args.output_dir, reports[-1])
        args.dry_run = not args.apply
        args.min_confidence = 0.3
        cmd_apply(args)


def main():
    parser = argparse.ArgumentParser(description="Ground truth comparison tool")
    subparsers = parser.add_subparsers(dest="command")

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare extracted vs ground truth")
    p_compare.add_argument("--stock-codes", required=True, help="Comma-separated stock codes")
    p_compare.add_argument("--year", type=int, default=2021, help="Year to compare")
    p_compare.add_argument("--rds-dir", default=RDS_DIR, help="RDS data directory")
    p_compare.add_argument("--extracted-dir", default=EXTRACTED_BY_CODE_DIR, help="Extracted JSON directory")
    p_compare.add_argument("--output-dir", default=OUTPUT_DIR, help="Output directory")

    # apply
    p_apply = subparsers.add_parser("apply", help="Apply improvement suggestions")
    p_apply.add_argument("--suggestions-file", required=True, help="Suggestions JSON file")
    p_apply.add_argument("--config-path", default=CONFIG_PATH, help="Config.py path")
    p_apply.add_argument("--dry-run", action="store_true", help="Preview only")
    p_apply.add_argument("--min-confidence", type=float, default=0.3, help="Min confidence threshold")

    # round
    p_round = subparsers.add_parser("round", help="Run a full comparison round")
    p_round.add_argument("--stock-codes", required=True, help="Comma-separated stock codes")
    p_round.add_argument("--year", type=int, default=2021, help="Year to compare")
    p_round.add_argument("--rds-dir", default=RDS_DIR, help="RDS data directory")
    p_round.add_argument("--extracted-dir", default=EXTRACTED_BY_CODE_DIR, help="Extracted JSON directory")
    p_round.add_argument("--output-dir", default=OUTPUT_DIR, help="Output directory")
    p_round.add_argument("--apply", action="store_true", help="Actually apply changes")

    args = parser.parse_args()

    if args.command == "compare":
        cmd_compare(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "round":
        cmd_round(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
