# -*- coding: utf-8 -*-
"""
Rule cleaner: applies externalized rules to Sina financial data.

Responsibilities:
- Load rules (aliases, value mappings, unit overrides) from YAML.
- Rename Sina columns to RDS standard names.
- Convert values to a unified currency unit (yuan).
- Aggregate Sina sub-items into RDS totals.
- Mark unmatched columns.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd
import yaml


RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "rules",
)


@dataclass
class CleaningRules:
    aliases: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    aggregations: Dict[str, List[dict]] = field(default_factory=dict)
    unit_overrides: Dict[str, str] = field(default_factory=dict)
    skip_items: List[str] = field(default_factory=list)


def _merge_alias_block(target: dict, extra_text: Optional[str]) -> None:
    if not extra_text:
        return
    extra = yaml.safe_load(extra_text) or {}
    for stype, items in extra.items():
        target.setdefault(stype, {})
        for canonical, alts in items.items():
            target[stype].setdefault(canonical, [])
            for a in alts or []:
                if a not in target[stype][canonical]:
                    target[stype][canonical].append(a)


def load_cleaning_rules(
    aliases_path: str = None,
    value_mapping_path: str = None,
    skip_items_path: str = None,
    extra_aliases_text: Optional[str] = None,
) -> CleaningRules:
    """Load externalized cleaning rules from YAML files."""
    aliases = {}
    if aliases_path is None:
        aliases_path = os.path.join(RULES_DIR, "aliases.yaml")
    if os.path.exists(aliases_path):
        with open(aliases_path, "r", encoding="utf-8") as f:
            aliases = yaml.safe_load(f) or {}

    _merge_alias_block(aliases, extra_aliases_text)

    # Merge sina_aliases_2019_2022 into the annual report type of each statement type.
    sina_block = aliases.pop("sina_aliases_2019_2022", None) or {}
    for stype, items in sina_block.items():
        aliases.setdefault(stype, {})
        aliases[stype].setdefault("annual", {})
        for canonical, alts in items.items():
            aliases[stype]["annual"].setdefault(canonical, [])
            for a in alts or []:
                if a not in aliases[stype]["annual"][canonical]:
                    aliases[stype]["annual"][canonical].append(a)

    skip_items = []
    if skip_items_path is None:
        skip_items_path = os.path.join(RULES_DIR, "skip_items.yaml")
    if os.path.exists(skip_items_path):
        with open(skip_items_path, "r", encoding="utf-8") as f:
            skip_items = yaml.safe_load(f) or []

    # Load sina_aggregations_2019_2022 from value_mapping_rules.yaml.
    if value_mapping_path is None:
        value_mapping_path = os.path.join(RULES_DIR, "value_mapping_rules.yaml")
    aggregations: Dict[str, List[dict]] = {}
    if os.path.exists(value_mapping_path):
        try:
            with open(value_mapping_path, "r", encoding="utf-8") as f:
                vm = yaml.safe_load(f) or {}
            aggregations = vm.get("sina_aggregations_2019_2022", {}) or {}
        except yaml.YAMLError:
            # Pre-existing YAML issue in the file — proceed with empty aggregations
            aggregations = {}

    return CleaningRules(
        aliases=aliases,
        aggregations=aggregations,
        skip_items=list(skip_items),
    )


def _build_reverse_alias_map(statement_type: str, rules: CleaningRules) -> Dict[str, str]:
    """Build {sina_name: rds_standard_name} for one statement type."""
    reverse: Dict[str, str] = {}
    for canonical, alts in rules.aliases.get(statement_type, {}).items():
        for alt in alts or []:
            reverse[alt] = canonical
    return reverse


def rename_columns(df: pd.DataFrame, statement_type: str, rules: CleaningRules) -> pd.DataFrame:
    """Rename Sina columns to RDS canonical names. Unknown columns kept as-is."""
    reverse = _build_reverse_alias_map(statement_type, rules)
    return df.rename(columns={k: v for k, v in reverse.items() if k in df.columns})


_UNIT_MULTIPLIERS = {
    "元": 1,
    "万元": 10000,
    "千元": 1000,
    "百万": 1000000,
    "亿元": 100000000,
}


def convert_values(df: pd.DataFrame, rules: CleaningRules) -> pd.DataFrame:
    """Convert values to yuan using unit_overrides map."""
    out = df.copy()
    for col, unit in rules.unit_overrides.items():
        if col in out.columns and unit in _UNIT_MULTIPLIERS:
            out[col] = pd.to_numeric(out[col], errors="coerce") * _UNIT_MULTIPLIERS[unit]
    return out


def _aggregate_column(series_list: List[pd.Series], op: str) -> pd.Series:
    aligned = pd.concat(series_list, axis=1)
    if op == "sum":
        return aligned.sum(axis=1, min_count=1)
    if op == "first":
        return aligned.iloc[:, 0]
    if op == "max":
        return aligned.max(axis=1)
    raise ValueError(f"Unknown aggregation op: {op}")


def apply_aggregations(df: pd.DataFrame, statement_type: str, rules: CleaningRules) -> pd.DataFrame:
    """Aggregate Sina sub-items into RDS totals based on rules."""
    out = df.copy()
    for rule in rules.aggregations.get(statement_type, []):
        sources = rule.get("sources") or []
        op = rule.get("op", "sum")
        present = [s for s in sources if s in out.columns]
        if not present:
            continue
        out[rule["target"]] = _aggregate_column([out[s] for s in present], op)
    return out