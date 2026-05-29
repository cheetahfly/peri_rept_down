# -*- coding: utf-8 -*-
"""
Gap analyzer - analyzes comparison results and generates improvement suggestions.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from astock_fundamentals.ground_truth.comparator import ComparisonResult, normalize_name


@dataclass
class RuleSuggestion:
    category: str  # alias, normalize_pattern, standard_items
    action: str    # add_alias, add_pattern, add_standard_item
    target: str    # config variable name
    key: str       # standard name
    value: Any     # new alias list or pattern
    confidence: float
    evidence: List[str] = field(default_factory=list)
    description: str = ""


def analyze_gaps(
    results: List[ComparisonResult],
    alias_map: Dict[str, List[str]],
    standard_items: Dict[str, List[str]],
) -> Dict:
    suggestions = []
    stats = defaultdict(lambda: {"matched": 0, "missing": 0, "unmatched": 0})

    # Collect all missing and unmatched items across results
    all_missing = defaultdict(list)  # gt_name -> [stock/year evidence]
    all_unmatched = defaultdict(list)  # ext_name -> [stock/year evidence]

    for r in results:
        key = f"{r.stock_code}/{r.year}"
        stats[r.statement_type]["matched"] += len(r.matched)
        stats[r.statement_type]["missing"] += len(r.missing)
        stats[r.statement_type]["unmatched"] += len(r.unmatched)

        for item in r.missing:
            all_missing[item.ground_truth_name].append(key)

        for item in r.unmatched:
            if item.extracted_name:
                all_unmatched[item.extracted_name].append(key)

    # Generate alias suggestions: unmatched extracted items similar to missing GT items
    for ext_name, ext_evidence in all_unmatched.items():
        norm_ext = normalize_name(ext_name)
        for gt_name, gt_evidence in all_missing.items():
            norm_gt = normalize_name(gt_name)
            score = SequenceMatcher(None, norm_ext, norm_gt).ratio()
            # Also check substring containment
            if norm_ext in norm_gt or norm_gt in norm_ext:
                score = max(score, 0.8)
            if score >= 0.5:
                # Found a potential alias mapping
                # Determine which standard name to map to
                # The GT name is the standard, the extracted name is the variant
                confidence = min(len(ext_evidence), len(gt_evidence)) / max(
                    len(set(ext_evidence) | set(gt_evidence)), 1
                )
                suggestions.append(RuleSuggestion(
                    category="alias",
                    action="add_alias",
                    target="ITEM_ALIAS_MAP",
                    key=gt_name,
                    value=[ext_name],
                    confidence=round(confidence, 3),
                    evidence=list(set(ext_evidence + gt_evidence)),
                    description=f"Extracted '{ext_name}' likely maps to GT '{gt_name}' (similarity={score:.2f})",
                ))

    # Generate standard item suggestions: missing items that appear in multiple stocks
    for gt_name, evidence in all_missing.items():
        if len(evidence) >= 2:
            norm_gt = normalize_name(gt_name)
            # Check if this item is already in standard items
            already_standard = False
            for st, items in standard_items.items():
                for item in items:
                    if normalize_name(item) == norm_gt:
                        already_standard = True
                        break
            if not already_standard:
                confidence = len(evidence) / max(len(results), 1)
                suggestions.append(RuleSuggestion(
                    category="standard_items",
                    action="add_standard_item",
                    target="STATEMENT_TYPE_STANDARD_ITEMS",
                    key=gt_name,
                    value=None,
                    confidence=round(confidence, 3),
                    evidence=evidence,
                    description=f"Item '{gt_name}' missing in {len(evidence)} extractions",
                ))

    # Deduplicate suggestions by (key, value)
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        sig = (s.key, str(s.value))
        if sig not in seen:
            seen.add(sig)
            unique_suggestions.append(s)

    # Sort by confidence
    unique_suggestions.sort(key=lambda x: -x.confidence)

    return {
        "stats": dict(stats),
        "suggestions": unique_suggestions,
        "missing_items": {k: v for k, v in all_missing.items()},
        "unmatched_items": {k: v for k, v in all_unmatched.items()},
    }


def suggestions_to_json(analysis: Dict) -> Dict:
    return {
        "stats": analysis["stats"],
        "suggestions_count": len(analysis["suggestions"]),
        "suggestions": [
            {
                "category": s.category,
                "action": s.action,
                "key": s.key,
                "value": s.value,
                "confidence": s.confidence,
                "evidence": s.evidence,
                "description": s.description,
            }
            for s in analysis["suggestions"]
        ],
        "missing_items": analysis["missing_items"],
        "unmatched_items": analysis["unmatched_items"],
    }


def _values_match(val1: Optional[float], val2: Optional[float], tolerance: float = 0.01) -> bool:
    """Check if two values match within tolerance (for financial data, typically 2 decimal places)"""
    if val1 is None or val2 is None:
        return False
    if val1 == val2:
        return True
    # Allow small floating point errors
    return abs(val1 - val2) <= tolerance


# Keywords that help identify statement type from item name
INCOME_KEYWORDS = {"收入", "成本", "费用", "利润", "收益", "税", "净利润", "营业"}
BALANCE_KEYWORDS = {"资产", "负债", "权益", "借款", "应收", "应付", "货币", "存货", "固定资产"}
CASHFLOW_KEYWORDS = {"现金", "流量", "活动"}


def _infer_statement_type(item_name: str) -> Optional[str]:
    """Infer statement type from item name"""
    name = normalize_name(item_name)

    # Check cash flow first (most specific)
    if any(kw in name for kw in CASHFLOW_KEYWORDS):
        return "cash_flow"

    # Check income statement
    if any(kw in name for kw in INCOME_KEYWORDS):
        return "income_statement"

    # Check balance sheet
    if any(kw in name for kw in BALANCE_KEYWORDS):
        return "balance_sheet"

    return None


def analyze_value_matches(
    results: List[ComparisonResult],
    alias_map: Dict[str, List[str]],
    min_stocks: int = 2,
) -> List[RuleSuggestion]:
    """
    Discover alias mappings by matching values between extracted and ground truth items.

    Logic:
    1. For each unmatched extracted item, find missing GT items with the same value
    2. If values match across multiple stocks, create an alias suggestion
    3. This catches naming differences that text similarity alone misses

    Args:
        results: List of comparison results from multiple stocks
        alias_map: Current alias mapping (to avoid duplicate suggestions)
        min_stocks: Minimum number of stocks that must agree for a suggestion

    Returns:
        List of RuleSuggestion for new alias mappings
    """
    # Track value matches: (statement_type, ext_name, gt_name) -> list of (stock_code, year, value)
    value_matches = defaultdict(list)

    for r in results:
        if not r.stock_code or not r.year:
            continue

        key = f"{r.stock_code}/{r.year}"
        stmt_type = r.statement_type  # Track statement type

        # Build lookup of missing GT items by value
        missing_by_value = {}
        for item in r.missing:
            if item.ground_truth_value is not None:
                # Round to 2 decimal places for matching
                rounded_val = round(item.ground_truth_value, 2)
                if rounded_val not in missing_by_value:
                    missing_by_value[rounded_val] = []
                missing_by_value[rounded_val].append(item.ground_truth_name)

        # Check each unmatched extracted item
        for item in r.unmatched:
            if item.extracted_value is None or item.extracted_name is None:
                continue

            rounded_ext_val = round(item.extracted_value, 2)
            if rounded_ext_val in missing_by_value:
                for gt_name in missing_by_value[rounded_ext_val]:
                    # Skip if already mapped
                    norm_ext = normalize_name(item.extracted_name)
                    norm_gt = normalize_name(gt_name)

                    # Check if already in alias map
                    already_mapped = False
                    if norm_gt in alias_map:
                        for variant in alias_map[norm_gt]:
                            if normalize_name(variant) == norm_ext:
                                already_mapped = True
                                break

                    if not already_mapped:
                        # Additional check: infer statement types from names
                        inferred_ext = _infer_statement_type(item.extracted_name)
                        inferred_gt = _infer_statement_type(gt_name)

                        # If we can infer types, they must match
                        if inferred_ext and inferred_gt and inferred_ext != inferred_gt:
                            continue

                        # Only match within the same statement type!
                        value_matches[(stmt_type, item.extracted_name, gt_name)].append({
                            "stock": r.stock_code,
                            "year": r.year,
                            "value": rounded_ext_val,
                        })

    # Generate suggestions for matches that appear in multiple stocks
    suggestions = []
    seen = set()

    for (stmt_type, ext_name, gt_name), evidence in value_matches.items():
        # Count unique stocks
        unique_stocks = len(set(e["stock"] for e in evidence))

        if unique_stocks >= min_stocks:
            sig = (gt_name, ext_name)
            if sig not in seen:
                seen.add(sig)
                confidence = min(unique_stocks / 3, 1.0)  # Max confidence at 3 stocks
                suggestions.append(RuleSuggestion(
                    category="alias",
                    action="add_alias",
                    target="ITEM_ALIAS_MAP",
                    key=gt_name,
                    value=[ext_name],
                    confidence=round(confidence, 3),
                    evidence=[f"{e['stock']}/{e['year']} (value={e['value']})" for e in evidence],
                    description=f"Value match [{stmt_type}]: '{ext_name}' = '{gt_name}' (same value in {unique_stocks} stocks)",
                ))

    suggestions.sort(key=lambda x: -x.confidence)
    return suggestions


class GapAnalyzer:
    """Analyzes comparison report dicts and suggests new aliases.

    Works with the detailed_report() output from ComparisonResult.
    """

    def __init__(self, min_similarity: float = 0.7):
        self.min_similarity = min_similarity

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Calculate name similarity between two strings."""
        if a == b:
            return 1.0
        if a in b or b in a:
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            return 0.7 + 0.3 * (len(shorter) / len(longer))
        return SequenceMatcher(None, a, b).ratio()

    def analyze(self, report: Dict) -> List[Dict]:
        """Analyze a detailed report and suggest aliases.

        Args:
            report: Dict with keys: missing_items, unmatched_items, value_diffs
                    (output of ComparisonResult.detailed_report())

        Returns:
            List of suggestion dicts with type, standard_name, variants/reason.
        """
        suggestions = []

        missing = report.get("missing_items", [])
        unmatched = report.get("unmatched_items", [])

        # Group unmatched by potential standard name
        unmatched_groups = defaultdict(list)
        for item in unmatched:
            unmatched_groups[item["name"]].append(item)

        # Try to match each missing item to unmatched items
        for missing_item in missing:
            missing_name = missing_item["name"]
            missing_code = missing_item.get("code")

            similar_variants = []
            for unmatched_name in unmatched_groups:
                similarity = self._name_similarity(missing_name, unmatched_name)
                if similarity >= self.min_similarity:
                    similar_variants.append(unmatched_name)

            if similar_variants:
                suggestions.append({
                    "type": "alias_suggestion",
                    "standard_name": missing_name,
                    "code": missing_code,
                    "variants": similar_variants,
                    "reason": "unmatched_item_similar_to_missing",
                })

        # Check for value mismatches (potential unit differences)
        value_diffs = report.get("value_diffs", [])
        for diff in value_diffs:
            gt_val = diff.get("ground_truth_value")
            ext_val = diff.get("extracted_value")
            if gt_val and ext_val:
                ratio = gt_val / ext_val
                if 9900 < ratio < 10100:  # ~10000x
                    suggestions.append({
                        "type": "unit_suggestion",
                        "standard_name": diff["name"],
                        "code": diff.get("code"),
                        "suggested_unit": "万元",
                        "reason": "value_off_by_10000x",
                    })
                elif 0.00009 < ratio < 0.00011:  # ~1/10000
                    suggestions.append({
                        "type": "unit_suggestion",
                        "standard_name": diff["name"],
                        "code": diff.get("code"),
                        "suggested_unit": "亿元",
                        "reason": "value_off_by_1billion",
                    })

        return suggestions

    def generate_yaml_updates(
        self, suggestions: List[Dict], statement_type: str = "income_statement"
    ) -> Dict[str, Dict[str, List[str]]]:
        """Generate YAML update structure from suggestions.

        Args:
            suggestions: Output of analyze().
            statement_type: Default statement type for alias suggestions.

        Returns:
            Dict mapping statement_type -> standard_name -> list of variants.
        """
        updates = defaultdict(lambda: defaultdict(list))

        for suggestion in suggestions:
            if suggestion["type"] == "alias_suggestion":
                standard = suggestion["standard_name"]
                variants = suggestion["variants"]
                updates[statement_type][standard].extend(variants)

        return dict(updates)

    def print_report(self, suggestions: List[Dict]) -> List[Dict]:
        """Print a summary of suggestions and return them."""
        print("\n" + "=" * 70)
        print("GAP ANALYSIS REPORT")
        print("=" * 70)

        alias_suggestions = [s for s in suggestions if s["type"] == "alias_suggestion"]
        unit_suggestions = [s for s in suggestions if s["type"] == "unit_suggestion"]

        print(f"\nAlias suggestions: {len(alias_suggestions)}")
        for s in alias_suggestions[:10]:
            print(f"  {s['standard_name']}: {s['variants']}")

        print(f"\nUnit suggestions: {len(unit_suggestions)}")
        for s in unit_suggestions[:5]:
            print(f"  {s['standard_name']}: {s['suggested_unit']}")

        return suggestions
