# Tidy Data Pipeline Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 Mapper 和 Comparator 支持行业 × 报告期类型匹配，输出详细差异报告，并自动建议新别名

**Architecture:** Phase 2 聚焦匹配增强：修改 ItemMapper 使用分层别名（get_aliases()），增强 Comparator 输出 item_code 级差异报告，添加 GapAnalyzer 根据缺失字段自动建议新别名

**Tech Stack:** Python 3.10+, pyreadr, JSON, YAML, pytest

---

## 文件结构

```
extraction/ground_truth/
├── mapper.py              # 修改：支持行业 × 报告期类型匹配
├── comparator.py          # 修改：增强差异报告输出
└── gap_analyzer.py        # 新增：差异分析和别名建议
```

---

## Task 1: 增强 ItemMapper 支持分层别名匹配

**Files:**
- Modify: `extraction/ground_truth/mapper.py`
- Test: `tests/test_mapper_hierarchical.py`

- [ ] **Step 1: 添加 industry 和 report_type 参数**

```python
# tests/test_mapper_hierarchical.py
def test_mapper_with_report_type():
    from extraction.ground_truth.mapper import ItemMapper
    
    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    EXTRACTED_DIR = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code"
    
    mapper = ItemMapper(RDS_DIR, EXTRACTED_DIR)
    
    # 测试指定 report_type
    mappings = mapper.discover_mappings(
        stock_codes=["600519"],
        years=[2020],
        statement_types=["income_statement"],
        report_type="annual",
    )
    
    assert len(mappings) > 0

def test_mapper_uses_hierarchical_aliases():
    from extraction.ground_truth.mapper import ItemMapper
    
    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    EXTRACTED_DIR = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code"
    
    mapper = ItemMapper(RDS_DIR, EXTRACTED_DIR)
    
    # 测试 industry 参数
    mappings = mapper.discover_mappings(
        stock_codes=["600519"],
        years=[2020],
        statement_types=["income_statement"],
        industry="白酒",
        report_type="annual",
    )
    
    assert len(mappings) > 0
```

- [ ] **Step 2: 修改 ItemMapper 类添加 industry 和 report_type 参数**

```python
# extraction/ground_truth/mapper.py
from extraction.config import get_aliases

class ItemMapper:
    def __init__(self, rds_dir: str, extracted_dir: str, decode_map_path: str = None):
        self.loader = RdsLoader(rds_dir, decode_map_path)
        self.extracted_dir = extracted_dir

    def discover_mappings(
        self,
        stock_codes: List[str],
        years: List[int],
        statement_types: List[str] = None,
        industry: str = None,
        report_type: str = "annual",
    ) -> List[NameMapping]:
        """
        Discover mappings between extracted and RDS names.

        Args:
            stock_codes: List of stock codes to analyze
            years: List of years to analyze
            statement_types: Statement types (default: all three)
            industry: Industry for alias matching (optional)
            report_type: Report type for alias matching (default: annual)

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

                    # Get hierarchical aliases for this statement type and report type
                    aliases = get_aliases(st, report_type)

                    # Find mappings
                    mappings = self._find_mappings(gt_data, ext_data, stock_code, year, st, aliases)
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
        aliases: Dict[str, List[str]] = None,
    ) -> List[tuple]:
        """Find mappings between GT and extracted data for one stock."""
        mappings = []

        # Build normalized extracted names
        norm_ext = {}
        for ext_name, ext_val in ext_data.items():
            norm = normalize_name(ext_name)
            if norm and norm not in ("", "行") and not re.match(r'^行\d+$', norm):
                norm_ext[norm] = (ext_name, ext_val)

        # Build reverse alias lookup: variant -> standard_name
        reverse_aliases = {}
        if aliases:
            for standard, variants in aliases.items():
                for v in variants:
                    norm_v = normalize_name(v)
                    if norm_v:
                        reverse_aliases[norm_v] = standard

        # Match each GT item to extracted items
        for gt_name, gt_val in gt_data.items():
            if gt_name in META_COLS or "编码" in gt_name or "来源" in gt_name:
                continue

            norm_gt = normalize_name(gt_name)

            # Find best matching extracted item
            best_match = None
            best_score = 0.0

            # First try exact match
            if norm_gt in norm_ext:
                orig_key, ext_val = norm_ext[norm_gt]
                val_sim = self._value_similarity(gt_val, ext_val)
                if val_sim > 0.9:
                    best_match = (orig_key, 1.0, val_sim)
                    best_score = 1.0

            # Then try alias match
            if not best_match and aliases:
                for variant in aliases.get(gt_name, []):
                    norm_v = normalize_name(variant)
                    if norm_v in norm_ext:
                        orig_key, ext_val = norm_ext[norm_v]
                        val_sim = self._value_similarity(gt_val, ext_val)
                        if val_sim > 0.9:
                            best_match = (orig_key, 0.9, val_sim)
                            best_score = 0.9
                            break

            # Finally try fuzzy match
            if not best_match:
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
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_mapper_hierarchical.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add extraction/ground_truth/mapper.py tests/test_mapper_hierarchical.py
git commit -m "feat: enhance ItemMapper to support industry × report_type matching"
```

