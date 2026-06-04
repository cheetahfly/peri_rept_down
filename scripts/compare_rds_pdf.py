#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
比较 RDS 数据库中的标准财务数据与 PDF 提取的财务数据
生成对比报告和规则总结
"""

import sys
import os
import json
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.comparator import compare_stock, normalize_name
from astock_fundamentals.core.extraction_config import get_aliases


def main():
    # Initialize
    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    loader = RdsLoader(RDS_DIR)

    with open('data/decode_mappings_by_type.json', 'r', encoding='utf-8') as f:
        decode_maps = json.load(f)

    # Get all extracted stocks
    extracted_stocks = {}
    extracted_dir = 'data/extracted/by_code'
    for code in os.listdir(extracted_dir):
        code_dir = os.path.join(extracted_dir, code)
        if os.path.isdir(code_dir):
            files = [f for f in os.listdir(code_dir) if f.endswith('.json')]
            if files:
                extracted_stocks[code] = files

    print(f"Found {len(extracted_stocks)} stocks with extracted data")

    # Compare each stock
    all_results = []
    mismatched_items = defaultdict(list)

    for code, files in sorted(extracted_stocks.items()):
        # Find available years for this stock
        available_years = set()
        for f in files:
            parts = f.replace('.json', '').split('_')
            if len(parts) >= 3 and parts[1].isdigit():
                available_years.add(int(parts[1]))

        if not available_years:
            continue

        # Check which years have RDS data
        import pyreadr
        RDS_DIR = 'D:/Research/Quant/SETL/cninfo/data_backup'
        rds_years = set()
        for fname in ['pl_o.rds', 'b_o.rds', 'cf_o.rds']:
            df = pyreadr.read_r(os.path.join(RDS_DIR, fname))[None]
            subset = df[df['SECCODE'] == code]
            if len(subset) > 0:
                years_in_rds = subset['ENDDATE'].unique()
                rds_years.update(y for y in years_in_rds if y.startswith(('2019', '2020', '2021', '2022', '2023', '2024', '2025')))
            del df  # Free memory

        # Only compare years where both RDS and PDF have data
        comparable_years = available_years & rds_years
        if not comparable_years:
            continue

        print(f"\\nProcessing {code} (comparable years: {sorted(comparable_years)})...")

        for year in sorted(comparable_years):
            for st in ['income_statement', 'balance_sheet', 'cash_flow']:
                # Load RDS data
                try:
                    rds = loader.load_stock_data(code, year, st)
                except:
                    rds = {}

                if not rds:
                    continue

                # Load extracted data
                fname = os.path.join(extracted_dir, code, f'{code}_{year}_{st}.json')
                if not os.path.exists(fname):
                    continue

                with open(fname, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Try both formats: data.get('data', {}).get('data', {}) and data.get('data', {})
                ext_data = data.get('data', {}).get('data', {})
                if not ext_data:
                    ext_data = data.get('data', {})

            if not ext_data:
                continue

            # Run comparison
            aliases = get_aliases(st, 'annual')
            dm = decode_maps.get(st, {})
            comp = compare_stock(rds, ext_data, aliases, stock_code=code, year=year, statement_type=st, decode_map=dm)
            s = comp.summary()

            all_results.append({
                'stock': code,
                'year': year,
                'statement': st,
                'rds_items': len(rds),
                'ext_items': len(ext_data),
                'matched': s['matched'],
                'coverage': s['coverage'],
                'value_accuracy': s['value_accuracy'],
                'missing': s['missing'],
                'unmatched': s['unmatched'],
            })

            # Track mismatched items
            for item in comp.items:
                if item.match_type in ['missing', 'unmatched', 'value_diff']:
                    key = (item.ground_truth_name or item.extracted_name, st)
                    mismatched_items[key].append({
                        'stock': code,
                        'year': year,
                        'match_type': item.match_type,
                        'gt_name': item.ground_truth_name,
                        'ext_name': item.extracted_name,
                        'gt_val': item.ground_truth_value,
                        'ext_val': item.extracted_value,
                    })

    # Generate report
    print("\\n" + "="*70)
    print("COMPARISON REPORT: RDS vs PDF Extracted")
    print("="*70)

    # Summary
    total_matched = sum(r['matched'] for r in all_results)
    total_gt = sum(r['rds_items'] for r in all_results)
    total_ext = sum(r['ext_items'] for r in all_results)

    print(f"Total stocks compared: {len(set(r['stock'] for r in all_results))}")
    print(f"Total RDS items: {total_gt}")
    print(f"Total extracted items: {total_ext}")
    print(f"Total matched items: {total_matched}")
    print(f"Overall coverage: {total_matched/total_gt*100:.1f}%")

    # By statement type
    by_type = defaultdict(lambda: {'matched': 0, 'gt': 0, 'ext': 0})
    for r in all_results:
        by_type[r['statement']]['matched'] += r['matched']
        by_type[r['statement']]['gt'] += r['rds_items']
        by_type[r['statement']]['ext'] += r['ext_items']

    print("\\nBy statement type:")
    for st, stats in sorted(by_type.items()):
        print(f"  {st}: {stats['matched']}/{stats['gt']} matched ({stats['matched']/stats['gt']*100:.1f}%)")

    # Top mismatched items
    print("\\nTop mismatched items (sorted by frequency):")
    for (name, st), items in sorted(mismatched_items.items(), key=lambda x: -len(x[1]))[:20]:
        stocks = [i['stock'] for i in items]
        print(f"  {name} ({st}): {len(items)} occurrences in {len(set(stocks))} stocks")

    # Save results
    report = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_stocks': len(set(r['stock'] for r in all_results)),
            'total_rds_items': total_gt,
            'total_ext_items': total_ext,
            'total_matched': total_matched,
            'overall_coverage': total_matched/total_gt*100,
        },
        'by_type': {k: {'matched': v['matched'], 'gt': v['gt'], 'coverage': v['matched']/v['gt']*100}
                    for k, v in by_type.items()},
        'detailed_results': all_results,
        'mismatched_items': {f"{name} ({st})": items for (name, st), items in mismatched_items.items()},
    }

    report_path = os.path.join('data', 'ground_truth_reports', 'rds_vs_pdf_comparison.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\\nReport saved to: {report_path}")


if __name__ == '__main__':
    main()
