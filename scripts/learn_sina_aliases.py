#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sina→RDS alias learner.

For each (stock, year, statement_type) in scope, load:
  - RDS data: {rds_chinese_name: value}
  - Sina data: {sina_chinese_name: value} (from one annual row)

Compare every (sina_name, rds_name) pair across all data points.
Pairs with at least N exact value matches (relative error < TOL) become
sina_aliases_2019_2022 rules written to rules/aliases.yaml.

Also detects sub-item aggregation: when one RDS value equals the sum
of multiple Sina columns (sub-items), generates an aggregation rule.
"""

import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.sina_loader import SinaLoader

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE, "data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
ALIASES_PATH = os.path.join(BASE, "rules", "aliases.yaml")
VALUE_MAPPING_PATH = os.path.join(BASE, "rules", "value_mapping_rules.yaml")

YEARS = [2019, 2020, 2021, 2022]
SAMPLE_STOCKS = ["000001", "600000", "600036", "600519", "000002", "000858"]
STATEMENT_TYPES = ["balance_sheet", "income_statement", "cash_flow"]
META_COLS = {"报告日", "数据源", "是否审计", "公告日期", "币种", "类型", "更新日期"}
EXACT_TOL = 0.001  # relative tolerance for value match
MIN_EVIDENCE = 4   # at least 4 (stock, year) pairs must agree
MIN_NAME_SIM = 0.5  # name similarity threshold (filter spurious value-only matches)


def _sina_row_to_dict(row) -> Dict[str, float]:
    out = {}
    for k, v in row.items():
        if k in META_COLS:
            continue
        if v is None:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _values_close(a: float, b: float, tol: float = EXACT_TOL) -> bool:
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return False
    return abs(a - b) / max(abs(a), abs(b)) < tol


def _name_similarity(a: str, b: str) -> float:
    """Token-overlap based similarity (handles Chinese substring matches)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Substring containment (handles 其中: vs 营业收入)
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer and len(shorter) >= 2:
        return len(shorter) / len(longer)
    # Common character overlap
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def learn_aliases(stocks: List[str] = None, years: List[int] = None) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """Discover exact-value aliases from cross-source value matching.

    Args:
        stocks: Stock codes to use. Defaults to SAMPLE_STOCKS.
        years: Years to use. Defaults to YEARS.

    Returns:
        aliases_by_type: {statement_type: [{rds_name, sina_names, evidence}, ...]}
        aggregations: [{statement_type, target, sources, op, evidence}, ...]
    """
    if stocks is None:
        stocks = SAMPLE_STOCKS
    if years is None:
        years = YEARS
    sina = SinaLoader(CACHE_DIR)
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)

    # For each (statement_type, sina_name, rds_name), count exact value matches.
    match_count: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    # For each (statement_type, rds_name), list of (stock, year) where it appears
    rds_presence: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    sina_names_by_st: Dict[str, set] = defaultdict(set)

    for code in stocks:
        for st in STATEMENT_TYPES:
            try:
                sina_df = sina.get_annual(code, years, st)
            except FileNotFoundError:
                continue
            if sina_df.empty:
                continue
            for _, row in sina_df.iterrows():
                period = str(row.get("报告日", ""))
                if not period.endswith("1231"):
                    continue
                year = int(period[:4])
                sina_dict = _sina_row_to_dict(row)
                if not sina_dict:
                    continue
                gt_data = rds.load_stock_data(code, year, st)
                if not gt_data:
                    continue
                sina_names_by_st[st].update(sina_dict.keys())
                for rds_name, rds_val in gt_data.items():
                    rds_presence[st][rds_name].add((code, year))
                    for sina_name, sina_val in sina_dict.items():
                        if _values_close(sina_val, rds_val):
                            match_count[st][sina_name][rds_name] += 1

    # Build alias rules
    aliases_by_type: Dict[str, List[dict]] = {}
    for st in STATEMENT_TYPES:
        aliases_by_type[st] = []
        seen = set()  # (rds_name, sina_name) pairs to avoid duplicates
        for sina_name, rds_map in match_count[st].items():
            for rds_name, cnt in rds_map.items():
                if cnt < MIN_EVIDENCE:
                    continue
                if sina_name == rds_name:
                    continue
                if _name_similarity(sina_name, rds_name) < MIN_NAME_SIM:
                    continue
                key = (rds_name, sina_name)
                if key in seen:
                    continue
                seen.add(key)
                aliases_by_type[st].append({
                    "rds_name": rds_name,
                    "sina_names": [sina_name],
                    "evidence": cnt,
                })

    # Sort each type by evidence desc
    for st in aliases_by_type:
        aliases_by_type[st].sort(key=lambda x: -x["evidence"])

    # Detect aggregations: a rds value that equals the sum of multiple
    # sina values with the same prefix (e.g. 其他应收款-关联方 + 其他应收款-外部 = 其他应收款)
    aggregations: List[dict] = []
    for st in STATEMENT_TYPES:
        # For each rds name, find sina names that share a prefix
        rds_names = list(rds_presence[st].keys())
        for rds_name in rds_names:
            prefix = rds_name[:max(1, len(rds_name) // 2)]  # crude prefix
            candidates = [
                sn for sn in sina_names_by_st[st]
                if sn != rds_name and sn.startswith(prefix) and len(sn) > len(prefix)
            ]
            if len(candidates) < 2:
                continue
            # Check if at least 3 (stock, year) pairs have rds_val == sum(sina_vals)
            evidence = 0
            for code, year in list(rds_presence[st][rds_name])[:20]:  # limit work
                try:
                    sina_df = sina.get_annual(code, [year], st)
                except FileNotFoundError:
                    continue
                if sina_df.empty:
                    continue
                row = sina_df[sina_df["报告日"].astype(str) == f"{year}1231"]
                if row.empty:
                    continue
                sina_dict = _sina_row_to_dict(row.iloc[0])
                rds_data = rds.load_stock_data(code, year, st)
                rds_val = rds_data.get(rds_name)
                if rds_val is None:
                    continue
                sina_sum = sum(sina_dict.get(c, 0) for c in candidates)
                if _values_close(rds_val, sina_sum, tol=0.005):
                    evidence += 1
            if evidence >= MIN_EVIDENCE:
                aggregations.append({
                    "statement_type": st,
                    "target": rds_name,
                    "sources": candidates,
                    "op": "sum",
                    "evidence": evidence,
                })

    return aliases_by_type, aggregations


def _safe_load_yaml(path: str) -> dict:
    """Load YAML; on parse error fall back to extracting just the target block via regex."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        # Fallback: extract sina_* blocks via regex
        import re
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        result = {}
        for key in ("sina_aliases_2019_2022", "sina_aggregations_2019_2022"):
            m = re.search(rf"^{key}:\s*\n((?:  .*\n)*)", text, re.MULTILINE)
            if m:
                try:
                    result[key] = yaml.safe_load(m.group(1)) or {}
                except yaml.YAMLError:
                    result[key] = {}
            else:
                result[key] = {}
        return result


def write_to_yaml(
    aliases_by_type: Dict[str, List[dict]],
    aggregations: List[dict],
) -> None:
    """Append discovered rules to existing YAML files (with regex fallback for parse-broken files)."""
    # ---- aliases.yaml: populate sina_aliases_2019_2022 ----
    aliases_doc = _safe_load_yaml(ALIASES_PATH)

    new_block = aliases_doc.get("sina_aliases_2019_2022", {})
    if not isinstance(new_block, dict):
        new_block = {}
    summary = {}
    for st, items in aliases_by_type.items():
        st_block = new_block.get(st, {}) or {}
        for item in items:
            rds_name = item["rds_name"]
            existing = st_block.get(rds_name, []) or []
            for sn in item["sina_names"]:
                if sn not in existing and sn != rds_name:
                    existing.append(sn)
            st_block[rds_name] = existing
        new_block[st] = st_block
        summary[st] = len(items)
    aliases_doc["sina_aliases_2019_2022"] = new_block

    with open(ALIASES_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(aliases_doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"  wrote {sum(summary.values())} alias rules to {ALIASES_PATH}")
    print(f"    by statement: {summary}")

    # ---- value_mapping_rules.yaml: populate sina_aggregations_2019_2022 ----
    vm_doc = _safe_load_yaml(VALUE_MAPPING_PATH)

    new_agg = vm_doc.get("sina_aggregations_2019_2022", {})
    if not isinstance(new_agg, dict):
        new_agg = {}
    agg_summary = {"balance_sheet": 0, "income_statement": 0, "cash_flow": 0}
    for agg in aggregations:
        st = agg["statement_type"]
        existing = new_agg.get(st, []) or []
        # Avoid duplicate (target, sources) entries
        if not any(a.get("target") == agg["target"] and a.get("sources") == agg["sources"] for a in existing):
            existing.append({
                "target": agg["target"],
                "sources": agg["sources"],
                "op": agg["op"],
                "evidence": agg["evidence"],
            })
            agg_summary[st] += 1
        new_agg[st] = existing
    vm_doc["sina_aggregations_2019_2022"] = new_agg

    with open(VALUE_MAPPING_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(vm_doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"  wrote {sum(agg_summary.values())} aggregation rules to {VALUE_MAPPING_PATH}")
    print(f"    by statement: {agg_summary}")


def main() -> int:
    # Resolve stocks/years from CLI
    years, stocks, industries, min_evidence_override = _parse_cli_args()
    # Override module-level MIN_EVIDENCE if CLI provided
    if min_evidence_override is not None:
        global MIN_EVIDENCE
        MIN_EVIDENCE = min_evidence_override
    print(f"Learning from {len(stocks)} stocks x {len(years)} years x {len(STATEMENT_TYPES)} types")
    if industries:
        print(f"  industries: {industries}")
    print(f"  min evidence: {MIN_EVIDENCE} matches, tol: {EXACT_TOL}")
    aliases_by_type, aggregations = learn_aliases(stocks=stocks, years=years)
    total = sum(len(v) for v in aliases_by_type.values())
    print(f"Discovered {total} alias rules and {len(aggregations)} aggregation rules")
    if total == 0 and len(aggregations) == 0:
        print("Nothing to write.")
        return 0
    write_to_yaml(aliases_by_type, aggregations)
    return 0


def _parse_cli_args():
    """Parse --stocks / --years / --industries from sys.argv. Falls back to defaults."""
    import argparse
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--stocks", nargs="+", default=None)
    p.add_argument("--years", nargs="+", default=None)
    p.add_argument("--industries", nargs="+", default=None)
    p.add_argument("--min-evidence", type=int, default=None)
    p.add_argument("--tol", type=float, default=None)
    p.add_argument("--cache-dir", default=CACHE_DIR)
    p.add_argument("--rds-dir", default=RDS_DIR)
    args, _unknown = p.parse_known_args()

    # Override module-level MIN_EVIDENCE from CLI if provided
    global MIN_EVIDENCE
    if args.min_evidence is not None:
        MIN_EVIDENCE = args.min_evidence

    stocks = args.stocks
    if args.industries and "none" not in args.industries:
        from pathlib import Path
        ind_path = Path(__file__).parent.parent / "rules" / "industry_aliases.yaml"
        try:
            with open(ind_path, "r", encoding="utf-8") as f:
                ind_doc = yaml.safe_load(f) or {}
        except FileNotFoundError:
            ind_doc = {}
        ind_defs = ind_doc.get("industries", {}) or {}
        default_pool = ind_doc.get("default_pool", []) or []
        resolved: list = []
        for name in args.industries:
            if name in ("all", "default"):
                for s in default_pool:
                    if s not in resolved: resolved.append(s)
                continue
            ind = ind_defs.get(name) or {}
            for s in ind.get("stocks", []):
                if s not in resolved: resolved.append(s)
        stocks = resolved or SAMPLE_STOCKS

    years = [int(y) for y in args.years] if args.years else YEARS
    return years, (stocks or SAMPLE_STOCKS), args.industries or [], args.min_evidence


if __name__ == "__main__":
    raise SystemExit(main())