---

## Task 2: 增强 Comparator 输出 item_code 级差异报告

**Files:**
- Modify: `extraction/ground_truth/comparator.py`
- Test: `tests/test_comparator_v2.py`

- [ ] **Step 1: 添加 item_code 字段到 ItemComparison**

```python
# tests/test_comparator_v2.py
def test_comparison_with_item_code():
    from extraction.ground_truth.comparator import compare_stock, ItemComparison
    
    # 模拟数据
    gt_data = {
        "营业收入": 1000000.0,
        "营业成本": 500000.0,
    }
    
    ext_data = {
        "营业收入": 1000000.0,
        "营业成本": 500000.0,
    }
    
    alias_map = {
        "营业收入": ["营业收入", "主营营业收入"],
        "营业成本": ["营业成本", "主营营业成本"],
    }
    
    result = compare_stock(
        gt_data=gt_data,
        ext_data=ext_data,
        alias_map=alias_map,
        stock_code="600519",
        year=2020,
        statement_type="income_statement",
    )
    
    assert result.coverage == 1.0
    assert len(result.items) == 2
    
    # 验证每个 item 有 item_code
    for item in result.items:
        assert hasattr(item, 'item_code') or hasattr(item, 'ground_truth_code')

def test_comparison_detailed_report():
    from extraction.ground_truth.comparator import compare_stock
    
    # 模拟数据 - 有缺失和不匹配
    gt_data = {
        "营业收入": 1000000.0,
        "营业成本": 500000.0,
        "财务费用": 100000.0,
    }
    
    ext_data = {
        "营业收入": 1000000.0,
        "营业成本": 500000.0,
        # 财务费用缺失
    }
    
    alias_map = {}
    
    result = compare_stock(
        gt_data=gt_data,
        ext_data=ext_data,
        alias_map=alias_map,
        stock_code="600519",
        year=2020,
        statement_type="income_statement",
    )
    
    # 验证详细报告
    report = result.detailed_report()
    assert "missing_items" in report
    assert len(report["missing_items"]) == 1
    assert report["missing_items"][0]["name"] == "财务费用"
```

- [ ] **Step 2: 修改 comparator.py 添加 item_code 字段和详细报告**

