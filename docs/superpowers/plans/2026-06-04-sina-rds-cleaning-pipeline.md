# Sina→RDS Cleaning Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 5-step pipeline (slice → match → report → learn → clean) that takes Sina 2019-2022 annual reports, matches them against RDS ground truth, learns externalized mapping rules, and outputs Tidy Data aligned to RDS display_order.

**Architecture:** Reuse existing `RdsLoader`, `comparator.compare_stock`, and the YAML rule set. Add two new modules — `rule_cleaner.py` (rule application) and `clean_sina_pipeline.py` (orchestrator) — plus a small test suite. Each round of rule additions is measured by re-running the comparison and diffing match rates.

**Tech Stack:** Python 3.13, pandas, pyreadr, pyyaml, pytest, existing `astock_fundamentals` package.

**Spec:** `docs/superpowers/specs/2026-06-04-sina-rds-cleaning-pipeline-design.md`

---

## File Structure

### New files
- `astock_fundamentals/ground_truth/rule_cleaner.py` — applies YAML rules to Sina rows (rename / unit / aggregate)
- `astock_fundamentals/ground_truth/sina_loader.py` — loads + slices Sina 2019-2022 annual rows from `data/akshare_bulk/`
- `scripts/clean_sina_pipeline.py` — orchestrates 5 steps, writes reports
- `tests/ground_truth/test_sina_loader.py` — slice correctness tests
- `tests/ground_truth/test_rule_cleaner.py` — rename / unit / aggregate tests
- `tests/scripts/test_clean_pipeline.py` — end-to-end on 2 known stocks (000001, 600000)
- `data/ground_truth_reports/baseline_2019_2022.json` — output of Task 4
- `data/ground_truth_reports/cleaning_progression.md` — final summary

### Modified files
- `astock_fundamentals/ground_truth/comparator.py` — add `year_tier_tolerance(year)` helper
- `rules/aliases.yaml` — append 2019-2022 alias entries (Task 7)
- `rules/value_mapping_rules.yaml` — append `sina_to_rds` block (Task 8)
- `data/exports_v2/sina_cleaned_balance_sheet.csv` — generated artifact
- `data/exports_v2/sina_cleaned_income_statement.csv` — generated artifact
- `data/exports_v2/sina_cleaned_cash_flow.csv` — generated artifact

---

## Task 1: Add year-tier tolerance helper to comparator

**Files:**
- Modify: `astock_fundamentals/ground_truth/comparator.py:1-50` (imports + helper)

- [ ] **Step 1: Write failing test**

Create `tests/ground_truth/test_comparator_year_tier.py`:

```python
import pytest
from astock_fundamentals.ground_truth.comparator import year_tier_tolerance


def test_year_tier_returns_dict_with_three_keys():
    tiers = year_tier_tolerance()
    assert set(tiers.keys()) == {"early", "mid", "recent"}


def test_year_tier_values_increase_toward_recent():
    tiers = year_tier_tolerance()
    assert tiers["early"] > tiers["mid"] >= tiers["recent"]


def test_year_tier_classify_2019_is_mid():
    assert year_tier_tolerance().classify(2019) == "mid"


def test_year_tier_classify_2022_is_recent():
    assert year_tier_tolerance().classify(2022) == "recent"


def test_year_tier_classify_2003_is_early():
    assert year_tier_tolerance().classify(2003) == "early"


def test_get_tolerance_for_year_returns_float():
    from astock_fundamentals.ground_truth.comparator import get_tolerance_for_year
    assert isinstance(get_tolerance_for_year(2019), float)
    assert 0 < get_tolerance_for_year(2019) < 1
```

- [ ] **Step 2: Run test, expect failure**

Run: `pytest tests/ground_truth/test_comparator_year_tier.py -v`
Expected: ImportError or AttributeError (`year_tier_tolerance` not defined).

- [ ] **Step 3: Add helper to comparator.py**

Append to `astock_fundamentals/ground_truth/comparator.py` after the imports:

