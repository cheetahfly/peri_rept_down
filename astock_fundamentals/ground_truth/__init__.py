# -*- coding: utf-8 -*-
"""
Ground truth comparison and mapping tools for A-share financial statements.
"""
from astock_fundamentals.ground_truth.comparator import (
    ItemComparison, ComparisonResult, compare_stock,
    normalize_name, load_extracted_json, find_extracted_json
)
from astock_fundamentals.ground_truth.gap_analyzer import GapAnalyzer, analyze_gaps, suggestions_to_json
from astock_fundamentals.ground_truth.mapper import ItemMapper, NameMapping
from astock_fundamentals.ground_truth.auto_learner import AutoLearner, ItemPattern, NameVariant
from astock_fundamentals.ground_truth.rule_applier import apply_suggestions, preview_changes

__all__ = [
    "ItemComparison", "ComparisonResult", "compare_stock",
    "normalize_name", "load_extracted_json", "find_extracted_json",
    "GapAnalyzer", "analyze_gaps", "suggestions_to_json",
    "ItemMapper", "NameMapping",
    "AutoLearner", "ItemPattern", "NameVariant",
    "apply_suggestions", "preview_changes",
]
