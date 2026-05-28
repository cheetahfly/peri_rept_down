# -*- coding: utf-8 -*-
"""
Batch comparison script.

Compares extracted data against RDS ground truth for multiple stocks/years.
Outputs detailed reports and alias suggestions.
"""

import os
import sys
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.ground_truth.rds_loader import RdsLoader
from extraction.ground_truth.comparator import compare_stock, load_extracted_json, ComparisonResult
from extraction.ground_truth.gap_analyzer import GapAnalyzer
from extraction.config import get_aliases, EXTRACTED_BY_CODE_DIR


def find_extracted_json(extracted_dir: str, stock_code: str, year: int, statement_type: str) -> Optional[str]:
    """Find extracted JSON file for a stock/year/statement type."""
    fname = f"{stock_code}_{year}_{statement_type}.json"
    path = os.path.join(extracted_dir, stock_code, fname)
    return path if os.path.exists(path) else None


def run_single_comparison(
    loader: RdsLoader,
    stock_code: str,
    year: int,
    statement_type: str,
    extracted_dir: str,
    report_type: str = "annual",
) -> Optional[ComparisonResult]:
    """
    Run a single comparison for one stock/year/statement type.

    Returns:
        ComparisonResult or None if no data available
    """
    # Load ground truth data
    gt_data = loader.load_stock_data(stock_code, year, statement_type)
    if not gt_data:
        return None

    # Find and load extracted data
    json_path = find_extracted_json(extracted_dir, stock_code, year, statement_type)
    if not json_path:
        return None

    ext_data = load_extracted_json(json_path)
    if not ext_data:
        return None

    # Get hierarchical aliases
    alias_map = get_aliases(statement_type, report_type)

    # Run comparison
    result = compare_stock(
        gt_data, ext_data, alias_map,
        stock_code=stock_code, year=year, statement_type=statement_type
    )

    return result


def batch_compare(
    stock_codes: List[str],
    years: List[int],
    statement_types: List[str] = None,
    rds_dir: str = "D:/Research/Quant/SETL/cninfo/data_backup",
    extracted_dir: str = None,
    report_type: str = "annual",
    output_dir: str = None,
) -> Dict[str, Any]:
    """
    Run batch comparison for multiple stocks/years.

    Args:
        stock_codes: List of stock codes to compare
        years: List of years to compare
        statement_types: List of statement types (default: all three)
        rds_dir: Path to RDS ground truth data directory
        extracted_dir: Path to extracted JSON files directory
        report_type: Report type for alias lookup ('annual', 'half_year', etc.)
        output_dir: Directory to save reports

    Returns:
        Dict with summary statistics and alias suggestions
    """
    if extracted_dir is None:
        extracted_dir = EXTRACTED_BY_CODE_DIR

    if statement_types is None:
        statement_types = ["income_statement", "balance_sheet", "cash_flow"]

    # Initialize loader
    loader = RdsLoader(rds_dir)

    # Initialize gap analyzer
    gap_analyzer = GapAnalyzer(min_similarity=0.7)

    # Track all results
    all_results: List[ComparisonResult] = []
    detailed_reports = []
    errors = []

    # Summary stats by statement type
    stats = defaultdict(lambda: {
        "total": 0, "compared": 0, "matched": 0, "missing": 0,
        "unmatched": 0, "coverage_sum": 0.0
    })

    print(f"Batch comparison: {len(stock_codes)} stocks x {len(years)} years x {len(statement_types)} types")
    print(f"Output dir: {output_dir}")
    print("-" * 60)

    for stock_code in stock_codes:
        for year in years:
            for st in statement_types:
                key = f"{stock_code}/{year}/{st}"
                stats[st]["total"] += 1

                try:
                    result = run_single_comparison(
                        loader, stock_code, year, st, extracted_dir, report_type
                    )

                    if result is None:
                        errors.append({
                            "key": key,
                            "error": "No data available",
                            "type": "missing"
                        })
                        continue

                    all_results.append(result)

                    # Update stats
                    s = result.summary()
                    stats[st]["compared"] += 1
                    stats[st]["matched"] += s["matched"]
                    stats[st]["missing"] += s["missing"]
                    stats[st]["unmatched"] += s["unmatched"]
                    stats[st]["coverage_sum"] += s["coverage"]

                    # Generate detailed report
                    report = result.detailed_report()
                    report["stock_code"] = stock_code
                    report["year"] = year
                    report["statement_type"] = st
                    detailed_reports.append(report)

                    # Progress output
                    print(f"  {key}: coverage={s['coverage']:.1%}, matched={s['matched']}, missing={s['missing']}")

                except Exception as e:
                    errors.append({
                        "key": key,
                        "error": str(e),
                        "type": "exception"
                    })
                    print(f"  {key}: ERROR - {e}")

    # Calculate aggregate stats
    total_compared = sum(s["compared"] for s in stats.values())
    total_matched = sum(s["matched"] for s in stats.values())
    total_missing = sum(s["missing"] for s in stats.values())
    total_unmatched = sum(s["unmatched"] for s in stats.values())
    total_coverage = total_matched / (total_matched + total_missing) if (total_matched + total_missing) > 0 else 0.0

    # Generate suggestions using GapAnalyzer
    suggestions = []
    for report in detailed_reports:
        report_suggestions = gap_analyzer.analyze(report)
        suggestions.extend(report_suggestions)

    # Group suggestions by standard name
    grouped_suggestions = defaultdict(list)
    for s in suggestions:
        key = s.get("standard_name", s.get("key", ""))
        if key:
            grouped_suggestions[key].append(s)

    # Build suggestion summary (highest confidence per standard name)
    suggestion_summary = []
    for standard_name, variants in grouped_suggestions.items():
        best = max(variants, key=lambda x: len(x.get("variants", [])))
        suggestion_summary.append({
            "standard_name": standard_name,
            "suggested_variants": list(set(
                v
                for s in variants
                for v in s.get("variants", [s.get("standard_name")])
            )),
            "evidence_count": len(variants),
            "reason": best.get("reason", ""),
        })

    suggestion_summary.sort(key=lambda x: -x["evidence_count"])

    # Build summary
    summary = {
        "total_compared": total_compared,
        "total_matched": total_matched,
        "total_missing": total_missing,
        "total_unmatched": total_unmatched,
        "total_coverage": round(total_coverage, 3),
        "by_statement_type": {
            st: {
                "compared": s["compared"],
                "coverage": round(s["coverage_sum"] / s["compared"], 3) if s["compared"] > 0 else 0.0,
                "matched": s["matched"],
                "missing": s["missing"],
                "unmatched": s["unmatched"],
            }
            for st, s in stats.items()
        },
        "errors": len(errors),
    }

    # Build result dict
    result = {
        "summary": summary,
        "suggestions": suggestion_summary,
        "detailed_reports": detailed_reports,
        "errors": errors,
        "metadata": {
            "stock_codes": stock_codes,
            "years": years,
            "statement_types": statement_types,
            "report_type": report_type,
            "rds_dir": rds_dir,
            "extracted_dir": extracted_dir,
            "timestamp": datetime.now().isoformat(),
        }
    }

    # Save to output directory if specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

        # Save summary report
        summary_path = os.path.join(output_dir, "batch_comparison_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump({
                "summary": result["summary"],
                "suggestions": result["suggestions"],
                "metadata": result["metadata"],
            }, f, ensure_ascii=False, indent=2)

        # Save detailed reports
        detailed_path = os.path.join(output_dir, "batch_comparison_detailed.json")
        with open(detailed_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Save per-stock reports
        for stock_code in stock_codes:
            stock_reports = [r for r in detailed_reports if r["stock_code"] == stock_code]
            if stock_reports:
                stock_path = os.path.join(output_dir, f"{stock_code}_comparison.json")
                with open(stock_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "stock_code": stock_code,
                        "reports": stock_reports,
                        "summary": {
                            "total_compared": len(stock_reports),
                            "avg_coverage": sum(r["coverage"] for r in stock_reports) / len(stock_reports) if stock_reports else 0,
                        }
                    }, f, ensure_ascii=False, indent=2)

        print(f"\nReports saved to: {output_dir}")
        print(f"  - Summary: {summary_path}")
        print(f"  - Detailed: {detailed_path}")

    return result