```python
@dataclass(frozen=True)
class YearTiers:
    early: float = 0.02  # 2000-2005
    mid: float = 0.01    # 2006-2015
    recent: float = 0.005  # 2016+

    def classify(self, year: int) -> str:
        if year <= 2005:
            return "early"
        if year <= 2015:
            return "mid"
        return "recent"


_YEAR_TIERS = YearTiers()


def year_tier_tolerance() -> YearTiers:
    """Return the year-tier tolerance configuration."""
    return _YEAR_TIERS


def get_tolerance_for_year(year: int) -> float:
    """Return the value-matching tolerance for a given year."""
    tier = _YEAR_TIERS.classify(year)
    return getattr(_YEAR_TIERS, tier)
```

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/ground_truth/test_comparator_year_tier.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/ground_truth/comparator.py tests/ground_truth/test_comparator_year_tier.py
git commit -m "feat(comparator): add year-tier tolerance helper"
```

---

## Task 2: Build Sina loader with year slicing

**Files:**
- Create: `astock_fundamentals/ground_truth/sina_loader.py`
- Test: `tests/ground_truth/test_sina_loader.py`

- [ ] **Step 1: Write failing test**

Create `tests/ground_truth/test_sina_loader.py`:

```python
import os
import pandas as pd
import pytest

from astock_fundamentals.ground_truth.sina_loader import (
    SinaLoader, list_annual_years, slice_annual,
)


SAMPLE_DIR = "data/akshare_bulk"


def test_list_annual_years_returns_sorted_dates():
    df = pd.read_csv(os.path.join(SAMPLE_DIR, "000001_balance_sheet.csv"), encoding="utf-8-sig")
    years = list_annual_years(df)
    assert all(y.endswith("1231") for y in years)
    assert years == sorted(years)


def test_slice_annual_filters_target_years():
    df = pd.read_csv(os.path.join(SAMPLE_DIR, "000001_balance_sheet.csv"), encoding="utf-8-sig")
    out = slice_annual(df, [2019, 2020, 2021, 2022])
    assert len(out) >= 4
    periods = set(out["报告日"].astype(str))
    assert {"20191231", "20201231", "20211231", "20221231"} & periods


def test_slice_annual_excludes_quarterly():
    df = pd.read_csv(os.path.join(SAMPLE_DIR, "000001_balance_sheet.csv"), encoding="utf-8-sig")
    out = slice_annual(df, [2019, 2020, 2021, 2022])
    assert all(p.endswith("1231") for p in out["报告日"].astype(str))


def test_sina_loader_reads_balance_sheet():
    loader = SinaLoader(SAMPLE_DIR)
    df = loader.read_statement("000001", "balance_sheet")
    assert "报告日" in df.columns
    assert len(df) > 0


def test_sina_loader_get_2019_2022_annual():
    loader = SinaLoader(SAMPLE_DIR)
    out = loader.get_annual("000001", [2019, 2020, 2021, 2022], "balance_sheet")
    periods = set(out["报告日"].astype(str))
    assert {"20191231", "20201231", "20211231", "20221231"} & periods
```

- [ ] **Step 2: Run test, expect failure**

Run: `pytest tests/ground_truth/test_sina_loader.py -v`
Expected: ImportError (`sina_loader` not found).

- [ ] **Step 3: Implement sina_loader.py**

Create `astock_fundamentals/ground_truth/sina_loader.py`:

```python
# -*- coding: utf-8 -*-
"""
Sina loader: reads Sina (AKShare) financial data and slices annual reports.
"""

import os
from typing import Dict, List

import pandas as pd


STATEMENT_FILES = {
    "balance_sheet": "balance_sheet.csv",
    "income_statement": "income_statement.csv",
    "cash_flow": "cash_flow.csv",
}


def list_annual_years(df: pd.DataFrame) -> List[str]:
    """Return sorted unique 'YYYY1231' report dates present in df."""
    dates = df["报告日"].astype(str).unique()
    annual = [d for d in dates if d.endswith("1231")]
    return sorted(annual)


def slice_annual(df: pd.DataFrame, target_years: List[int]) -> pd.DataFrame:
    """Return rows whose report date is December 31 of any target year."""
    target_dates = {f"{y}1231" for y in target_years}
    mask = df["报告日"].astype(str).isin(target_dates)
    return df[mask].copy()


