# -*- coding: utf-8 -*-
"""
Auto-learning CLI: learns naming patterns from RDS ground truth data.

Usage:
    python scripts/auto_learn.py --stock-codes 000001,601318,600036
    python scripts/auto_learn.py --stock-codes 000001,601318,600036,000858,600519 --apply
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.ground_truth.auto_learner import AutoLearner
from extraction.config import EXTRACTED_BY_CODE_DIR


RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ground_truth_reports")


def main():
    parser = argparse.ArgumentParser(description="Auto-learning from RDS ground truth")
    parser.add_argument("--stock-codes", required=True, help="Comma-separated stock codes")
    parser.add_argument("--year", type=int, default=2021, help="Year to analyze")
    parser.add_argument("--rds-dir", default=RDS_DIR, help="RDS data directory")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Output directory")
    parser.add_argument("--apply", action="store_true", help="Apply rules to config.py")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    stock_codes = [s.strip() for s in args.stock_codes.split(",")]
    years = [args.year]

    print(f"Auto-learning from {len(stock_codes)} stocks, year {args.year}")
    print(f"RDS dir: {args.rds_dir}")

    # Run auto-learner
    learner = AutoLearner(args.rds_dir)
    patterns = learner.learn(stock_codes, years)

    # Print report
    alias_map = learner.print_report(patterns)

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "stock_codes": stock_codes,
        "years": years,
        "patterns_count": len(patterns),
        "alias_map": alias_map,
    }

    report_path = os.path.join(args.output_dir, f"auto_learn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved: {report_path}")

    # Apply rules if requested
    if args.apply:
        _apply_alias_map(alias_map)


def _apply_alias_map(alias_map: dict):
    """Apply learned alias map to config.py."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extraction", "config.py")

    # Backup
    import shutil
    backup_path = config_path + ".bak"
    shutil.copy2(config_path, backup_path)
    print(f"Backup created: {backup_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    changes = 0
    for canonical, variants in alias_map.items():
        # Find the entry in ITEM_ALIAS_MAP
        pattern = re.compile(
            r'(\s*"' + re.escape(canonical) + r'"\s*:\s*\[)([^\]]*?)(\])',
            re.DOTALL,
        )
        match = pattern.search(content)
        if match:
            existing = match.group(2)
            for variant in variants:
                if variant not in existing:
                    existing = existing.rstrip() + f',\n        "{variant}"'
                    changes += 1
            content = content[:match.start(2)] + existing + content[match.end(2):]
        else:
            # Add new entry after ITEM_ALIAS_MAP = {
            insert_pattern = re.compile(r'(ITEM_ALIAS_MAP\s*=\s*\{)')
            insert_match = insert_pattern.search(content)
            if insert_match:
                pos = insert_match.end()
                new_entry = f'\n    "{canonical}": {variants},'
                content = content[:pos] + new_entry + content[pos:]
                changes += 1

    if changes > 0:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Applied {changes} new alias entries to config.py")
    else:
        print("No new aliases to apply")


if __name__ == "__main__":
    main()
