# -*- coding: utf-8 -*-
"""
Item mapper: finds mappings between extracted item names and RDS ground truth.

Analyzes extracted data and RDS data to discover how extracted names
map to standard RDS names.
"""

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set

from extraction.ground_truth.comparator import normalize_name, load_extracted_json
from extraction.ground_truth.rds_loader import RdsLoader, META_COLS


@dataclass
class NameMapping:
    """A mapping from extracted name to RDS name."""
    extracted_name: str
    rds_name: str
    confidence: float
    evidence: List[str] = field(default_factory=list)  # stock/year pairs
    values_compared: int = 0
    values_matched: int = 0


class ItemMapper:
    """Finds mappings between extracted and RDS item names."""

    def __init__(self, rds_dir: str, extracted_dir: str, decode_map_path: str = None):
        self.loader = RdsLoader(rds_dir, decode_map_path)
        self.extracted_dir = extracted_dir

    def discover_mappings(
        self,
        stock_codes: List[str],
        years: List[int],
        statement_types: List[str] = None,
    ) -> List[NameMapping]:
        """
        Discover mappings between extracted and RDS names.

        Returns: list of NameMapping
        """
        if statement_types is None:
            statement_types = ["income_statement", "balance_sheet", "cash_flow"]

        # Collect all mappings across stocks
        all_mappings = defaultdict(lambda: {
            "rds_name": "",
            "evidence": [],
            "values_compared": 0,
            "values_matched": 0,
        })

        for stock_code in stock_codes:
            for year in years:
                for st in statement_types:
                    # Load RDS data
                    gt_data = self.loader.load_stock_data(stock_code, year, st)
                    if not gt_data:
                        continue

                    # Load extracted data
                    ext_data = self._load_extracted(stock_code, year, st)
                    if not ext_data:
                        continue

                    # Find mappings
                    mappings = self._find_mappings(gt_data, ext_data, stock_code, year, st)
                    for ext_name, rds_name, confidence, values_compared, values_matched in mappings:
                        key = (ext_name, rds_name)
                        all_mappings[key]["rds_name"] = rds_name
                        all_mappings[key]["evidence"].append(f"{stock_code}/{year}")
                        all_mappings[key]["values_compared"] += values_compared
                        all_mappings[key]["values_matched"] += values_matched

        # Convert to NameMapping list
        result = []
        for (ext_name, rds_name), info in all_mappings.items():
            if len(info["evidence"]) >= 2:  # Appears in at least 2 stocks
                confidence = min(info["values_matched"] / max(info["values_compared"], 1), 1.0)
                result.append(NameMapping(
                    extracted_name=ext_name,
                    rds_name=rds_name,
                    confidence=confidence,
                    evidence=info["evidence"],
                    values_compared=info["values_compared"],
                    values_matched=info["values_matched"],
                ))

        # Sort by confidence
        result.sort(key=lambda m: -m.confidence)
        return result

    def _find_mappings(
        self,
        gt_data: Dict[str, float],
        ext_data: Dict[str, float],
        stock_code: str,
        year: int,
        statement_type: str,
    ) -> List[tuple]:
        """Find mappings between GT and extracted data for one stock."""
        mappings = []

        # Build normalized extracted names
        norm_ext = {}
        for ext_name, ext_val in ext_data.items():
            norm = normalize_name(ext_name)
            if norm and norm not in ("", "行") and not re.match(r'^行\d+$', norm):
                norm_ext[norm] = (ext_name, ext_val)

        # Match each GT item to extracted items
        for gt_name, gt_val in gt_data.items():
            if gt_name in META_COLS or "编码" in gt_name or "来源" in gt_name:
                continue

            norm_gt = normalize_name(gt_name)

            # Find best matching extracted item
            best_match = None
            best_score = 0.0

            for norm_ext_name, (ext_name, ext_val) in norm_ext.items():
                # Name similarity
                name_sim = self._name_similarity(norm_gt, norm_ext_name)

                # Value similarity
                val_sim = self._value_similarity(gt_val, ext_val)

                # Combined score (name is primary)
                score = 0.7 * name_sim + 0.3 * val_sim

                if score > best_score and score >= 0.6:
                    best_score = score
                    best_match = (ext_name, name_sim, val_sim)

            if best_match:
                ext_name, name_sim, val_sim = best_match
                values_compared = 1
                values_matched = 1 if val_sim > 0.9 else 0

                mappings.append((
                    ext_name,
                    gt_name,
                    best_score,
                    values_compared,
                    values_matched,
                ))

        return mappings

    def _load_extracted(self, stock_code: str, year: int, statement_type: str) -> Dict[str, float]:
        """Load extracted JSON data."""
        fname = f"{stock_code}_{year}_{statement_type}.json"
        path = os.path.join(self.extracted_dir, stock_code, fname)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        inner = data.get("data", data)
        if isinstance(inner, dict) and "data" in inner:
            return inner["data"]
        return {}

    def _name_similarity(self, a: str, b: str) -> float:
        """Calculate name similarity."""
        if a == b:
            return 1.0

        # Prefix/suffix match
        if a.startswith(b) or b.startswith(a):
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            if len(shorter) >= 3:
                return 0.8 + 0.2 * (len(shorter) / len(longer))

        # Substring containment
        if a in b or b in a:
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            if len(shorter) >= 3:
                return 0.7 + 0.3 * (len(shorter) / len(longer))

        # Fuzzy match
        return SequenceMatcher(None, a, b).ratio()

    def _value_similarity(self, v1: float, v2: float) -> float:
        """Calculate value similarity."""
        if v1 is None or v2 is None:
            return 0.0
        if v1 == 0 and v2 == 0:
            return 1.0
        if v1 == 0 or v2 == 0:
            return 0.0
        error = abs(v1 - v2) / abs(v1)
        return max(0, 1.0 - error)

    def generate_alias_map(self, mappings: List[NameMapping]) -> Dict[str, List[str]]:
        """Generate alias map from discovered mappings."""
        alias_map = defaultdict(list)

        for mapping in mappings:
            if mapping.confidence >= 0.7:
                # Normalize RDS name to get canonical form
                canonical = self._get_canonical(mapping.rds_name)
                if canonical != mapping.extracted_name:
                    alias_map[canonical].append(mapping.extracted_name)

        # Deduplicate
        return {k: list(dict.fromkeys(v)) for k, v in alias_map.items()}

    def _get_canonical(self, name: str) -> str:
        """Get canonical form of RDS name."""
        # Remove common prefixes
        name = re.sub(r'^(其中[：:]|减[：:]|加[：:])', '', name)
        # Remove numbering
        name = re.sub(r'^[一二三四五六七八九十]+[、.]', '', name)
        return name.strip()

    def print_report(self, mappings: List[NameMapping]):
        """Print a summary report."""
        print("\n" + "=" * 70)
        print("ITEM MAPPING REPORT")
        print("=" * 70)
        print(f"\nDiscovered {len(mappings)} mappings")

        for mapping in mappings[:20]:
            print(f"\n  [{mapping.confidence:.2f}] {mapping.extracted_name} -> {mapping.rds_name}")
            print(f"    Evidence: {', '.join(mapping.evidence[:3])}")

        alias_map = self.generate_alias_map(mappings)
        print(f"\nAlias map entries: {len(alias_map)}")

        return alias_map