```python
# extraction/ground_truth/comparator.py

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

    # ... (existing properties)

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

def compare_stock(
    gt_data: Dict[str, float],
    ext_data: Dict[str, float],
    alias_map: Dict[str, List[str]],
    stock_code: str = "",
    year: int = 0,
    statement_type: str = "",
    decode_map: Dict[str, str] = None,  # NEW: field code to name mapping
) -> ComparisonResult:
    result = ComparisonResult(stock_code, year, statement_type)

    # Build reverse decode map: name -> code
    reverse_decode = {}
    if decode_map:
        for code, name in decode_map.items():
            reverse_decode[name] = code

    # Build reverse alias lookup: variant -> standard_name
    reverse_aliases = {}
    for standard, variants in alias_map.items():
        for v in variants:
            reverse_aliases[v] = standard

    # Build normalized extracted data
    norm_ext = {}
    for k, v in ext_data.items():
        nk = normalize_name(k)
        if nk and nk not in ("", "行") and not re.match(r'^行\d+$', nk):
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

        # Get item_code for gt_name
        gt_code = reverse_decode.get(gt_name)

        # Normalize gt_name for comparison
        norm_gt = normalize_name(gt_name)

        # 1. Exact match (normalized) with value validation
        if norm_gt in norm_ext:
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
            ground_truth_code=gt_code,
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
                extracted_item_code=orig_key,
            ))

    return result
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_comparator_v2.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add extraction/ground_truth/comparator.py tests/test_comparator_v2.py
git commit -m "feat: enhance Comparator with item_code tracking and detailed reports"
```

---

## Task 3: 创建 GapAnalyzer 分析差异并建议新别名

**Files:**
- Create: `extraction/ground_truth/gap_analyzer.py`
- Test: `tests/test_gap_analyzer.py`

- [ ] **Step 1: 创建 GapAnalyzer 类**

```python
# tests/test_gap_analyzer.py
def test_gap_analyzer_suggests_aliases():
    from extraction.ground_truth.gap_analyzer import GapAnalyzer
    
    # 模拟差异报告
    report = {
        "missing_items": [
            {"name": "利息收入", "code": "F033N", "expected_value": 3000000.0},
        ],
        "unmatched_items": [
            {"name": "利息收入(银行)", "code": None, "value": 3000000.0},
        ],
        "value_diffs": [],
    }
    
    analyzer = GapAnalyzer()
    suggestions = analyzer.analyze(report)
    
    assert len(suggestions) > 0
    assert suggestions[0]["type"] == "alias_suggestion"
    assert "利息收入(银行)" in suggestions[0]["variants"]

def test_gap_analyzer_groups_similar_names():
    from extraction.ground_truth.gap_analyzer import GapAnalyzer
    
    report = {
        "missing_items": [
            {"name": "营业收入", "code": "F006N", "expected_value": 1000000.0},
        ],
        "unmatched_items": [
            {"name": "主营业务收入", "code": None, "value": 1000000.0},
            {"name": "主营营业收入", "code": None, "value": 1000000.0},
        ],
        "value_diffs": [],
    }
    
    analyzer = GapAnalyzer()
    suggestions = analyzer.analyze(report)
    
    # 应该建议将 "主营业务收入" 和 "主营营业收入" 添加到 "营业收入" 的别名
    assert any("营业收入" in s["standard_name"] for s in suggestions)
```

- [ ] **Step 2: 创建 gap_analyzer.py**

