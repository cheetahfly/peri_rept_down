# -*- coding: utf-8 -*-
"""
Ground truth comparison engine.

Compares extracted PDF data against RDS ground truth at the item level.
"""

import json
import os
import re
import yaml
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

# 规则文件目录
RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "rules")


def load_yaml_rule(filename: str, default=None):
    """从 rules/ 目录加载 YAML 规则文件"""
    path = os.path.join(RULES_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return default


@dataclass
class ItemComparison:
    ground_truth_name: str
    ground_truth_value: Optional[float]
    extracted_name: Optional[str]
    extracted_value: Optional[float]
    match_type: str  # exact, alias, fuzzy, missing, unmatched
    value_error_pct: Optional[float] = None
    ground_truth_code: Optional[str] = None  # item_code like F033N
    extracted_item_code: Optional[str] = None  # extracted item code if available


@dataclass
class ComparisonResult:
    stock_code: str
    year: int
    statement_type: str
    items: List[ItemComparison] = field(default_factory=list)

    @property
    def matched(self) -> List[ItemComparison]:
        return [i for i in self.items if i.match_type in ("exact", "alias", "fuzzy", "cid_value")]

    @property
    def missing(self) -> List[ItemComparison]:
        return [i for i in self.items if i.match_type == "missing"]

    @property
    def unmatched(self) -> List[ItemComparison]:
        return [i for i in self.items if i.match_type == "unmatched"]

    @property
    def coverage(self) -> float:
        gt_count = len(self.matched) + len(self.missing)
        return len(self.matched) / gt_count if gt_count > 0 else 0.0

    @property
    def value_accuracy(self) -> float:
        matched = [i for i in self.matched if i.value_error_pct is not None]
        if not matched:
            return 0.0
        accurate = sum(1 for i in matched if i.value_error_pct < 1.0)
        return accurate / len(matched)

    def summary(self) -> Dict:
        return {
            "stock_code": self.stock_code,
            "year": self.year,
            "statement_type": self.statement_type,
            "gt_items": len(self.matched) + len(self.missing),
            "matched": len(self.matched),
            "missing": len(self.missing),
            "unmatched": len(self.unmatched),
            "coverage": round(self.coverage, 3),
            "value_accuracy": round(self.value_accuracy, 3),
        }

    def detailed_report(self) -> Dict:
        """Generate detailed difference report with item codes."""
        missing_items = []
        for item in self.missing:
            missing_items.append({
                "name": item.ground_truth_name,
                "code": item.ground_truth_code,
                "expected_value": item.ground_truth_value,
            })

        unmatched_items = []
        for item in self.unmatched:
            unmatched_items.append({
                "name": item.extracted_name,
                "code": item.extracted_item_code,
                "value": item.extracted_value,
            })

        value_diffs = []
        for item in self.matched:
            if item.value_error_pct is not None and item.value_error_pct > 1.0:
                value_diffs.append({
                    "name": item.ground_truth_name,
                    "code": item.ground_truth_code,
                    "ground_truth_value": item.ground_truth_value,
                    "extracted_value": item.extracted_value,
                    "error_pct": item.value_error_pct,
                })

        return {
            "stock_code": self.stock_code,
            "year": self.year,
            "statement_type": self.statement_type,
            "coverage": self.coverage,
            "value_accuracy": self.value_accuracy,
            "missing_items": missing_items,
            "unmatched_items": unmatched_items,
            "value_diffs": value_diffs,
        }


def normalize_name(name: str) -> str:
    """Normalize an item name for comparison."""
    # Remove column suffixes: _c1, _c2, etc.
    name = re.sub(r'_c\d+$', '', name)
    # Remove prefixes: 其中：, 减：, 加：, 其中：对联营...
    name = re.sub(r'^(其中[：:]|减[：:]|加[：:])', '', name)
    # Remove numbering: 一、, 二、, 三、, (一), (二), 1., 2.
    name = re.sub(r'^[一二三四五六七八九十]+[、.]', '', name)
    name = re.sub(r'^[（(][一二三四五六七八九十1234567890]+[)）]', '', name)
    name = re.sub(r'^\d+[、.]', '', name)
    # Remove trailing parenthetical notes (with or without closing parenthesis)
    name = re.sub(r'[（(][^)）]*$', '', name)
    # Strip whitespace
    name = name.strip()
    return name


# Items to skip (from YAML, with fallback to defaults)
SKIP_ITEMS_LIST = load_yaml_rule("skip_items.yaml", [
    "合并类型编码", "报表来源编码", "合并类型", "报表来源",
    "盈余公积", "未分配利润", "资本公积", "所有者权益（或股东权",
    "负债和所有者权益", "股本", "库存股",
    "（一）基本每股收益", "（二）稀释每股收益",
])
SKIP_ITEMS = set(SKIP_ITEMS_LIST if isinstance(SKIP_ITEMS_LIST, list) else [])


def _name_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if a in b or b in a:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        return 0.7 + 0.3 * (len(shorter) / len(longer))
    return SequenceMatcher(None, a, b).ratio()


def _extract_keywords(name: str) -> List[str]:
    """从科目名提取关键词用于关键词匹配。

    去除通用前缀（其中：、减：、加：、编号等）后，返回有意义的
    多字关键词。适用于RDS科目名与提取名不完全一致但含相同核心词的情况。
    如RDS"其中：归属于母公司"→关键词["归属于母公司"]→匹配提取的
    "1.归属于母公司股东的净利润"。
    """
    normalized = normalize_name(name)
    if not normalized or len(normalized) < 2:
        return []
    # 主要关键词：标准化后的完整名称（已去除前缀编号）
    keywords = [normalized]
    # 对于4字以上的名称，也生成2字滑动窗口子关键词
    # 如"归属于少数股东"→"归属""属于""于少""少数""数股""股东"
    if len(normalized) >= 4:
        for i in range(len(normalized) - 1):
            bigram = normalized[i:i+2]
            if len(bigram) >= 2 and bigram not in keywords:
                keywords.append(bigram)
    return keywords


def _compare_values(gt_val, ext_val, tolerance=0.01):
    if gt_val is None or ext_val is None:
        return None
    if gt_val == 0 and ext_val == 0:
        return 0.0
    if gt_val == 0:
        return float("inf") if abs(ext_val) > 1000 else 0.0
    return abs(ext_val - gt_val) / abs(gt_val) * 100


def compare_stock(
    gt_data: Dict[str, float],
    ext_data: Dict[str, float],
    alias_map: Dict[str, List[str]],
    stock_code: str = "",
    year: int = 0,
    statement_type: str = "",
    decode_map: Dict[str, str] = None,
) -> ComparisonResult:
    result = ComparisonResult(stock_code, year, statement_type)

    # Build reverse decode map: name -> code
    reverse_decode = {}
    if decode_map:
        reverse_decode = {name: code for code, name in decode_map.items()}

    # Build reverse alias lookup: variant -> standard_name
    reverse_aliases = {}
    for standard, variants in alias_map.items():
        for v in variants:
            reverse_aliases[v] = standard

    # Build normalized extracted data (first occurrence wins)
    norm_ext = {}
    exact_ext = {}  # original-name index for exact matching
    for k, v in ext_data.items():
        exact_ext[k] = v
        nk = normalize_name(k)
        if nk and nk not in ("", "行") and not re.match(r'^行\d+$', nk):
            if nk not in norm_ext:  # Keep first occurrence to avoid overwrite
                norm_ext[nk] = (k, v)

    # Match ground truth items to extracted items
    matched_ext_keys = set()
    for gt_name, gt_val in gt_data.items():
        # Skip non-financial metadata
        if gt_name in SKIP_ITEMS or "编码" in gt_name or "来源" in gt_name or "F0" in gt_name:
            continue

        ext_name = None
        ext_val = None
        match_type = "missing"

        # Normalize gt_name for comparison
        norm_gt = normalize_name(gt_name)

        # 1. Exact match (original name or normalized) with value validation
        if gt_name in exact_ext:
            orig_key = gt_name
            ext_val = exact_ext[gt_name]
            match_check = _compare_values(gt_val, ext_val)
            if match_check is not None and match_check < 10:
                ext_name = orig_key
                match_type = "exact"
            else:
                ext_val = None
        if match_type == "missing" and norm_gt in norm_ext:
            orig_key, ext_val = norm_ext[norm_gt]
            # Validate that values are similar
            value_error = _compare_values(gt_val, ext_val)
            if value_error is not None and value_error < 10:  # <10% error
                ext_name = orig_key
                match_type = "exact"
            else:
                # Values don't match, skip this exact match
                ext_val = None
        else:
            # 2. Check if norm_gt is a standard name with aliases in ext
            if norm_gt in alias_map:
                for variant in alias_map[norm_gt]:
                    norm_v = normalize_name(variant)
                    if norm_v in norm_ext:
                        orig_key, ext_val = norm_ext[norm_v]
                        ext_name = orig_key
                        match_type = "alias"
                        break

            # 3. Check reverse aliases (variant -> standard)
            if match_type == "missing":
                standard = reverse_aliases.get(norm_gt)
                if standard:
                    norm_std = normalize_name(standard)
                    if norm_std in norm_ext:
                        orig_key, ext_val = norm_ext[norm_std]
                        ext_name = orig_key
                        match_type = "alias"

            if match_type == "missing":
                # 4. Fuzzy match with value validation
                best_score = 0.0
                best_key = None
                best_orig = None
                best_val = None
                for norm_k, (orig_k, v) in norm_ext.items():
                    if orig_k in matched_ext_keys:
                        continue
                    name_score = _name_similarity(norm_gt, norm_k)
                    # Require high name similarity AND value similarity
                    if name_score >= 0.8:
                        val_score = _compare_values(gt_val, v)
                        if val_score is not None and val_score < 10:  # <10% error
                            combined = 0.6 * name_score + 0.4 * (1 - val_score/100)
                            if combined > best_score:
                                best_score = combined
                                best_key = norm_k
                                best_orig = orig_k
                                best_val = v
                if best_score >= 0.7:
                    ext_name = best_orig
                    ext_val = best_val
                    match_type = "fuzzy"

            if match_type == "missing":
                # 5. CID字体回退：纯数值匹配
                # CID字体PDF中科目名称乱码，但数值正确。当名称匹配全部失败时，
                # 尝试仅通过数值找到匹配项（要求值误差<1%且未匹配的提取项唯一）
                best_v = None
                best_k = None
                candidates = []
                for norm_k, (orig_k, v) in norm_ext.items():
                    if orig_k in matched_ext_keys:
                        continue
                    val_error = _compare_values(gt_val, v)
                    if val_error is not None and val_error < 1.0:  # <1% error
                        candidates.append((norm_k, orig_k, v))
                if len(candidates) == 1:
                    ext_name = candidates[0][1]
                    ext_val = candidates[0][2]
                    match_type = "cid_value"

            if match_type == "missing":
                # 6. 关键词匹配（替代穷举变体法）
                # 从RDS科目名提取核心关键词，在提取结果中搜索包含该关键词的项。
                # 适用于RDS"归属于母公司"→提取"1.归属于母公司股东的净利润"
                gt_keywords = _extract_keywords(gt_name)
                if gt_keywords:
                    # 6a. 优先匹配未消费的提取项
                    for norm_k, (orig_k, v) in norm_ext.items():
                        if orig_k in matched_ext_keys:
                            continue
                        if any(kw in norm_k for kw in gt_keywords):
                            val_error = _compare_values(gt_val, v)
                            if val_error is not None and val_error < 5.0:
                                ext_name = orig_k
                                ext_val = v
                                match_type = "keyword"
                                break

                if match_type == "missing" and gt_keywords:
                    # 6b. 若未消费项无匹配，尝试已消费项（值高度一致即为冗余科目）
                    # RDS有时包含多个科目指向同一财务指标，如：
                    #   F028N"归属于母公司所有者的净利润" 和 F040N"其中：归属于母公司"
                    # 两者值相同，后者应共享前者的提取项。
                    for norm_k, (orig_k, v) in norm_ext.items():
                        if orig_k not in matched_ext_keys:
                            continue
                        if any(kw in norm_k for kw in gt_keywords):
                            val_error = _compare_values(gt_val, v)
                            if val_error is not None and val_error < 1.0:
                                ext_name = orig_k
                                ext_val = v
                                match_type = "keyword"
                                break

            if match_type == "missing":
                # 7. 纯冗余科目匹配：值完全相同但名称无关键词交集
                # 如RDS"其中：归属于少数股东"与提取"2.少数股东损益"值相同
                # 但关键词"归属于少数股东"不在"少数股东损益"中。
                for norm_k, (orig_k, v) in norm_ext.items():
                    if orig_k not in matched_ext_keys:
                        continue
                    val_error = _compare_values(gt_val, v)
                    if val_error is not None and val_error < 1.0:
                        ext_name = orig_k
                        ext_val = v
                        match_type = "redundant"
                        break

        if ext_name:
            matched_ext_keys.add(ext_name)

        value_error = _compare_values(gt_val, ext_val) if ext_val is not None else None

        result.items.append(ItemComparison(
            ground_truth_name=gt_name,
            ground_truth_value=gt_val,
            extracted_name=ext_name,
            extracted_value=ext_val,
            match_type=match_type,
            value_error_pct=value_error,
            ground_truth_code=reverse_decode.get(gt_name),
        ))

    # Unmatched extracted items
    for orig_key, (norm_k, ext_val) in norm_ext.items():
        if orig_key not in matched_ext_keys:
            result.items.append(ItemComparison(
                ground_truth_name="",
                ground_truth_value=None,
                extracted_name=orig_key,
                extracted_value=ext_val,
                match_type="unmatched",
            ))

    return result


def load_extracted_json(json_path: str) -> Dict[str, float]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    inner = data.get("data", data)
    if isinstance(inner, dict) and "data" in inner:
        return inner["data"]
    if isinstance(inner, dict):
        return inner
    return {}


def find_extracted_json(extracted_dir: str, stock_code: str, year: int, statement_type: str) -> Optional[str]:
    fname = f"{stock_code}_{year}_{statement_type}.json"
    path = os.path.join(extracted_dir, stock_code, fname)
    return path if os.path.exists(path) else None
