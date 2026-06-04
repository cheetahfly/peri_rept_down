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


@dataclass(frozen=True)
class YearTiers:
    early: float = 0.02  # 2000-2005
    mid: float = 0.01    # 2006-2019
    recent: float = 0.005  # 2020+

    def classify(self, year: int) -> str:
        if year <= 2005:
            return "early"
        if year <= 2019:
            return "mid"
        return "recent"

    def keys(self):
        return ("early", "mid", "recent")

    def __getitem__(self, key):
        return getattr(self, key)


_YEAR_TIERS = YearTiers()


def year_tier_tolerance() -> YearTiers:
    """Return the year-tier tolerance configuration."""
    return _YEAR_TIERS


def get_tolerance_for_year(year: int) -> float:
    """Return the value-matching tolerance for a given year."""
    tier = _YEAR_TIERS.classify(year)
    return getattr(_YEAR_TIERS, tier)

# 规则文件目录
RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "rules")

# 值映射规则缓存
_VALUE_MAP_CACHE = None


def load_value_mapping_rules() -> dict:
    """加载值映射规则（基于复杂金额全等匹配的数据源间科目名映射）"""
    global _VALUE_MAP_CACHE
    if _VALUE_MAP_CACHE is not None:
        return _VALUE_MAP_CACHE
    path = os.path.join(RULES_DIR, "value_mapping_rules.yaml")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            rules = yaml.safe_load(f)
            _VALUE_MAP_CACHE = rules or {}
    except (FileNotFoundError, yaml.YAMLError):
        _VALUE_MAP_CACHE = {}
    return _VALUE_MAP_CACHE


def _add_value_matched(self, gt_name, gt_val, ext_name, ext_val):
    """记录值匹配映射（用于自动学习）"""
    pass  # TODO: 记录到 auto_learned_mappings


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
    industry: str = None,  # 行业标识，用于行业特定规则
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

    # Strategy-driven matching chain: ordered list of (name, func)
    # Each func receives: (gt_name, gt_val, norm_gt, exact_ext, norm_ext, matched_keys)
    # Returns: (ext_name, ext_val, match_type) or None
    _STRATEGY = [
        ("exact_original", lambda n,v,ng,ee,ne,mk:
            (n,ee[n],"exact") if n in ee and _compare_values(v,ee[n]) is not None and _compare_values(v,ee[n])<10 else None),
        ("exact_norm", lambda n,v,ng,ee,ne,mk:
            (ne[ng][0],ne[ng][1],"exact") if ng in ne and _compare_values(v,ne[ng][1]) is not None and _compare_values(v,ne[ng][1])<10 else None),
        ("alias", lambda n,v,ng,ee,ne,mk:
            next(((va,ne[_mv(va)][1],"alias") for va in alias_map.get(ng,[]) if (_mv:=normalize_name)(va) in ne),None) if ng in alias_map else None),
        ("reverse_alias", lambda n,v,ng,ee,ne,mk:
            (ne[_ms(s)][0],ne[_ms(s)][1],"alias") if (s:=reverse_aliases.get(ng)) and (_ms:=normalize_name)(s) in ne else None),
        ("fuzzy", lambda n,v,ng,ee,ne,mk:
            (lambda b:(b[2],b[3],"fuzzy") if b[0]>=0.7 else None)(max([(0.6*_name_similarity(ng,nk)+0.4*(1-_compare_values(v,vl)/100),nk,ok,vl) for nk,(ok,vl) in ne.items() if ok not in mk and _name_similarity(ng,nk)>=0.8 and _compare_values(v,vl) is not None and _compare_values(v,vl)<10],default=[0]))),
        ("cid", lambda n,v,ng,ee,ne,mk:
            (lambda c:(c[0][0],c[0][1],"cid_value") if len(c)==1 else None)([(ok,vl) for nk,(ok,vl) in ne.items() if ok not in mk and _compare_values(v,vl) is not None and _compare_values(v,vl)<1.0])),
        ("keyword", lambda n,v,ng,ee,ne,mk:
            next(((ok,vl,"keyword") for kw in _extract_keywords(n) for nk,(ok,vl) in ne.items() if ok not in mk and any(k in nk for k in _extract_keywords(n)) and _compare_values(v,vl) is not None and _compare_values(v,vl)<5.0),
                 next(((ok,vl,"keyword") for kw in _extract_keywords(n) for nk,(ok,vl) in ne.items() if ok in mk and any(k in nk for k in _extract_keywords(n)) and _compare_values(v,vl) is not None and _compare_values(v,vl)<1.0),None)) if _extract_keywords(n) else None),
        ("redundant", lambda n,v,ng,ee,ne,mk:
            next(((ok,vl,"redundant") for nk,(ok,vl) in ne.items() if ok in mk and _compare_values(v,vl) is not None and _compare_values(v,vl)<1.0),None)),
        ("value_exact", lambda n,v,ng,ee,ne,mk:
            next(((ek,ev,"value_exact") for ek,ev in ext_data.items() if ek not in mk and _compare_values(v,ev) is not None and _compare_values(v,ev)<0.001),None)),
    ]

    matched_ext_keys = set()
    for gt_name, gt_val in gt_data.items():
        if gt_name in SKIP_ITEMS or "编码" in gt_name or "来源" in gt_name or "F0" in gt_name:
            continue
        ext_name = ext_val = None
        match_type = "missing"
        ng = normalize_name(gt_name)

        for sname, sfn in _STRATEGY:
            r = sfn(gt_name, gt_val, ng, exact_ext, norm_ext, matched_ext_keys)
            if r is not None:
                ext_name, ext_val, match_type = r
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

    # 添加行业特定匹配 (如果前8步未完全覆盖)
    if len(result.matched) < len(gt_data) * 0.8:  # 覆盖率低于80%时触发
        _apply_industry_rules(result, gt_data, ext_data, industry)

    return result


def _apply_industry_rules(result: ComparisonResult, gt_data: Dict[str, float],
                          ext_data: Dict[str, float], industry: str = None):
    """
    应用行业特定规则进行匹配。

    基于2026-05-30对比分析发现：
    - 金融行业（银行/保险/证券）有特有科目，需要专门匹配
    - 非金融行业科目相对标准，但也有特定差异
    """
    if not industry:
        return

    # 加载金融行业规则
    try:
        import yaml
        rules_path = os.path.join(os.path.dirname(__file__), "..", "..", "rules",
                                  "value_mapping_rules.yaml")
        with open(rules_path, "r", encoding="utf-8") as f:
            rules = yaml.safe_load(f)

        financial_rules = rules.get("financial_sector_rules", {}).get(industry, {})
        if not financial_rules:
            return

        # 获取已匹配的提取项
        matched_ext_keys = set(item.extracted_name for item in result.matched)

        # 对未匹配的RDS项尝试行业特定匹配
        for item in result.missing:
            gt_name = item.ground_truth_name
            for sina_name, rds_name in financial_rules.items():
                if rds_name in gt_name or gt_name in rds_name:
                    # 尝试在ext_data中找到对应的值
                    if sina_name in ext_data:
                        ext_val = ext_data[sina_name]
                        value_error = _compare_values(item.ground_truth_value, ext_val)
                        if value_error is not None and value_error < 0.005:
                            # 找到行业特定匹配
                            result.matched.append(ItemComparison(
                                ground_truth_name=gt_name,
                                ground_truth_value=item.ground_truth_value,
                                extracted_name=sina_name,
                                extracted_value=ext_val,
                                match_type="industry",
                                value_error_pct=value_error,
                            ))
                            matched_ext_keys.add(sina_name)
                            break
    except Exception:
        pass


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