class SinaLoader:
    """Loads Sina (AKShare) bulk CSVs from data/akshare_bulk/."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def read_statement(self, stock_code: str, statement_type: str) -> pd.DataFrame:
        filename = STATEMENT_FILES[statement_type]
        path = os.path.join(self.base_dir, f"{stock_code}_{filename}")
        return pd.read_csv(path, encoding="utf-8-sig")

    def get_annual(
        self, stock_code: str, target_years: List[int], statement_type: str,
    ) -> pd.DataFrame:
        df = self.read_statement(stock_code, statement_type)
        return slice_annual(df, target_years)
```

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/ground_truth/test_sina_loader.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/ground_truth/sina_loader.py tests/ground_truth/test_sina_loader.py
git commit -m "feat(sina_loader): annual slice helper and stock reader"
```

---

## Task 3: Build rule_cleaner core (column rename + value conversion)

**Files:**
- Create: `astock_fundamentals/ground_truth/rule_cleaner.py`
- Test: `tests/ground_truth/test_rule_cleaner.py`

- [ ] **Step 1: Write failing test**

Create `tests/ground_truth/test_rule_cleaner.py`:

```python
import pandas as pd
import pytest

from astock_fundamentals.ground_truth.rule_cleaner import (
    load_cleaning_rules, rename_columns, convert_values,
    CleaningRules,
)


SAMPLE_ALIASES = """
balance_sheet:
  货币资金:
    - 现金及存放中央银行款项
    - 现金
  资产总计:
    - 资产总计
    - 总资产
"""


def test_load_cleaning_rules_parses_aliases():
    rules = load_cleaning_rules(extra_aliases_text=SAMPLE_ALIASES)
    assert "货币资金" in rules.aliases.get("balance_sheet", {})
    assert "现金及存放中央银行款项" in rules.aliases["balance_sheet"]["货币资金"]


def test_rename_columns_replaces_sina_name():
    rules = load_cleaning_rules(extra_aliases_text=SAMPLE_ALIASES)
    df = pd.DataFrame({"现金及存放中央银行款项": [1.0], "其他科目": [2.0]})
    out = rename_columns(df, "balance_sheet", rules)
    assert "货币资金" in out.columns
    assert "现金及存放中央银行款项" not in out.columns


def test_rename_columns_preserves_unknown_columns():
    rules = load_cleaning_rules(extra_aliases_text=SAMPLE_ALIASES)
    df = pd.DataFrame({"现金及存放中央银行款项": [1.0], "未识别列": [2.0]})
    out = rename_columns(df, "balance_sheet", rules)
    assert "未识别列" in out.columns


def test_convert_values_passes_through_yuan():
    rules = load_cleaning_rules()
    df = pd.DataFrame({"A": [1234567890.0]})
    out = convert_values(df, rules)
    assert out["A"].iloc[0] == 1234567890.0


def test_convert_values_known_unit_wan_yuan():
    rules = load_cleaning_rules()
    rules.unit_overrides = {"A": "万元"}
    df = pd.DataFrame({"A": [1234.0]})
    out = convert_values(df, rules)
    assert out["A"].iloc[0] == 12340000.0
```

- [ ] **Step 2: Run test, expect failure**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: ImportError (`rule_cleaner` not found).

- [ ] **Step 3: Implement rule_cleaner.py (part 1)**

Create `astock_fundamentals/ground_truth/rule_cleaner.py`:

```python
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

    skip_items = []
    if skip_items_path is None:
        skip_items_path = os.path.join(RULES_DIR, "skip_items.yaml")
    if os.path.exists(skip_items_path):
        with open(skip_items_path, "r", encoding="utf-8") as f:
            skip_items = yaml.safe_load(f) or []

    return CleaningRules(
        aliases=aliases,
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
```

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/ground_truth/rule_cleaner.py tests/ground_truth/test_rule_cleaner.py
git commit -m "feat(rule_cleaner): column rename and value conversion"
```

---

## Task 4: Run baseline comparison for 2019-2022

**Files:**
- Create: `data/ground_truth_reports/baseline_2019_2022.json` (output)
- Use: `scripts/clean_sina_pipeline.py` (created in Task 6)

- [ ] **Step 1: Write stub for baseline command in pipeline (Task 6 will fully implement)**

For now, create a minimal one-off runner at `scripts/baseline_2019_2022.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""One-off baseline: compare Sina 2019-2022 vs RDS using current comparator."""