def print_summary(result: Dict[str, Any]) -> None:
    """Print a formatted summary of batch comparison results."""
    summary = result["summary"]

    print("\n" + "=" * 60)
    print("BATCH COMPARISON SUMMARY")
    print("=" * 60)

    print(f"\nTotal compared: {summary['total_compared']}")
    print(f"Total matched: {summary['total_matched']}")
    print(f"Total missing: {summary['total_missing']}")
    print(f"Total unmatched: {summary['total_unmatched']}")
    print(f"Overall coverage: {summary['total_coverage']:.2%}")

    print("\n--- By Statement Type ---")
    for st, s in summary.get("by_statement_type", {}).items():
        print(f"\n  {st}:")
        print(f"    Compared: {s['compared']}")
        print(f"    Coverage: {s['coverage']:.2%}")
        print(f"    Matched: {s['matched']}, Missing: {s['missing']}, Unmatched: {s['unmatched']}")

    suggestions = result.get("suggestions", [])
    print(f"\n--- Alias Suggestions ({len(suggestions)} total) ---")
    for s in suggestions[:20]:
        print(f"  {s['standard_name']}: {s['suggested_variants'][:3]}")

    errors = result.get("errors", [])
    if errors:
        print(f"\n--- Errors ({len(errors)}) ---")
        for e in errors[:10]:
            print(f"  {e['key']}: {e['error']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch compare extracted data against RDS")
    parser.add_argument("--stocks", nargs="+", default=["600519"], help="Stock codes")
    parser.add_argument("--years", nargs="+", type=int, default=[2020], help="Years")
    parser.add_argument("--types", nargs="+", default=["income_statement", "balance_sheet", "cash_flow"],
                        help="Statement types")
    parser.add_argument("--rds-dir", default="D:/Research/Quant/SETL/cninfo/data_backup", help="RDS data directory")
    parser.add_argument("--extracted-dir", default=None, help="Extracted JSON directory")
    parser.add_argument("--output", default="data/phase2_reports", help="Output directory")
    parser.add_argument("--report-type", default="annual", help="Report type for aliases")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    result = batch_compare(
        stock_codes=args.stocks,
        years=args.years,
        statement_types=args.types,
        rds_dir=args.rds_dir,
        extracted_dir=args.extracted_dir,
        report_type=args.report_type,
        output_dir=args.output,
    )

    if not args.quiet:
        print_summary(result)

    print(f"\nComparison complete!")
    print(f"Total compared: {result['summary']['total_compared']}")
    print(f"Average coverage: {result['summary']['total_coverage']:.2%}")
    print(f"Alias suggestions: {len(result['suggestions'])}")
    print(f"\nResults saved to: {args.output}")
