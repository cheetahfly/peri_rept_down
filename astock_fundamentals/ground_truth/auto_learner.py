# -*- coding: utf-8 -*-
"""
Auto-learner: discovers extraction patterns from RDS ground truth.

Uses a hybrid approach: name similarity for initial grouping,
value comparison for validation, and cross-stock evidence for confidence.
"""

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from astock_fundamentals.sources.rds.rds_loader import RdsLoader, META_COLS


@dataclass
class NameVariant:
    """A variant name for a financial item."""
    name: str
    stocks: Set[str] = field(default_factory=set)
    values: List[float] = field(default_factory=list)


@dataclass
class ItemPattern:
    """A discovered item pattern with name variations."""
    canonical_name: str
    variants: Dict[str, NameVariant] = field(default_factory=dict)
    confidence: float = 0.0


class AutoLearner:
    """Discovers name variations for financial items."""

    def __init__(self, rds_dir: str, decode_map_path: str = None):
        self.loader = RdsLoader(rds_dir, decode_map_path)

    def learn(
        self,
        stock_codes: List[str],
        years: List[int],
        statement_types: List[str] = None,
    ) -> Dict[str, ItemPattern]:
        """
        Learn name variations from multiple stocks.

        Returns: {canonical_name: ItemPattern}
        """
        if statement_types is None:
            statement_types = ["income_statement", "balance_sheet", "cash_flow"]

        # Phase 1: Collect all item names with their values
        all_items = defaultdict(lambda: NameVariant(name=""))
        all_items.clear()

        # Track which stocks have which names
        stock_names = defaultdict(set)  # stock_code -> set of names

        for stock_code in stock_codes:
            for year in years:
                for st in statement_types:
                    data = self.loader.load_stock_data(stock_code, year, st)
                    for name, value in data.items():
                        if name in META_COLS or "编码" in name or "来源" in name:
                            continue

                        if name not in all_items:
                            all_items[name] = NameVariant(name=name)

                        all_items[name].stocks.add(stock_code)
                        all_items[name].values.append(value)
                        stock_names[stock_code].add(name)

        # Phase 2: Group names that are variants of the same item
        patterns = self._find_variants(all_items, stock_names, stock_codes)

        return patterns

    def _find_variants(
        self,
        all_items: Dict[str, NameVariant],
        stock_names: Dict[str, Set[str]],
        stock_codes: List[str],
    ) -> Dict[str, ItemPattern]:
        """Find name variants using multiple signals."""
        patterns = {}
        processed = set()

        names = list(all_items.keys())

        for i, name1 in enumerate(names):
            if name1 in processed:
                continue

            # Find all names that are variants of name1
            variants = {name1: all_items[name1]}

            for j, name2 in enumerate(names[i+1:], i+1):
                if name2 in processed:
                    continue

                # Check if name1 and name2 are variants
                if self._are_variants(name1, name2, all_items, stock_names, stock_codes):
                    variants[name2] = all_items[name2]
                    processed.add(name2)

            if len(variants) > 1:
                # Choose canonical name (most frequent)
                canonical = max(variants.keys(), key=lambda n: len(variants[n].stocks))

                pattern = ItemPattern(
                    canonical_name=canonical,
                    variants=variants,
                    confidence=min(len(variants) / max(len(stock_codes), 1), 1.0),
                )
                patterns[canonical] = pattern
                processed.add(canonical)

        return patterns

    def _are_variants(
        self,
        name1: str,
        name2: str,
        all_items: Dict[str, NameVariant],
        stock_names: Dict[str, Set[str]],
        stock_codes: List[str],
    ) -> bool:
        """Check if two names are variants of the same item."""
        # Signal 1: Name similarity
        name_sim = self._name_similarity(name1, name2)

        # Signal 2: Never appear together in the same stock
        # (variants should be mutually exclusive)
        stocks1 = all_items[name1].stocks
        stocks2 = all_items[name2].stocks
        overlap = stocks1 & stocks2

        # If they appear together in many stocks, they're likely different items
        if len(overlap) > len(stock_codes) * 0.3:
            return False

        # Signal 3: Similar values in common stocks
        common_stocks = stocks1 & stocks2
        if len(common_stocks) >= 2:
            values1 = {sk: v for sk, v in zip(all_items[name1].stocks, all_items[name1].values) if sk in common_stocks}
            values2 = {sk: v for sk, v in zip(all_items[name2].stocks, all_items[name2].values) if sk in common_stocks}

            # Check if values are similar
            similar_values = 0
            for sk in common_stocks:
                if sk in values1 and sk in values2:
                    v1, v2 = values1[sk], values2[sk]
                    if v1 == 0 and v2 == 0:
                        similar_values += 1
                    elif v1 != 0 and v2 != 0:
                        error = abs(v1 - v2) / abs(v1)
                        if error < 0.1:
                            similar_values += 1

            if similar_values >= 2:
                return True

        # Signal 4: Strong name similarity
        if name_sim >= 0.8:
            return True

        # Signal 5: One name is a prefix/suffix of the other
        if self._is_prefix_variant(name1, name2):
            return True

        return False

    def _name_similarity(self, a: str, b: str) -> float:
        """Calculate similarity between two names."""
        if a == b:
            return 1.0

        # Normalize
        norm_a = self._normalize(a)
        norm_b = self._normalize(b)

        if norm_a == norm_b:
            return 1.0

        # Prefix/suffix match
        if norm_a.startswith(norm_b) or norm_b.startswith(norm_a):
            shorter, longer = (norm_a, norm_b) if len(norm_a) <= len(norm_b) else (norm_b, norm_a)
            if len(shorter) >= 3:
                return 0.8 + 0.2 * (len(shorter) / len(longer))

        # Substring containment
        if norm_a in norm_b or norm_b in norm_a:
            shorter, longer = (norm_a, norm_b) if len(norm_a) <= len(norm_b) else (norm_b, norm_a)
            if len(shorter) >= 3:
                return 0.7 + 0.3 * (len(shorter) / len(longer))

        # Fuzzy match
        return SequenceMatcher(None, norm_a, norm_b).ratio()

    def _normalize(self, name: str) -> str:
        """Normalize name for comparison."""
        # Remove common prefixes
        name = re.sub(r'^(其中[：:]|减[：:]|加[：:])', '', name)
        # Remove numbering
        name = re.sub(r'^[一二三四五六七八九十]+[、.]', '', name)
        name = re.sub(r'^[（(][一二三四五六七八九十1234567890]+[)）]', '', name)
        name = re.sub(r'^\d+[、.]', '', name)
        # Remove trailing notes
        name = re.sub(r'[（(][^)）]*[)）]$', '', name)
        return name.strip()

    def _is_prefix_variant(self, a: str, b: str) -> bool:
        """Check if one name is a prefix variant of the other."""
        # Common prefix patterns
        prefixes = ['其中：', '减：', '加：', '一、', '二、', '三、', '四、', '五、', '六、']
        for prefix in prefixes:
            if a.startswith(prefix) and a[len(prefix):] == b:
                return True
            if b.startswith(prefix) and b[len(prefix):] == a:
                return True
        return False

    def generate_alias_map(self, patterns: Dict[str, ItemPattern]) -> Dict[str, List[str]]:
        """Generate alias map from learned patterns."""
        alias_map = {}
        for canonical, pattern in patterns.items():
            variants = [name for name in pattern.variants.keys() if name != canonical]
            if variants:
                alias_map[canonical] = variants
        return alias_map

    def print_report(self, patterns: Dict[str, ItemPattern]):
        """Print a summary report."""
        print("\n" + "=" * 70)
        print("AUTO-LEARNING REPORT")
        print("=" * 70)
        print(f"\nDiscovered {len(patterns)} patterns with variations")

        for canonical, pattern in sorted(patterns.items(), key=lambda x: -x[1].confidence)[:15]:
            print(f"\n  [{pattern.confidence:.2f}] {canonical}")
            for name, variant in pattern.variants.items():
                stocks = len(variant.stocks)
                print(f"    - {name} (stocks: {stocks})")

        alias_map = self.generate_alias_map(patterns)
        print(f"\nAlias map entries: {len(alias_map)}")

        return alias_map
