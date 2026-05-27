# -*- coding: utf-8 -*-
"""
Generate alias mappings from ground truth comparison results.
Reads comparison data and produces new aliases for the extraction config.
"""

import sys
import os
import json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.ground_truth.rds_loader import RdsLoader
from extraction.ground_truth.comparator import load_extracted_json, normalize_name


def generate_aliases(rds_dir, extracted_dir, output_path, years=(2019, 2020, 2021)):
    """Generate alias mappings from comparison data."""
    loader = RdsLoader(rds_dir)

    # Collect (gt_name, ext_name) matches across stocks
    name_matches = defaultdict(set)
    gt_names_by_st = defaultdict(set)
    ext_names_by_st = defaultdict(set)

    stock_codes = sorted(
        d for d in os.listdir(extracted_dir)
        if os.path.isdir(os.path.join(extracted_dir, d)) and d.isdigit()
    )

    for stock_code in stock_codes:
        stock_dir = os.path.join(extracted_dir, stock_code)
        for fname in sorted(os.listdir(stock_dir)):
            if "_indicators" in fname or not fname.endswith(".json"):
                continue
            base = fname.replace(".json", "")
            parts = base.split("_")
            if len(parts) < 3:
                continue
            st = "_".join(parts[2:])
            if st not in ("balance_sheet", "income_statement", "cash_flow"):
                continue
            try:
                year = int(parts[1])
            except ValueError:
                continue
            if year < years[0] or year > years[-1]:
                continue

            json_path = os.path.join(stock_dir, fname)
            gt = loader.load_stock_data(stock_code, year, st)
            ext = load_extracted_json(json_path)
            if not gt or not ext:
                continue

            gt_names_by_st[st].update(gt.keys())
            ext_names_by_st[st].update(ext.keys())

            gt_norm = {normalize_name(k): k for k in gt}
            for ek in ext:
                nek = normalize_name(ek)
                if nek in gt_norm:
                    gk = gt_norm[nek]
                    name_matches[(st, gk, ek)].add(f"{stock_code}_{year}")

    # Build aliases: standard_name -> [variants] per statement type
    aliases = defaultdict(lambda: defaultdict(set))
    for (st, gk, ek), evidence in name_matches.items():
        if gk == ek:
            continue
        if len(evidence) >= 2:
            aliases[st][gk].add(ek)

    # Convert to plain dicts
    result = {}
    for st in ("balance_sheet", "income_statement", "cash_flow"):
        if st in aliases:
            result[st] = {k: sorted(v) for k, v in sorted(aliases[st].items())}

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Print summary
    total = sum(len(v) for v in result.values())
    print(f"Generated {total} alias mappings across {len(result)} statement types")
    for st, mapping in result.items():
        print(f"  {st}: {len(mapping)} standard names, {sum(len(v) for v in mapping.values())} variants")

    return result


if __name__ == "__main__":
    rds_dir = sys.argv[1] if len(sys.argv) > 1 else "F:/Research/Quant/SETL/cninfo/data_backup"
    extracted_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "extracted", "by_code"
    )
    output_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "generated_aliases.json"
    )
    generate_aliases(rds_dir, extracted_dir, output_path)