import json
import os
import sys
from typing import Dict, List

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.sources.rds.rds_loader import RdsLoader
from astock_fundamentals.ground_truth.sina_loader import SinaLoader
from astock_fundamentals.ground_truth.comparator import compare_stock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE, "data", "akshare_bulk")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
OUTPUT = os.path.join(BASE, "data", "ground_truth_reports", "baseline_2019_2022.json")

YEARS = [2019, 2020, 2021, 2022]
SAMPLE_STOCKS = ["000001", "600000", "600036", "600519", "000002", "000858"]
STATEMENT_TYPES = ["balance_sheet", "income_statement", "cash_flow"]


def main():
    loader = SinaLoader(CACHE_DIR)
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    results: List[dict] = []
    for code in SAMPLE_STOCKS:
        for st in STATEMENT_TYPES:
            try:
                sina_df = loader.get_annual(code, YEARS, st)
            except FileNotFoundError:
                continue
            if sina_df.empty:
                continue
            sina_dict = sina_df.to_dict(orient="records")
            for row in sina_dict:
                year = int(str(row.get("报告日", ""))[:4])
                r = compare_stock(
                    stock_code=code,
                    year=year,
                    sina_data=row,
                    rds_loader=rds,
                    statement_type=st,
                )
                results.append({
                    "stock_code": code,
                    "year": year,
                    "statement_type": st,
                    "matched_count": r.matched_count,
                    "total_rds_items": r.gt_items,
                })
    by_stmt: Dict[str, dict] = {}
    for r in results:
        k = r["statement_type"]
        by_stmt.setdefault(k, {"total": 0, "matched": 0})
        by_stmt[k]["total"] += r["total_rds_items"]
        by_stmt[k]["matched"] += r["matched_count"]
    summary = {
        "scope": f"{len(SAMPLE_STOCKS)} stocks x {YEARS} x {len(STATEMENT_TYPES)}",
        "total_comparisons": len(results),
        "by_statement": {
            k: {
                "rds_items": v["total"],
                "matched": v["matched"],
                "match_rate": v["matched"] / v["total"] if v["total"] else 0,
            } for k, v in by_stmt.items()
        },
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run baseline**

Run: `python scripts/baseline_2019_2022.py`
Expected: prints a JSON summary with `by_statement.match_rate` for BS/IS/CF and writes the JSON file. No assertion — this is a measurement task.

- [ ] **Step 3: Commit**

```bash
git add scripts/baseline_2019_2022.py data/ground_truth_reports/baseline_2019_2022.json
git commit -m "feat(measurement): 2019-2022 baseline Sina vs RDS comparison"
```

---

## Task 5: Implement aggregation rules in rule_cleaner

**Files:**
- Modify: `astock_fundamentals/ground_truth/rule_cleaner.py`
- Modify: `tests/ground_truth/test_rule_cleaner.py`

- [ ] **Step 1: Add failing tests for aggregation**

Append to `tests/ground_truth/test_rule_cleaner.py`:

```python
def test_aggregate_sums_subitems_into_target():
    from astock_fundamentals.ground_truth.rule_cleaner import apply_aggregations
    rules = load_cleaning_rules()
    rules.aggregations = {
        "balance_sheet": [
            {
                "target": "其他应收款合计",
                "sources": ["其他应收款-关联方", "其他应收款-外部"],
                "op": "sum",
            }
        ]
    }
    df = pd.DataFrame({
        "其他应收款-关联方": [100.0],
        "其他应收款-外部": [200.0],
        "其他科目": [50.0],
    })
    out = apply_aggregations(df, "balance_sheet", rules)
    assert "其他应收款合计" in out.columns
    assert out["其他应收款合计"].iloc[0] == 300.0


def test_aggregate_uses_first_when_op_first():
    from astock_fundamentals.ground_truth.rule_cleaner import apply_aggregations
    rules = load_cleaning_rules()
    rules.aggregations = {
        "balance_sheet": [
            {
                "target": "X",
                "sources": ["X-a", "X-b"],
                "op": "first",
            }
        ]
    }
    df = pd.DataFrame({"X-a": [11.0], "X-b": [22.0]})
    out = apply_aggregations(df, "balance_sheet", rules)
    assert out["X"].iloc[0] == 11.0
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: ImportError on `apply_aggregations`.

- [ ] **Step 3: Add apply_aggregations to rule_cleaner.py**

Append to `astock_fundamentals/ground_truth/rule_cleaner.py`:

```python
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
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/ground_truth/rule_cleaner.py tests/ground_truth/test_rule_cleaner.py
git commit -m "feat(rule_cleaner): aggregation of Sina sub-items into RDS totals"
```

---

## Task 6: Pipeline orchestrator script (Steps 1-5)

**Files:**
- Create: `scripts/clean_sina_pipeline.py`
- Test: `tests/scripts/test_clean_pipeline.py`

- [ ] **Step 1: Write failing test for end-to-end on 2 stocks**

Create `tests/scripts/test_clean_pipeline.py`:

```python
import os
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline_runs_on_two_stocks():
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(PROJECT_ROOT, "scripts", "clean_sina_pipeline.py"),
            "--stocks", "000001", "600000",
            "--years", "2019", "2020", "2021", "2022",
            "--output-dir", os.path.join(PROJECT_ROOT, "data", "exports_v2"),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    out_dir = os.path.join(PROJECT_ROOT, "data", "exports_v2")
    assert os.path.exists(os.path.join(out_dir, "sina_cleaned_balance_sheet.csv"))
    assert os.path.exists(os.path.join(out_dir, "sina_cleaned_income_statement.csv"))
    assert os.path.exists(os.path.join(out_dir, "sina_cleaned_cash_flow.csv"))
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/scripts/test_clean_pipeline.py -v`
Expected: subprocess fails because the script does not exist.

- [ ] **Step 3: Implement clean_sina_pipeline.py**

Create `scripts/clean_sina_pipeline.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sina→RDS cleaning pipeline orchestrator.

Steps:
1. Slice Sina 2019-2022 annual rows
2. Match against RDS via existing comparator
3. Emit matching report (JSON)
4. Apply externalized cleaning rules (rename / unit / aggregate)
5. Write Tidy Data CSV aligned to field_order.yaml display_order
"""

import argparse
import json
import os
import sys
from typing import Dict, List

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astock_fundamentals.ground_truth.sina_loader import SinaLoader
from astock_fundamentals.ground_truth.rule_cleaner import (
    load_cleaning_rules, rename_columns, convert_values, apply_aggregations,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CACHE = os.path.join(BASE, "data", "akshare_bulk")
DEFAULT_OUTPUT = os.path.join(BASE, "data", "exports_v2")
DEFAULT_REPORT_DIR = os.path.join(BASE, "data", "ground_truth_reports")
FIELD_ORDER_PATH = os.path.join(BASE, "rules", "field_order.yaml")


def _parse_years(values: List[str]) -> List[int]:
    return [int(v) for v in values]


def _load_field_order() -> Dict[str, Dict[str, int]]:
    with open(FIELD_ORDER_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _tidy_rows(
    df: pd.DataFrame,
    statement_type: str,
    field_order: Dict[str, Dict[str, int]],
    stock_code: str,
) -> pd.DataFrame:
    """Pivot wide cleaned rows into Tidy (one row per field per period)."""
    order_map = field_order.get(statement_type, {})
    rows: List[dict] = []
    for _, row in df.iterrows():
        period = str(row.get("报告日", ""))
        for canonical, order in order_map.items():
            if canonical in df.columns:
                value = row[canonical]
                if pd.notna(value):
                    rows.append({
                        "stock_code": stock_code,
                        "year": int(period[:4]) if period else 0,
                        "period": "annual",
                        "statement_type": statement_type,
                        "field_name": canonical,
                        "value": float(value),
                        "display_order": order,
                    })
    return pd.DataFrame(rows)


def run_pipeline(
    stocks: List[str],
    years: List[int],
    cache_dir: str,
    output_dir: str,
    report_dir: str,
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)
    field_order = _load_field_order()
    rules = load_cleaning_rules()

    summary: Dict[str, dict] = {}
    tidy_frames: Dict[str, List[pd.DataFrame]] = {
        "balance_sheet": [],
        "income_statement": [],
        "cash_flow": [],
    }

    loader = SinaLoader(cache_dir)
    for code in stocks:
        for st in ["balance_sheet", "income_statement", "cash_flow"]:
            try:
                sina_df = loader.get_annual(code, years, st)
            except FileNotFoundError:
                continue
            if sina_df.empty:
                continue
            cleaned = rename_columns(sina_df, st, rules)
            cleaned = convert_values(cleaned, rules)
            cleaned = apply_aggregations(cleaned, st, rules)
            tidy_frames[st].append(_tidy_rows(cleaned, st, field_order, code))
            summary.setdefault(st, {"stocks": set(), "rows": 0})
            summary[st]["stocks"].add(code)
            summary[st]["rows"] += len(cleaned)

    for st, frames in tidy_frames.items():
        if not frames:
            continue
        out_df = pd.concat(frames, ignore_index=True)
        out_path = os.path.join(output_dir, f"sina_cleaned_{st}.csv")
        out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"  wrote {len(out_df)} rows to {out_path}")

    summary_json = {
        st: {"stocks": len(v["stocks"]), "rows": v["rows"]}
        for st, v in summary.items()
    }
    report_path = os.path.join(report_dir, "cleaning_run_summary.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)
    print(f"Summary written to {report_path}")


def main() -> int:
    p = argparse.ArgumentParser(description="Sina→RDS cleaning pipeline")
    p.add_argument("--stocks", nargs="+", default=["000001", "600000"])
    p.add_argument("--years", nargs="+", required=True)
    p.add_argument("--cache-dir", default=DEFAULT_CACHE)
    p.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    p.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
    args = p.parse_args()

    run_pipeline(
        stocks=args.stocks,
        years=_parse_years(args.years),
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/scripts/test_clean_pipeline.py -v`
Expected: PASS in < 600s.

- [ ] **Step 5: Commit**

```bash
git add scripts/clean_sina_pipeline.py tests/scripts/test_clean_pipeline.py
git commit -m "feat(pipeline): Sina→RDS cleaning pipeline orchestrator"
```

---

## Task 7: Append discovered aliases to rules/aliases.yaml

**Files:**
- Modify: `rules/aliases.yaml` (append a new top-level key)

- [ ] **Step 1: Inspect current aliases.yaml structure**

Run: `head -30 rules/aliases.yaml`
Expected: top-level keys are `balance_sheet`, `income_statement`, `cash_flow`, with each canonical name mapping to a list of aliases.

- [ ] **Step 2: Extract discovered aliases from the baseline**

Run: `python -c "
import json
with open('data/ground_truth_reports/baseline_2019_2022.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(json.dumps(data, ensure_ascii=False, indent=2))
"`
This shows you the baseline numbers — keep them in mind for the final progression report.

- [ ] **Step 3: Append 2019-2022 alias block**

Append to `rules/aliases.yaml` (preserve existing content, add a new top-level section):

```yaml

# ============================================================================
# Sina→RDS aliases (2019-2022)
# Auto-derived from baseline_2019_2022.json + manual confirmation.
# Format: {statement_type: {rds_canonical_name: [sina_alias_1, sina_alias_2, ...]}}
# ============================================================================

sina_aliases_2019_2022:
  balance_sheet: {}
  income_statement: {}
  cash_flow: {}
```

The new block starts empty — it will be filled in by `auto_learner` after the rules engine recognises the new schema. (This task sets up the structure; Task 8 populates the real content.)

- [ ] **Step 4: Verify YAML still parses**

Run: `python -c "import yaml; print(len(yaml.safe_load(open('rules/aliases.yaml','r',encoding='utf-8'))))"`
Expected: 4 (existing 3 statement types + sina_aliases_2019_2022).

- [ ] **Step 5: Commit**

```bash
git add rules/aliases.yaml
git commit -m "feat(rules): scaffold sina_aliases_2019_2022 in aliases.yaml"
```

---

## Task 8: Append aggregation rules to value_mapping_rules.yaml

**Files:**
- Modify: `rules/value_mapping_rules.yaml`

- [ ] **Step 1: Inspect existing top-level keys**

Run: `head -20 rules/value_mapping_rules.yaml`
Expected: existing rules use a `value_mapping:` top-level key.

- [ ] **Step 2: Append aggregation block**

Append to `rules/value_mapping_rules.yaml`:

```yaml

# ============================================================================
# Sina→RDS aggregation rules (2019-2022)
# Sub-items in Sina (multiple细项) → RDS standard totals.
# ============================================================================

sina_aggregations_2019_2022:
  balance_sheet:
    - target: "其他应收款"
      sources:
        - "其他应收款-关联方"
        - "其他应收款-外部"
        - "其他应收款-合计"
      op: sum
  income_statement: []
  cash_flow: []
```

- [ ] **Step 3: Verify YAML parses**

Run: `python -c "import yaml; d=yaml.safe_load(open('rules/value_mapping_rules.yaml','r',encoding='utf-8')); print(list(d.keys()))"`
Expected: existing keys + `sina_aggregations_2019_2022`.

- [ ] **Step 4: Add a test that loads these rules into CleaningRules**

Add to `tests/ground_truth/test_rule_cleaner.py`:

```python
def test_load_real_yaml_rules_has_sina_block():
    rules = load_cleaning_rules()
    assert hasattr(rules, "aliases")
    assert isinstance(rules.aggregations, dict)
```

- [ ] **Step 5: Run all rule_cleaner tests**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add rules/value_mapping_rules.yaml tests/ground_truth/test_rule_cleaner.py
git commit -m "feat(rules): add sina_aggregations_2019_2022 scaffolding"
```

---

## Task 9: Wire sina_aliases into load_cleaning_rules

**Files:**
- Modify: `astock_fundamentals/ground_truth/rule_cleaner.py`

- [ ] **Step 1: Add failing test for sina_aliases_2019_2022 loading**

Append to `tests/ground_truth/test_rule_cleaner.py`:

```python
def test_sina_aliases_2019_2022_loaded_into_balance_sheet():
    rules = load_cleaning_rules()
    # After Task 7 added the sina_aliases_2019_2022 block,
    # load_cleaning_rules should merge it into rules.aliases[statement_type]
    assert "balance_sheet" in rules.aliases
```

- [ ] **Step 2: Run, expect pass (the block exists, even if empty)**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: 9 passed (no change yet — just confirms the scaffold is in place).

- [ ] **Step 3: Update load_cleaning_rules to merge sina_aliases and sina_aggregations**

In `astock_fundamentals/ground_truth/rule_cleaner.py`, modify `load_cleaning_rules` so after loading `aliases.yaml`, it merges `sina_aliases_2019_2022` content into `rules.aliases`:

```python
    # After existing aliases loading and before the return:
    sina_block = aliases.pop("sina_aliases_2019_2022", None) or {}
    for stype, items in sina_block.items():
        aliases.setdefault(stype, {})
        for canonical, alts in items.items():
            aliases[stype].setdefault(canonical, [])
            for a in alts or []:
                if a not in aliases[stype][canonical]:
                    aliases[stype][canonical].append(a)
```

Also update value_mapping loading to populate `rules.aggregations` from `sina_aggregations_2019_2022`:

```python
    # In load_cleaning_rules, after building CleaningRules:
    if value_mapping_path is None:
        value_mapping_path = os.path.join(RULES_DIR, "value_mapping_rules.yaml")
    aggregations: Dict[str, List[dict]] = {}
    if os.path.exists(value_mapping_path):
        with open(value_mapping_path, "r", encoding="utf-8") as f:
            vm = yaml.safe_load(f) or {}
        aggregations = vm.get("sina_aggregations_2019_2022", {}) or {}
    return CleaningRules(
        aliases=aliases,
        aggregations=aggregations,
        skip_items=list(skip_items),
    )
```

- [ ] **Step 4: Run, expect pass**

Run: `pytest tests/ground_truth/test_rule_cleaner.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/ground_truth/rule_cleaner.py tests/ground_truth/test_rule_cleaner.py
git commit -m "feat(rule_cleaner): load sina_aliases_2019_2022 and sina_aggregations"
```

---

## Task 10: End-to-end pipeline test on the real data

**Files:**
- Create: `data/ground_truth_reports/cleaning_progression.md`

- [ ] **Step 1: Run the orchestrator on a 4-stock sample**

Run: `python scripts/clean_sina_pipeline.py --stocks 000001 600000 600036 600519 --years 2019 2020 2021 2022`
Expected: prints summary, writes 3 CSVs to `data/exports_v2/`.

- [ ] **Step 2: Inspect output**

Run: `head -3 data/exports_v2/sina_cleaned_balance_sheet.csv`
Expected: Tidy Data with columns `stock_code, year, period, statement_type, field_name, value, display_order`.

Run: `wc -l data/exports_v2/sina_cleaned_*.csv`
Expected: BS/IS/CF each have at least hundreds of rows.

- [ ] **Step 3: Write progression report**

Create `data/ground_truth_reports/cleaning_progression.md`:

```markdown
# Sina→RDS Cleaning Progression (2019-2022)

## Run summary

- Stocks processed: 4
- Years: 2019-2022
- Output: data/exports_v2/sina_cleaned_{balance_sheet,income_statement,cash_flow}.csv

## Row counts (after Task 10)

| Statement | Rows | Stocks |
|-----------|------|--------|
| balance_sheet | <BS_ROWS> | <BS_STOCKS> |
| income_statement | <IS_ROWS> | <IS_STOCKS> |
| cash_flow | <CF_ROWS> | <CF_STOCKS> |

## Baseline match rates (from baseline_2019_2022.json)

| Statement | Match rate |
|-----------|-----------|
| balance_sheet | <BS_RATE> |
| income_statement | <IS_RATE> |
| cash_flow | <CF_RATE> |

## Next rounds

- Round 1: populate sina_aliases_2019_2022 with discovered aliases
- Round 2: extend sina_aggregations_2019_2022 with CF sub-items
- Round 3: re-measure and append delta
```

Fill in the `<...>` placeholders with actual values from the run.

- [ ] **Step 4: Commit**

```bash
git add data/ground_truth_reports/cleaning_progression.md data/exports_v2/sina_cleaned_*.csv
git commit -m "feat(pipeline): first end-to-end cleaning run on 4 stocks"
```

---

## Self-Review

**1. Spec coverage:**
- Step 1 (annual slice) → Task 2 ✓
- Step 2 (name match) → covered by reusing `comparator.compare_stock` (already exists); cleaning rule path is Task 3
- Step 3 (matching report) → Task 4 (baseline), Task 10 (progression)
- Step 4 (rule learning) → Task 7, Task 8 scaffold the structure; populating real rules is a follow-up round
- Step 5 (cleaning) → Tasks 3, 5, 6, 9
- Tidy Data output with display_order → Task 6 (`_tidy_rows`), Task 10 (verification)

**2. Placeholder scan:** No "TBD" or "TODO" remains. All code blocks are complete. Test steps include exact expected output.

**3. Type consistency:** `CleaningRules` is defined once in Task 3; reused in Tasks 5, 8, 9. `rename_columns`, `convert_values`, `apply_aggregations` signatures are stable. `SinaLoader.get_annual` signature is used identically in Task 4 and Task 6.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-sina-rds-cleaning-pipeline.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks
2. **Inline Execution** - execute tasks in this session with checkpoints

Which approach?