```python
# extraction/ground_truth/gap_analyzer.py
"""
Gap analyzer: analyzes comparison results and suggests new aliases.

Identifies missing items and unmatched items to automatically
suggest additions to aliases.yaml.
"""

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, List, Optional


class GapAnalyzer:
    """Analyzes comparison gaps and suggests new aliases."""

    def __init__(self, min_similarity: float = 0.7):
        self.min_similarity = min_similarity

    def analyze(self, report: Dict) -> List[Dict]:
        """
        Analyze a comparison report and suggest aliases.

        Args:
            report: Dict with keys: missing_items, unmatched_items, value_diffs

        Returns:
            List of suggestions, each with type, standard_name, variants
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

            # Find similar unmatched items
            similar_variants = []
            for unmatched_name, unmatched_items in unmatched_groups.items():
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

        # Check for value mismatches (potential different units)
        value_diffs = report.get("value_diffs", [])
        for diff in value_diffs:
            # If value is off by exactly 10000x, suggest unit alias
            if diff["ground_truth_value"] and diff["extracted_value"]:
                ratio = diff["ground_truth_value"] / diff["extracted_value"]
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

    def _name_similarity(self, a: str, b: str) -> float:
        """Calculate name similarity."""
        if a == b:
            return 1.0
        if a in b or b in a:
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            return 0.7 + 0.3 * (len(shorter) / len(longer))
        return SequenceMatcher(None, a, b).ratio()

    def generate_yaml_updates(self, suggestions: List[Dict]) -> Dict[str, Dict[str, List[str]]]:
        """
        Generate YAML update structure from suggestions.

        Returns:
            Dict mapping statement_type -> standard_name -> list of variants
        """
        updates = defaultdict(lambda: defaultdict(list))

        for suggestion in suggestions:
            if suggestion["type"] == "alias_suggestion":
                standard = suggestion["standard_name"]
                variants = suggestion["variants"]
                # Default to income_statement, can be extended
                updates["income_statement"][standard].extend(variants)

        return dict(updates)

    def print_report(self, suggestions: List[Dict]):
        """Print a summary of suggestions."""
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
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/test_gap_analyzer.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add extraction/ground_truth/gap_analyzer.py tests/test_gap_analyzer.py
git commit -m "feat: add GapAnalyzer for automatic alias suggestion from comparison gaps"
```

---

## Task 4: 集成测试 - 端到端对比流程

**Files:**
- Test: `tests/test_phase2_integration.py`

- [ ] **Step 1: 编写端到端集成测试**

```python
# tests/test_phase2_integration.py
def test_end_to_end_comparison_with_item_codes():
    """测试完整的对比流程，包括 item_code 追踪"""
    from extraction.ground_truth.rds_loader import RdsLoader
    from extraction.ground_truth.comparator import compare_stock, load_extracted_json
    from extraction.config import get_aliases
    
    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    EXTRACTED_DIR = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code"
    
    loader = RdsLoader(RDS_DIR)
    
    # 加载 RDS Tidy Data
    gt_tidy = loader.load_stock_data_tidy("600519", 2020, "income_statement")
    assert len(gt_tidy) > 0
    
    # 转换为旧格式用于 comparator
    gt_data = {item["item_name"]: item["value"] for item in gt_tidy}
    
    # 加载 extracted data
    ext_data = {}
    extracted_path = f"{EXTRACTED_DIR}/600519/600519_2020_income_statement.json"
    if os.path.exists(extracted_path):
        ext_data = load_extracted_json(extracted_path)
    
    # 获取 aliases
    aliases = get_aliases("income_statement", "annual")
    
    # 获取 decode_map for item_code tracking
    decode_map = loader._decode_maps.get("income_statement", {})
    
    # 执行对比
    result = compare_stock(
        gt_data=gt_data,
        ext_data=ext_data,
        alias_map=aliases,
        stock_code="600519",
        year=2020,
        statement_type="income_statement",
        decode_map=decode_map,
    )
    
    # 验证结果
    assert result.stock_code == "600519"
    assert result.year == 2020
    assert result.statement_type == "income_statement"
    
    # 验证 detailed report
    report = result.detailed_report()
    assert "missing_items" in report
    assert "unmatched_items" in report
    assert "value_diffs" in report

def test_gap_analyzer_with_real_data():
    """使用真实数据测试 GapAnalyzer"""
    from extraction.ground_truth.gap_analyzer import GapAnalyzer
    from extraction.ground_truth.rds_loader import RdsLoader
    from extraction.ground_truth.comparator import compare_stock, load_extracted_json
    from extraction.config import get_aliases
    
    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    EXTRACTED_DIR = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code"
    
    loader = RdsLoader(RDS_DIR)
    
    # 加载数据
    gt_tidy = loader.load_stock_data_tidy("600519", 2020, "income_statement")
    gt_data = {item["item_name"]: item["value"] for item in gt_tidy}
    
    ext_data = {}
    extracted_path = f"{EXTRACTED_DIR}/600519/600519_2020_income_statement.json"
    if os.path.exists(extracted_path):
        ext_data = load_extracted_json(extracted_path)
    
    aliases = get_aliases("income_statement", "annual")
    decode_map = loader._decode_maps.get("income_statement", {})
    
    result = compare_stock(
        gt_data=gt_data,
        ext_data=ext_data,
        alias_map=aliases,
        stock_code="600519",
        year=2020,
        statement_type="income_statement",
        decode_map=decode_map,
    )
    
    # 使用 GapAnalyzer 分析
    analyzer = GapAnalyzer()
    report = result.detailed_report()
    suggestions = analyzer.analyze(report)
    
    # 验证 suggestions 结构
    for s in suggestions:
        assert "type" in s
        assert "standard_name" in s

def test_mapper_discovers_mappings_with_hierarchical_aliases():
    """测试 Mapper 使用分层别名发现映射"""
    from extraction.ground_truth.mapper import ItemMapper
    
    RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
    EXTRACTED_DIR = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code"
    
    mapper = ItemMapper(RDS_DIR, EXTRACTED_DIR)
    
    # 发现映射
    mappings = mapper.discover_mappings(
        stock_codes=["600519"],
        years=[2020],
        statement_types=["income_statement"],
        report_type="annual",
    )
    
    # 验证映射
    assert len(mappings) > 0
    
    for mapping in mappings:
        assert mapping.confidence >= 0.7
        assert len(mapping.evidence) >= 1
```

