# -*- coding: utf-8 -*-
"""
建立金融股 EM 字段 → RDS 字段映射（基于 value-match）。

输入：
  - tmp/eval_financial_cf_2020/600036_em_yearly.csv
  - tmp/eval_financial_cf_2020/600036_rds_standard.json
输出：
  - rules/cf_field_map_financial.yaml
"""
import json
import os
import sys

import pandas as pd
import yaml

sys.path.insert(0, 'scripts')
from akshare_cf_test_compare import normalize_value, best_match  # noqa: E402

EM_CSV = 'tmp/eval_financial_cf_2020/600036_em_yearly.csv'
RDS_JSON = 'tmp/eval_financial_cf_2020/600036_rds_standard.json'
OUT_YAML = 'rules/cf_field_map_financial.yaml'

EM_EXCLUDE = {
    "SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "ORG_CODE", "ORG_TYPE",
    "REPORT_DATE", "REPORT_TYPE", "REPORT_DATE_NAME", "SECURITY_TYPE_CODE",
    "NOTICE_DATE", "UPDATE_DATE", "CURRENCY", "LISTING_STATE", "OPINION_TYPE",
    "OPDATE", "OSOPINION_TYPE",
}


def main():
    with open(RDS_JSON, 'r', encoding='utf-8') as f:
        rds = json.load(f)
    df = pd.read_csv(EM_CSV)
    mask = df['REPORT_DATE'].astype(str).str.startswith('2020-12-31')
    if mask.sum() == 0:
        raise SystemExit('no 2020-12-31 row in EM CSV')
    r = df[mask].iloc[0].to_dict()
    em_values = {
        c: normalize_value(v)
        for c, v in r.items()
        if c not in EM_EXCLUDE and not c.endswith('_YOY') and normalize_value(v) is not None
    }
    print(f'EM fields: {len(em_values)}, RDS items: {len(rds)}')

    mapping_exact = []
    mismatches = []
    for item in rds:
        if item['value'] is None:
            continue
        label, ch_v, diff, rel = best_match(item['value'], em_values)
        if diff is not None and diff < 0.01:
            mapping_exact.append({
                'rds_code': item['item_code'],
                'rds_name': item['item_name'],
                'em_field': label,
            })
        else:
            mismatches.append({
                'rds_code': item['item_code'],
                'rds_name': item['item_name'],
                'rds_value': item['value'],
                'em_field': label,
                'em_value': ch_v,
                'abs_diff': diff,
                'rel_err': rel,
            })

    os.makedirs(os.path.dirname(OUT_YAML), exist_ok=True)
    with open(OUT_YAML, 'w', encoding='utf-8') as f:
        yaml.safe_dump(
            {
                'description': '600036 招商银行 2020 年报 EM yearly → RDS 字段映射（value-match exact only）',
                'baseline_stock': '600036',
                'baseline_year': 2020,
                'em_to_rds': mapping_exact,
            },
            f, allow_unicode=True, sort_keys=False,
        )
    print(f'exact mapped: {len(mapping_exact)}/{len(rds)}')
    print(f'YAML 写入 {OUT_YAML}')

    # 保存 mismatches 供人工审查
    with open('tmp/eval_financial_cf_2020/_mapping_mismatches.json', 'w', encoding='utf-8') as f:
        json.dump(mismatches, f, ensure_ascii=False, indent=2)
    print(f'mismatches saved: tmp/eval_financial_cf_2020/_mapping_mismatches.json (count={len(mismatches)})')


if __name__ == '__main__':
    main()