- [ ] **Step 2: 运行集成测试**

Run: `pytest tests/test_phase2_integration.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_phase2_integration.py
git commit -m "test: add Phase 2 integration tests for end-to-end comparison flow"
```

---

## Task 5: 创建批量对比脚本

**Files:**
- Create: `scripts/batch_compare.py`

- [ ] **Step 1: 创建批量对比脚本**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch comparison script.

Compares extracted data against RDS ground truth for multiple stocks/years.
Outputs detailed reports and alias suggestions.
"""

import os
import sys
import json
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.ground_truth.rds_loader import RdsLoader
from extraction.ground_truth.comparator import compare_stock, load_extracted_json
from extraction.ground_truth.gap_analyzer import GapAnalyzer
from extraction.config import get_aliases


def batch_compare(
    stock_codes: list,
    years: list,
    statement_types: list = None,
    rds_dir: str = "D:/Research/Quant/SETL/cninfo/data_backup",
    extracted_dir: str = "F:/ai_fin_proj/peri_rept_down/data/extracted/by_code",
    report_type: str = "annual",
    output_dir: str = None,
):
    """
    Run batch comparison for multiple stocks/years.
    
    Returns:
        Dict with summary statistics and alias suggestions
    """
    if statement_types is None:
        statement_types = ["income_statement", "balance_sheet", "cash_flow"]

    loader = RdsLoader(rds_dir)
    analyzer = GapAnalyzer()

    all_suggestions = []
    all_reports = []
    
    summary = {
        "total_compared": 0,
        "total_coverage": 0.0,
        "total_value_accuracy": 0.0,
        "by_statement_type": defaultdict(lambda: {"count": 0, "coverage": 0.0, "accuracy": 0.0}),
    }

    for stock_code in stock_codes:
        for year in years:
            for st in statement_types:
                # Load RDS Tidy Data
                gt_tidy = loader.load_stock_data_tidy(stock_code, year, st)
                if not gt_tidy:
                    continue

                gt_data = {item["item_name"]: item["value"] for item in gt_tidy}

                # Load extracted data
                ext_data = {}
                extracted_path = os.path.join(extracted_dir, stock_code, f"{stock_code}_{year}_{st}.json")
                if os.path.exists(extracted_path):
                    ext_data = load_extracted_json(extracted_path)

                if not ext_data:
                    continue

                # Get aliases and decode map
                aliases = get_aliases(st, report_type)
                decode_map = loader._decode_maps.get(st, {})

                # Compare
                result = compare_stock(
                    gt_data=gt_data,
                    ext_data=ext_data,
                    alias_map=aliases,
                    stock_code=stock_code,
                    year=year,
                    statement_type=st,
                    decode_map=decode_map,
                )

                # Store report
                report = result.detailed_report()
                all_reports.append(report)

                # Analyze gaps
                suggestions = analyzer.analyze(report)
                all_suggestions.extend(suggestions)

                # Update summary
                summary["total_compared"] += 1
                summary["total_coverage"] += result.coverage
                summary["total_value_accuracy"] += result.value_accuracy
                summary["by_statement_type"][st]["count"] += 1
                summary["by_statement_type"][st]["coverage"] += result.coverage
                summary["by_statement_type"][st]["accuracy"] += result.value_accuracy

    # Calculate averages
    if summary["total_compared"] > 0:
        summary["total_coverage"] /= summary["total_compared"]
        summary["total_value_accuracy"] /= summary["total_compared"]
        for st in summary["by_statement_type"]:
            count = summary["by_statement_type"][st]["count"]
            if count > 0:
                summary["by_statement_type"][st]["coverage"] /= count
                summary["by_statement_type"][st]["accuracy"] /= count

    # Generate YAML updates
    yaml_updates = analyzer.generate_yaml_updates(all_suggestions)

    # Save results if output_dir specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        
        with open(os.path.join(output_dir, "suggestions.json"), "w", encoding="utf-8") as f:
            json.dump(all_suggestions, f, indent=2, ensure_ascii=False)
        
        with open(os.path.join(output_dir, "yaml_updates.json"), "w", encoding="utf-8") as f:
            json.dump(yaml_updates, f, indent=2, ensure_ascii=False)

    return {
        "summary": summary,
        "suggestions": all_suggestions,
        "yaml_updates": yaml_updates,
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch compare extracted data against RDS")
    parser.add_argument("--stocks", nargs="+", default=["600519"], help="Stock codes")
    parser.add_argument("--years", nargs="+", type=int, default=[2020], help="Years")
    parser.add_argument("--types", nargs="+", default=["income_statement"], help="Statement types")
    parser.add_argument("--output", default="data/phase2_reports", help="Output directory")
    
    args = parser.parse_args()
    
    result = batch_compare(
        stock_codes=args.stocks,
        years=args.years,
        statement_types=args.types,
        output_dir=args.output,
    )
    
    print(f"\nComparison complete!")
    print(f"Total compared: {result['summary']['total_compared']}")
    print(f"Average coverage: {result['summary']['total_coverage']:.2%}")
    print(f"Alias suggestions: {len(result['suggestions'])}")
    print(f"\nResults saved to: {args.output}")
```

- [ ] **Step 2: 运行脚本测试**

Run: `python scripts/batch_compare.py --stocks 600519 --years 2020 --types income_statement`
Expected: Script completes, outputs summary

- [ ] **Step 3: 提交**

```bash
git add scripts/batch_compare.py
git commit -m "feat: add batch comparison script for multi-stock analysis"
```

---

## Phase 2 完成后检查清单

- [ ] `mapper.py` 已修改，支持 `industry` 和 `report_type` 参数
- [ ] `comparator.py` 已增强，包含 `item_code` 字段和 `detailed_report()` 方法
- [ ] `gap_analyzer.py` 已创建，支持自动别名建议
- [ ] 所有测试通过
- [ ] 端到端集成测试通过
- [ ] 批量对比脚本可运行
