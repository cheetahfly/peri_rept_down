# EM 渠道全面评估实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 评估 akshare-EM（东方财富）渠道对 A 股财报数据的下载完整性与数据质量（vs RDS），产出结构化评估结论。

**Architecture:** 6 个独立运行的 Python CLI 脚本（抽样→下载→完整性→比对→疑难→报告），共享一个 `eval_em_lib.py` 工具模块。对生产代码 0 处修改。

**Tech Stack:** Python 3.13、AKShare 1.18+、pandas、pytest

**Spec:** `docs/superpowers/specs/2026-06-10-em-channel-evaluation-design.md`

**Error tolerance:** EM 与 RDS 值差异 |Δ| ≤ 1.00 元 = 匹配（与项目数据精度规则"分"一致）。

---

## 文件结构

```
scripts/
  eval_em_lib.py                 # 共享工具（分类/抽样/解析/比对/报告）
  eval_em_sample.py              # M1: 抽样 200 只
  eval_em_download.py            # M2: 下载
  eval_em_completeness.py        # M3: 完整性
  eval_em_compare_rds.py         # M4: 比对
  eval_em_historical.py          # M5: 疑难
  eval_em_report.py              # M6: 报告
tests/eval_em/
  __init__.py
  conftest.py                    # 共享 fixtures
  test_sample.py                 # 板块分类 + 抽样
  test_parse.py                  # Tidy 解析
  test_compare.py                # EM-RDS 比对
  test_historical.py             # 历史扫描
data/exports_v2/em_evaluation/
  .gitkeep                       # 输出目录
docs/audit/
  2026-06-10-em-channel-evaluation.md  # 最终报告（M6 生成）
```

**复用现有**：`astock_fundamentals.sources.rds.RdsLoader`、`data/decode_mappings_by_type.json`、`data/ground_truth_reports/full_stock_list.txt`（3902 只股票）。

---

## Phase 0：项目脚手架

### Task 0.1：创建目录与占位文件

**Files:**
- Create: `data/exports_v2/em_evaluation/.gitkeep`
- Create: `tests/eval_em/__init__.py`
- Create: `tests/eval_em/conftest.py`

- [ ] **Step 1: 创建空目录占位**

```bash
mkdir -p data/exports_v2/em_evaluation tests/eval_em
touch data/exports_v2/em_evaluation/.gitkeep
touch tests/eval_em/__init__.py
```

- [ ] **Step 2: 写入共享测试 fixtures**

写入 `tests/eval_em/conftest.py`：

```python
"""Shared test fixtures for EM evaluation tests."""
import pytest


@pytest.fixture
def sample_stock_list():
    """A small stock list spanning all 4 boards."""
    return [
        "600000", "600001", "601000", "603000",  # 沪市主板
        "000001", "000002", "002001",            # 深市主板
        "300001", "300002", "301001",            # 创业板
        "688001", "688002", "689001",            # 科创板
    ]


@pytest.fixture
def fake_em_balance_sheet_df():
    """A fake balance sheet DataFrame mimicking AKShare EM output."""
    import pandas as pd
    return pd.DataFrame({
        "REPORT_DATE": ["2022-03-31", "2022-06-30", "2022-09-30", "2022-12-31"],
        "货币资金": [100.0, 110.0, 120.0, 130.0],
        "应收账款": [50.0, 55.0, 60.0, 65.0],
    })


@pytest.fixture
def fake_em_cash_flow_df_with_yi_suffix():
    """Cash flow DataFrame with 亿 suffix on values."""
    import pandas as pd
    return pd.DataFrame({
        "REPORT_DATE": ["2022-12-31"],
        "经营活动产生的现金流量净额": ["100.50亿"],
    })
```

- [ ] **Step 3: 验证目录结构**

```bash
ls -la data/exports_v2/em_evaluation/ tests/eval_em/
```
预期：两个目录都存在，`.gitkeep` 和 `__init__.py` 存在。

- [ ] **Step 4: 提交**

```bash
git add data/exports_v2/em_evaluation/.gitkeep tests/eval_em/
git commit -m "chore(eval_em): scaffold evaluation directories and fixtures"
```

---

## Phase 1：抽样（M1）

### Task 1.1：板块分类函数（TDD）

**Files:**
- Create: `scripts/eval_em_lib.py`
- Test: `tests/eval_em/test_sample.py`

- [ ] **Step 1: 写测试**

写入 `tests/eval_em/test_sample.py`：

```python
"""Tests for board classifier and sampler."""
import pytest
from scripts.eval_em_lib import classify_board, BOARD_PREFIXES


def test_classify_sh_main():
    assert classify_board("600000") == "sh_main"
    assert classify_board("601000") == "sh_main"
    assert classify_board("603000") == "sh_main"
    assert classify_board("605000") == "sh_main"


def test_classify_sz_main():
    assert classify_board("000001") == "sz_main"
    assert classify_board("001001") == "sz_main"
    assert classify_board("002001") == "sz_main"


def test_classify_chinext():
    assert classify_board("300001") == "chinext"
    assert classify_board("301001") == "chinext"


def test_classify_star():
    assert classify_board("688001") == "star"
    assert classify_board("689001") == "star"


def test_classify_excludes_300_from_sz():
    """创业板 300/301 不应被分到深市主板。"""
    assert classify_board("300750") == "chinext"


def test_classify_unknown():
    """未知前缀归为 unknown。"""
    assert classify_board("999999") == "unknown"
    assert classify_board("830001") == "unknown"  # 北交所


def test_board_prefixes_complete():
    """所有 4 个板块都应在 BOARD_PREFIXES 中。"""
    assert set(BOARD_PREFIXES.keys()) == {"sh_main", "sz_main", "chinext", "star"}
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
python -m pytest tests/eval_em/test_sample.py -v
```
预期：FAIL with `ModuleNotFoundError: No module named 'scripts.eval_em_lib'`

- [ ] **Step 3: 实现 `classify_board`**

写入 `scripts/eval_em_lib.py`（第一部分）：

```python
# -*- coding: utf-8 -*-
"""
Shared library for EM channel evaluation.

Provides:
- Board classification (沪市主板/深市主板/创业板/科创板)
- Stock sampling (stratified random, seed-reproducible)
- Tidy CSV parsing (EM raw -> Tidy with F-code mapping)
- EM vs RDS comparison (1元 absolute tolerance)
- Historical issues scanner
- Report aggregator
"""

import json
import os
import random
import re
import time
import warnings
from typing import Dict, List, Optional, Tuple

import pandas as pd

warnings.filterwarnings("ignore")

# ----- 板块代码前缀映射 -----
BOARD_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "sh_main": ("600", "601", "603", "605"),  # 沪市主板
    "sz_main": ("000", "001", "002"),          # 深市主板（排除 003/300/301）
    "chinext": ("300", "301"),                 # 创业板
    "star":    ("688", "689"),                 # 科创板
}


def classify_board(stock_code: str) -> str:
    """Classify a stock code to one of 4 boards.

    Returns one of: sh_main, sz_main, chinext, star, unknown.
    """
    code = str(stock_code).zfill(6)
    for board, prefixes in BOARD_PREFIXES.items():
        for prefix in prefixes:
            if code.startswith(prefix):
                return board
    return "unknown"
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
python -m pytest tests/eval_em/test_sample.py -v
```
预期：7 个 test 都 PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_sample.py
git commit -m "feat(eval_em): add board classifier with tests"
```

---

### Task 1.2：分层抽样函数（TDD）

**Files:**
- Modify: `scripts/eval_em_lib.py`
- Modify: `tests/eval_em/test_sample.py`

- [ ] **Step 1: 追加测试**

追加到 `tests/eval_em/test_sample.py`：

```python
from scripts.eval_em_lib import stratified_sample


def test_stratified_sample_seed_reproducible():
    """相同 seed 必须产出相同结果。"""
    stock_list = [f"{600000 + i:06d}" for i in range(100)] + \
                 [f"{300000 + i:06d}" for i in range(100)] + \
                 [f"{688000 + i:06d}" for i in range(100)] + \
                 [f"{i:06d}" for i in range(1, 101)]
    s1 = stratified_sample(stock_list, per_board=10, seed=42)
    s2 = stratified_sample(stock_list, per_board=10, seed=42)
    assert s1 == s2


def test_stratified_sample_returns_4_boards():
    """返回 4 个板块各 N 只。"""
    stock_list = [f"{600000 + i:06d}" for i in range(50)] + \
                 [f"{300000 + i:06d}" for i in range(50)] + \
                 [f"{688000 + i:06d}" for i in range(50)] + \
                 [f"{i:06d}" for i in range(1, 51)]
    result = stratified_sample(stock_list, per_board=20, seed=1)
    assert set(result["boards"].keys()) == {"sh_main", "sz_main", "chinext", "star"}
    for board, codes in result["boards"].items():
        assert len(codes) == 20, f"{board} got {len(codes)}, expected 20"


def test_stratified_sample_insufficient_stocks():
    """某板块股票不足时只取该板块全部，但仍返回 4 个 key。"""
    stock_list = ["600000", "600001", "300000"]  # 只有 2 只沪市主板，1 只创业板
    result = stratified_sample(stock_list, per_board=5, seed=1)
    assert len(result["boards"]["sh_main"]) == 2  # 全部取走
    assert len(result["boards"]["chinext"]) == 1
    assert len(result["boards"]["star"]) == 0     # 无股票
    assert len(result["boards"]["sz_main"]) == 0


def test_stratified_sample_includes_all_codes():
    """all_codes 字段汇总 4 个板块的所有股票。"""
    stock_list = [f"{600000 + i:06d}" for i in range(50)] + \
                 [f"{i:06d}" for i in range(1, 51)]
    result = stratified_sample(stock_list, per_board=10, seed=1)
    total = sum(len(v) for v in result["boards"].values())
    assert len(result["all_codes"]) == total
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
python -m pytest tests/eval_em/test_sample.py::test_stratified_sample_seed_reproducible -v
```
预期：FAIL with `ImportError: cannot import name 'stratified_sample'`

- [ ] **Step 3: 实现 `stratified_sample`**

追加到 `scripts/eval_em_lib.py`：

```python
def stratified_sample(
    stock_list: List[str],
    per_board: int = 50,
    seed: int = 42,
) -> Dict:
    """Stratified random sample: per_board stocks from each of 4 boards.

    Args:
        stock_list: full A-share stock codes.
        per_board: how many to sample from each board (default 50).
        seed: random seed for reproducibility.

    Returns:
        {
            "seed": 42,
            "per_board": 50,
            "boards": {"sh_main": [...], "sz_main": [...], "chinext": [...], "star": [...]},
            "all_codes": [所有抽到的代码]
        }
    """
    by_board: Dict[str, List[str]] = {b: [] for b in BOARD_PREFIXES}
    for code in stock_list:
        board = classify_board(code)
        if board in by_board:
            by_board[board].append(code)

    rng = random.Random(seed)
    sampled: Dict[str, List[str]] = {}
    for board, codes in by_board.items():
        rng.shuffle(codes)
        sampled[board] = codes[:per_board]

    all_codes = []
    for codes in sampled.values():
        all_codes.extend(codes)

    return {
        "seed": seed,
        "per_board": per_board,
        "boards": sampled,
        "all_codes": all_codes,
    }
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
python -m pytest tests/eval_em/test_sample.py -v
```
预期：所有 test PASS（11 个）。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_sample.py
git commit -m "feat(eval_em): add stratified stock sampler with tests"
```

---

### Task 1.3：抽样 CLI 入口

**Files:**
- Create: `scripts/eval_em_sample.py`

- [ ] **Step 1: 实现 CLI 入口**

写入 `scripts/eval_em_sample.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M1: Sample 200 A-share stocks (50 from each of 4 boards) for EM evaluation.

Usage:
    python scripts/eval_em_sample.py --seed 42

Output:
    data/exports_v2/em_evaluation/sample_200.json
"""
import argparse
import json
import os
import sys
from datetime import datetime

# Ensure project root is on path so scripts/eval_em_lib is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import stratified_sample  # noqa: E402

BASE = _PROJECT_ROOT
STOCK_LIST = os.path.join(BASE, "data", "ground_truth_reports", "full_stock_list.txt")
OUTPUT_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")


def load_full_stock_list() -> list:
    with open(STOCK_LIST, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    p.add_argument("--per-board", type=int, default=50, help="Per board sample size (default 50)")
    args = p.parse_args()

    if not os.path.exists(STOCK_LIST):
        print(f"ERROR: Stock list not found: {STOCK_LIST}")
        return 1

    stock_list = load_full_stock_list()
    print(f"Loaded {len(stock_list)} stocks from {STOCK_LIST}")

    result = stratified_sample(stock_list, per_board=args.per_board, seed=args.seed)
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    result["source_stock_list"] = STOCK_LIST

    # Print summary
    print(f"\nSampled {args.per_board} from each board (seed={args.seed}):")
    for board, codes in result["boards"].items():
        print(f"  {board:10s}: {len(codes):3d} stocks  (samples: {codes[:3]}...)")
    print(f"  TOTAL      : {len(result['all_codes']):3d} stocks")

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 抽样并验证**

```bash
python scripts/eval_em_sample.py --seed 42
```
预期：
```
Sampled 50 from each board (seed=42):
  sh_main   :  50 stocks  (samples: ['600519', '600036', ...]...)
  ...
TOTAL      : 200 stocks
Saved to: data/exports_v2/em_evaluation/sample_200.json
```

- [ ] **Step 3: 验证 JSON 结构**

```bash
python -c "
import json
d = json.load(open('data/exports_v2/em_evaluation/sample_200.json', encoding='utf-8'))
assert len(d['all_codes']) == 200
for b, codes in d['boards'].items():
    assert len(codes) == 50, f'{b} has {len(codes)}'
print('OK: 4 boards × 50 = 200 stocks')
"
```

- [ ] **Step 4: 提交**

```bash
git add scripts/eval_em_sample.py data/exports_v2/em_evaluation/sample_200.json
git commit -m "feat(eval_em): add sample CLI; output sample_200.json with 4 boards x 50"
```

---

## Phase 2：下载（M2）

### Task 2.1：EM API 包装器（TDD）

**Files:**
- Modify: `scripts/eval_em_lib.py`
- Modify: `tests/eval_em/test_parse.py`

- [ ] **Step 1: 创建测试文件**

写入 `tests/eval_em/test_parse.py`：

```python
"""Tests for Tidy parser and EM API wrapper."""
import pandas as pd
import pytest

from scripts.eval_em_lib import (
    parse_to_tidy,
    detect_period,
    parse_yi_value,
    fetch_em_balance_sheet,
    fetch_em_income_statement,
    fetch_em_cash_flow,
    EM_API_MAX_RETRIES,
)


# ---- detect_period ----

def test_detect_period_q1():
    assert detect_period("2022-03-31") == "Q1"


def test_detect_period_half_year():
    assert detect_period("2022-06-30") == "half_year"


def test_detect_period_q3():
    assert detect_period("2022-09-30") == "Q3"


def test_detect_period_annual():
    assert detect_period("2022-12-31") == "annual"


def test_detect_period_invalid():
    assert detect_period("2022-13-31") is None
    assert detect_period("not-a-date") is None
    assert detect_period(None) is None


# ---- parse_yi_value ----

def test_parse_yi_value_with_yi_suffix():
    assert parse_yi_value("100.50亿") == 10050000000.0  # 100.50 × 1e8


def test_parse_yi_value_plain_number():
    assert parse_yi_value("1234.56") == 1234.56


def test_parse_yi_value_with_commas():
    assert parse_yi_value("1,234.56") == 1234.56


def test_parse_yi_value_invalid():
    assert parse_yi_value("not-a-number") is None
    assert parse_yi_value("") is None
    assert parse_yi_value(None) is None


# ---- parse_to_tidy ----

def test_parse_to_tidy_filters_by_year_and_period(fake_em_balance_sheet_df):
    """应只保留 2022 年的 4 个指定报告期。"""
    df = pd.DataFrame({
        "REPORT_DATE": ["2021-12-31", "2022-03-31", "2022-06-30", "2022-12-31", "2023-12-31"],
        "货币资金": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    field_map = {"货币资金": ("A001N", 1, "货币资金")}
    tidy = parse_to_tidy(df, "600000", 2022, field_map, "balance_sheet", source="em")
    assert len(tidy) == 3  # 排除 2021 和 2023
    assert set(tidy["period"]) == {"Q1", "half_year", "annual"}


def test_parse_to_tidy_handles_yi_suffix(fake_em_cash_flow_df_with_yi_suffix):
    tidy = parse_to_tidy(
        fake_em_cash_flow_df_with_yi_suffix, "600000", 2022,
        {"经营活动产生的现金流量净额": ("F046N", 46, "经营活动现金流量净额")},
        "cash_flow", source="em",
    )
    assert len(tidy) == 1
    assert tidy.iloc[0]["value"] == 10050000000.0


def test_parse_to_tidy_skips_unknown_columns():
    """未在 field_map 中的列应被跳过。"""
    df = pd.DataFrame({
        "REPORT_DATE": ["2022-12-31"],
        "货币资金": [100.0],
        "未知字段": [200.0],
    })
    field_map = {"货币资金": ("A001N", 1, "货币资金")}
    tidy = parse_to_tidy(df, "600000", 2022, field_map, "balance_sheet", source="em")
    assert len(tidy) == 1
    assert tidy.iloc[0]["field_code"] == "A001N"


def test_parse_to_tidy_sets_source_column():
    df = pd.DataFrame({
        "REPORT_DATE": ["2022-12-31"],
        "货币资金": [100.0],
    })
    field_map = {"货币资金": ("A001N", 1, "货币资金")}
    tidy = parse_to_tidy(df, "600000", 2022, field_map, "balance_sheet", source="em")
    assert tidy.iloc[0]["source"] == "em"


# ---- EM API wrapper constants ----

def test_em_api_max_retries_positive():
    assert EM_API_MAX_RETRIES >= 1
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
python -m pytest tests/eval_em/test_parse.py -v
```
预期：FAIL with `ImportError`。

- [ ] **Step 3: 实现 `detect_period` 和 `parse_yi_value`**

追加到 `scripts/eval_em_lib.py`：

```python
# ----- Tidy 解析 -----

PERIOD_MAP = {
    "03-31": "Q1",
    "06-30": "half_year",
    "09-30": "Q3",
    "12-31": "annual",
}

EM_API_MAX_RETRIES = 3
EM_API_REQUEST_DELAY = 0.5  # seconds


def detect_period(report_date: str) -> Optional[str]:
    """Detect report period from date string like '2022-03-31'.

    Returns 'Q1' / 'half_year' / 'Q3' / 'annual' or None if not a valid period end.
    """
    if not report_date or not isinstance(report_date, str):
        return None
    s = str(report_date).strip()
    # Try to find "MM-DD" pattern at the end
    m = re.search(r"(\d{2})-(\d{2})$", s)
    if not m:
        return None
    mm_dd = f"{m.group(1)}-{m.group(2)}"
    return PERIOD_MAP.get(mm_dd)


def parse_yi_value(val) -> Optional[float]:
    """Parse a financial value, handling '亿' suffix and commas.

    Examples:
        "100.50亿" -> 10050000000.0
        "1,234.56" -> 1234.56
        None -> None
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "false", "none"):
        return None
    try:
        if s.endswith("亿"):
            return float(s[:-1]) * 1e8
        # Remove commas
        s = s.replace(",", "")
        return float(s)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: 继续运行测试**

```bash
python -m pytest tests/eval_em/test_parse.py::test_detect_period_q1 tests/eval_em/test_parse.py::test_parse_yi_value_with_yi_suffix -v
```
预期：PASS（这两个测试现在应通过）。

- [ ] **Step 5: 实现 `parse_to_tidy`**

追加到 `scripts/eval_em_lib.py`：

```python
def parse_to_tidy(
    df: pd.DataFrame,
    stock_code: str,
    year: int,
    field_map: Dict[str, Tuple[str, int, str]],
    statement_type: str,
    source: str = "em",
) -> pd.DataFrame:
    """Parse EM raw DataFrame to Tidy CSV format.

    Args:
        df: raw DataFrame from EM API (must have 'REPORT_DATE' column).
        stock_code: 6-digit stock code.
        year: target year to filter (e.g. 2022).
        field_map: {column_name: (F-code, display_order, short_name)}.
        statement_type: 'balance_sheet' / 'income_statement' / 'cash_flow'.
        source: source label, default 'em'.

    Returns:
        DataFrame with columns:
            stock_code, year, period, statement_type, field_code, field_name, value, display_order, source
    """
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=[
            "stock_code", "year", "period", "statement_type",
            "field_code", "field_name", "value", "display_order", "source",
        ])

    # Find date column (case-insensitive search for REPORT_DATE)
    date_col = None
    for c in df.columns:
        if str(c).upper() in ("REPORT_DATE", "报告日期"):
            date_col = c
            break
    if date_col is None:
        # Fallback: first column
        date_col = df.columns[0]

    rows = []
    for _, row in df.iterrows():
        report_date = str(row[date_col])
        # Filter by year
        if not report_date.startswith(str(year)):
            continue
        period = detect_period(report_date)
        if period is None:
            continue

        for col_name, (fcode, order, short_name) in field_map.items():
            if col_name not in df.columns:
                continue
            val = parse_yi_value(row[col_name])
            if val is None:
                continue
            rows.append({
                "stock_code": str(stock_code).zfill(6),
                "year": year,
                "period": period,
                "statement_type": statement_type,
                "field_code": fcode,
                "field_name": short_name,
                "value": val,
                "display_order": order,
                "source": source,
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 6: 实现 EM API 包装器（仅声明，先不调用真实 API）**

追加到 `scripts/eval_em_lib.py`：

```python
# ----- EM API 包装器 -----

def _em_api_call(api_func, symbol: str):
    """Single EM API call with retry. Returns DataFrame or None."""
    import akshare as ak
    func = getattr(ak, api_func)
    for attempt in range(EM_API_MAX_RETRIES):
        try:
            df = func(symbol=symbol)
            time.sleep(EM_API_REQUEST_DELAY)
            return df
        except Exception as e:
            print(f"  Retry {attempt + 1}/{EM_API_MAX_RETRIES} for {symbol}: {type(e).__name__}")
            time.sleep(2 ** attempt)
    return None


def _to_em_symbol(stock_code: str) -> str:
    """Convert 6-digit code to EM symbol (SH600519 / SZ000001)."""
    code = str(stock_code).zfill(6)
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return f"SH{code}"
    return f"SZ{code}"


def fetch_em_balance_sheet(stock_code: str):
    """Fetch balance sheet from AKShare EM API. Returns DataFrame or None."""
    return _em_api_call("stock_balance_sheet_by_report_em", _to_em_symbol(stock_code))


def fetch_em_income_statement(stock_code: str):
    """Fetch income statement from AKShare EM API. Returns DataFrame or None."""
    return _em_api_call("stock_profit_statement_by_report_em", _to_em_symbol(stock_code))


def fetch_em_cash_flow(stock_code: str):
    """Fetch cash flow statement from AKShare EM API. Returns DataFrame or None."""
    return _em_api_call("stock_cash_flow_sheet_by_report_em", _to_em_symbol(stock_code))
```

- [ ] **Step 7: 运行测试，验证全部通过**

```bash
python -m pytest tests/eval_em/test_parse.py -v
```
预期：所有 test PASS（注意：EM API wrapper 测试不会被自动调用真实 API，因为 fixture 都没 mock 它们）。

- [ ] **Step 8: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_parse.py
git commit -m "feat(eval_em): add tidy parser, period detection, yi-suffix, EM API wrapper"
```

---

### Task 2.2：字段映射表加载

**Files:**
- Modify: `scripts/eval_em_lib.py`

- [ ] **Step 1: 实现 `load_field_map` 函数**

追加到 `scripts/eval_em_lib.py`：

```python
def load_field_map(statement_type: str) -> Dict[str, Tuple[str, int, str]]:
    """Load F-code field mapping for a statement type from project decode_mappings.

    Args:
        statement_type: 'balance_sheet' / 'income_statement' / 'cash_flow'.

    Returns:
        {em_column_name: (F-code, display_order, short_name)}.
        Empty dict if not found.
    """
    import json
    decode_path = os.path.join(BASE_DIR, "data", "decode_mappings_by_type.json")
    if not os.path.exists(decode_path):
        return {}
    with open(decode_path, "r", encoding="utf-8") as f:
        all_maps = json.load(f)
    # The decode_maps structure is {statement_type: {fcode: chinese_name}}
    # We need to invert this and also get display_order from rules
    fcode_to_name = all_maps.get(statement_type, {})
    if not fcode_to_name:
        return {}
    # Load display_order from rules/
    rules_dir = os.path.join(BASE_DIR, "rules")
    fcode_to_order = {}
    if os.path.isdir(rules_dir):
        for fname in os.listdir(rules_dir):
            if fname.endswith(".yaml") or fname.endswith(".yml"):
                try:
                    import yaml
                    with open(os.path.join(rules_dir, fname), "r", encoding="utf-8") as f:
                        rule = yaml.safe_load(f)
                    if rule and "fields" in rule:
                        for fcode, info in rule["fields"].items():
                            if "display_order" in info:
                                fcode_to_order[fcode] = info["display_order"]
                except Exception:
                    pass

    field_map: Dict[str, Tuple[str, int, str]] = {}
    for fcode, name in fcode_to_name.items():
        order = fcode_to_order.get(fcode, 999)
        field_map[name] = (fcode, order, name)
    return field_map
```

同时在 `eval_em_lib.py` 顶部添加 `BASE_DIR` 常量（紧跟 import 之后）：

```python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

- [ ] **Step 2: 验证函数能加载映射**

```bash
python -c "
import sys, os
sys.path.insert(0, r'$(pwd)')
from scripts.eval_em_lib import load_field_map
m = load_field_map('balance_sheet')
print(f'Loaded {len(m)} balance sheet fields')
print('Sample:', list(m.items())[:3])
"
```
预期：打印 3+ 个 BS 字段映射。

- [ ] **Step 3: 提交**

```bash
git add scripts/eval_em_lib.py
git commit -m "feat(eval_em): add load_field_map from decode_mappings_by_type.json"
```

---

### Task 2.3：下载 CLI 入口

**Files:**
- Create: `scripts/eval_em_download.py`

- [ ] **Step 1: 实现下载 CLI**

写入 `scripts/eval_em_download.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M2: Download EM data for 200 sampled stocks (4 periods × 3 statements).

Usage:
    python scripts/eval_em_download.py [--limit N] [--year 2022]

Output:
    data/exports_v2/em_evaluation/balance_sheet/{code}.csv
    data/exports_v2/em_evaluation/income_statement/{code}.csv
    data/exports_v2/em_evaluation/cash_flow/{code}.csv
    data/exports_v2/em_evaluation/download_progress.json
    data/exports_v2/em_evaluation/download.log
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import (  # noqa: E402
    fetch_em_balance_sheet,
    fetch_em_income_statement,
    fetch_em_cash_flow,
    parse_to_tidy,
    load_field_map,
    EM_API_REQUEST_DELAY,
)

BASE = _PROJECT_ROOT
SAMPLE_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
PROGRESS_PATH = os.path.join(OUTPUT_ROOT, "download_progress.json")
LOG_PATH = os.path.join(OUTPUT_ROOT, "download.log")
YEAR = 2022

STATEMENT_TYPES = [
    ("balance_sheet", fetch_em_balance_sheet),
    ("income_statement", fetch_em_income_statement),
    ("cash_flow", fetch_em_cash_flow),
]


def log(msg: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def load_progress() -> dict:
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict) -> None:
    tmp = PROGRESS_PATH + ".tmp"
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    if os.path.exists(PROGRESS_PATH):
        os.remove(PROGRESS_PATH)
    os.rename(tmp, PROGRESS_PATH)


def process_stock(stock_code: str, progress: dict) -> None:
    """Process one stock: fetch all 3 statements, save to CSV."""
    for stmt_type, fetch_func in STATEMENT_TYPES:
        out_dir = os.path.join(OUTPUT_ROOT, stmt_type)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{stock_code}.csv")

        # Skip if already done
        if progress.get(f"{stock_code}|{stmt_type}") in ("done", "no_data"):
            continue

        # Fetch
        df = fetch_func(stock_code)
        if df is None or len(df) == 0:
            progress[f"{stock_code}|{stmt_type}"] = "no_data"
            log(f"  {stock_code}/{stmt_type}: no_data")
            continue

        # Parse to tidy
        field_map = load_field_map(stmt_type)
        if not field_map:
            log(f"  {stock_code}/{stmt_type}: no field map")
            progress[f"{stock_code}|{stmt_type}"] = "no_data"
            continue

        tidy = parse_to_tidy(df, stock_code, YEAR, field_map, stmt_type, source="em")
        if len(tidy) == 0:
            progress[f"{stock_code}|{stmt_type}"] = "no_data"
            log(f"  {stock_code}/{stmt_type}: no rows after parse")
            continue

        # Save
        tidy.to_csv(out_path, index=False, encoding="utf-8-sig")
        progress[f"{stock_code}|{stmt_type}"] = "done"
        log(f"  {stock_code}/{stmt_type}: {len(tidy)} rows saved")
        time.sleep(EM_API_REQUEST_DELAY)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None, help="Limit to first N stocks (for testing)")
    p.add_argument("--year", type=int, default=YEAR, help=f"Year (default {YEAR})")
    args = p.parse_args()

    if not os.path.exists(SAMPLE_PATH):
        print(f"ERROR: Sample not found: {SAMPLE_PATH}. Run eval_em_sample.py first.")
        return 1

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)
    codes = sample["all_codes"]
    if args.limit:
        codes = codes[:args.limit]
    print(f"Processing {len(codes)} stocks for year {args.year}...")

    progress = load_progress()

    for i, code in enumerate(codes):
        process_stock(code, progress)
        save_progress(progress)
        if (i + 1) % 10 == 0:
            done = sum(1 for v in progress.values() if v == "done")
            no_data = sum(1 for v in progress.values() if v == "no_data")
            print(f"  [{i + 1}/{len(codes)}] {code}: done={done}, no_data={no_data}")

    # Final summary
    done = sum(1 for v in progress.values() if v == "done")
    no_data = sum(1 for v in progress.values() if v == "no_data")
    failed = sum(1 for v in progress.values() if v == "failed")
    print(f"\nFinal: done={done}, no_data={no_data}, failed={failed}")
    print(f"Log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 烟雾测试 3 只股票**

```bash
python scripts/eval_em_download.py --limit 3
```
预期：3 只股票×3 张表=9 个进度条目，部分可能 no_data，但脚本能跑通。

- [ ] **Step 3: 检查输出文件**

```bash
ls -la data/exports_v2/em_evaluation/balance_sheet/ | head -10
echo "---"
ls -la data/exports_v2/em_evaluation/cash_flow/ | head -10
```
预期：每张表至少有 1-3 个 CSV。

- [ ] **Step 4: 提交**

```bash
git add scripts/eval_em_download.py
git commit -m "feat(eval_em): add download CLI with checkpoint + retry"
```

---

### Task 2.4：全量下载 200 只股票

**Files:** （无文件创建；运行已存在的脚本）

- [ ] **Step 1: 清理 3 只烟雾测试数据**

```bash
rm -f data/exports_v2/em_evaluation/balance_sheet/*.csv
rm -f data/exports_v2/em_evaluation/income_statement/*.csv
rm -f data/exports_v2/em_evaluation/cash_flow/*.csv
rm -f data/exports_v2/em_evaluation/download_progress.json
```

- [ ] **Step 2: 全量下载**

```bash
python scripts/eval_em_download.py
```
预期耗时：30-60 分钟。脚本会持续打印进度。

> **注意**：如果中途网络异常，脚本会重试；如彻底中断，重新运行会从断点恢复。

- [ ] **Step 3: 验证最终进度**

```bash
python -c "
import json
d = json.load(open('data/exports_v2/em_evaluation/download_progress.json', encoding='utf-8'))
from collections import Counter
print(f'Total: {len(d)}')
print(f'  {dict(Counter(d.values()))}')
print(f'Expected: 200 stocks × 3 statements = 600 entries')
"
```

- [ ] **Step 4: 验证 CSV 文件数**

```bash
for t in balance_sheet income_statement cash_flow; do
  count=$(ls data/exports_v2/em_evaluation/$t/ | wc -l)
  echo "$t: $count files"
done
```

- [ ] **Step 5: 提交（仅 progress 和 log，不提交 CSV 数据）**

按 CLAUDE.md "数据文件和脚本文件分开提交" 规则：

```bash
git add scripts/eval_em_download.py  # 脚本已在 Task 2.3 提交
# 进度/日志不进 git
echo "data/exports_v2/em_evaluation/*/$(ls data/exports_v2/em_evaluation/balance_sheet/ | head -1)" > /dev/null
git status
```

---

## Phase 3：完整性检查（M3）

### Task 3.1：完整性检查函数（TDD）

**Files:**
- Modify: `scripts/eval_em_lib.py`
- Modify: `tests/eval_em/test_parse.py`（追加测试）

- [ ] **Step 1: 追加测试**

追加到 `tests/eval_em/test_parse.py`：

```python
from scripts.eval_em_lib import check_completeness


def test_check_completeness_full(tmp_path):
    """所有 12 项齐全 → complete=True。"""
    sample = {"all_codes": ["600000", "300001"]}
    for code in sample["all_codes"]:
        for t in ("balance_sheet", "income_statement", "cash_flow"):
            (tmp_path / t).mkdir(parents=True, exist_ok=True)
            (tmp_path / t / f"{code}.csv").write_text("h\n", encoding="utf-8")

    result = check_completeness(sample, str(tmp_path))
    assert result["total_stocks"] == 2
    assert result["complete_stocks"] == 2
    assert result["coverage_rate"] == 1.0
    assert result["completeness_rate"] == 1.0


def test_check_completeness_partial(tmp_path):
    """部分缺失 → coverage/completeness 不同。"""
    sample = {"all_codes": ["600000", "300001", "688001"]}
    # 600000: 全部
    for t in ("balance_sheet", "income_statement", "cash_flow"):
        (tmp_path / t).mkdir(parents=True, exist_ok=True)
        (tmp_path / t / "600000.csv").write_text("h\n", encoding="utf-8")
    # 300001: 仅 BS
    (tmp_path / "balance_sheet" / "300001.csv").write_text("h\n", encoding="utf-8")
    # 688001: 无

    result = check_completeness(sample, str(tmp_path))
    assert result["total_stocks"] == 3
    assert result["stocks_with_data"] == 2  # 600000, 300001
    assert result["complete_stocks"] == 1  # 600000
    assert result["coverage_rate"] == 2 / 3
    assert result["completeness_rate"] == 1 / 3


def test_check_completeness_per_board(tmp_path):
    """分板块统计。"""
    sample = {
        "boards": {
            "sh_main": ["600000", "600001"],
            "chinext": ["300001"],
        }
    }
    for t in ("balance_sheet", "income_statement", "cash_flow"):
        (tmp_path / t).mkdir(parents=True, exist_ok=True)
    # sh_main: 600000 全有，600001 无
    for t in ("balance_sheet", "income_statement", "cash_flow"):
        (tmp_path / t / "600000.csv").write_text("h\n", encoding="utf-8")
    # chinext: 300001 仅 BS
    (tmp_path / "balance_sheet" / "300001.csv").write_text("h\n", encoding="utf-8")

    result = check_completeness(sample, str(tmp_path))
    assert result["per_board"]["sh_main"] == {"total": 2, "complete": 1, "with_data": 1}
    assert result["per_board"]["chinext"] == {"total": 1, "complete": 0, "with_data": 1}


def test_check_completeness_per_statement(tmp_path):
    """分表统计。"""
    sample = {"all_codes": ["600000"]}
    (tmp_path / "balance_sheet").mkdir(parents=True, exist_ok=True)
    (tmp_path / "balance_sheet" / "600000.csv").write_text("h\n", encoding="utf-8")
    # income_statement 和 cash_flow 缺失

    result = check_completeness(sample, str(tmp_path))
    assert result["per_statement"]["balance_sheet"] == 1
    assert result["per_statement"]["income_statement"] == 0
    assert result["per_statement"]["cash_flow"] == 0
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
python -m pytest tests/eval_em/test_parse.py::test_check_completeness_full -v
```
预期：FAIL with `ImportError`。

- [ ] **Step 3: 实现 `check_completeness`**

追加到 `scripts/eval_em_lib.py`：

```python
def check_completeness(sample: dict, output_root: str) -> dict:
    """Check download completeness for the sample.

    Args:
        sample: dict with 'all_codes' (and optionally 'boards').
        output_root: directory containing balance_sheet/, income_statement/, cash_flow/.

    Returns:
        {
          "total_stocks": int,
          "stocks_with_data": int,    # 至少有一张表
          "complete_stocks": int,     # 3 张表齐全
          "coverage_rate": float,     # with_data / total
          "completeness_rate": float, # complete / total
          "per_board": {board: {total, complete, with_data}},
          "per_statement": {stmt: count}
        }
    """
    STATEMENTS = ("balance_sheet", "income_statement", "cash_flow")
    all_codes = sample.get("all_codes", [])
    if "boards" in sample:
        boards = sample["boards"]
    else:
        boards = {"all": all_codes}

    total = len(all_codes)
    stocks_with_data = 0
    complete_stocks = 0
    per_board = {b: {"total": len(codes), "complete": 0, "with_data": 0} for b, codes in boards.items()}
    per_statement = {s: 0 for s in STATEMENTS}

    for code in all_codes:
        has_data = False
        all_three = True
        for stmt in STATEMENTS:
            csv_path = os.path.join(output_root, stmt, f"{code}.csv")
            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                has_data = True
                per_statement[stmt] += 1
            else:
                all_three = False
        if has_data:
            stocks_with_data += 1
        if all_three:
            complete_stocks += 1

    # Per-board aggregation
    for board, codes in boards.items():
        for code in codes:
            has_data = False
            all_three = True
            for stmt in STATEMENTS:
                csv_path = os.path.join(output_root, stmt, f"{code}.csv")
                if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                    has_data = True
                else:
                    all_three = False
            if has_data:
                per_board[board]["with_data"] += 1
            if all_three:
                per_board[board]["complete"] += 1

    return {
        "total_stocks": total,
        "stocks_with_data": stocks_with_data,
        "complete_stocks": complete_stocks,
        "coverage_rate": stocks_with_data / total if total else 0,
        "completeness_rate": complete_stocks / total if total else 0,
        "per_board": per_board,
        "per_statement": per_statement,
    }
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
python -m pytest tests/eval_em/test_parse.py -v -k "completeness"
```
预期：4 个 completeness 测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_parse.py
git commit -m "feat(eval_em): add completeness checker with per-board/per-statement breakdown"
```

---

### Task 3.2：完整性 CLI 入口

**Files:**
- Create: `scripts/eval_em_completeness.py`

- [ ] **Step 1: 实现 CLI**

写入 `scripts/eval_em_completeness.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M3: Check download completeness for the 200-stock sample.

Usage:
    python scripts/eval_em_completeness.py

Output:
    data/exports_v2/em_evaluation/completeness.json
"""
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import check_completeness  # noqa: E402

BASE = _PROJECT_ROOT
SAMPLE_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "completeness.json")


def main() -> int:
    if not os.path.exists(SAMPLE_PATH):
        print(f"ERROR: Sample not found: {SAMPLE_PATH}")
        return 1

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)

    result = check_completeness(sample, OUTPUT_ROOT)

    # Print summary
    print(f"\n=== 完整性检查报告 ===")
    print(f"总样本: {result['total_stocks']} 只")
    print(f"有数据: {result['stocks_with_data']} 只 ({result['coverage_rate'] * 100:.1f}%)")
    print(f"完整 (3表齐全): {result['complete_stocks']} 只 ({result['completeness_rate'] * 100:.1f}%)")
    print()
    print("分板块:")
    for board, stats in result["per_board"].items():
        print(f"  {board:10s}: total={stats['total']:3d}  with_data={stats['with_data']:3d}  complete={stats['complete']:3d}")
    print()
    print("分表:")
    for stmt, count in result["per_statement"].items():
        print(f"  {stmt:20s}: {count:3d} 只")

    # Save
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行并验证**

```bash
python scripts/eval_em_completeness.py
```
预期：输出覆盖率和完整率。

- [ ] **Step 3: 提交**

```bash
git add scripts/eval_em_completeness.py
git commit -m "feat(eval_em): add completeness CLI"
```

---

## Phase 4：EM vs RDS 比对（M4）

### Task 4.1：值比对函数（TDD）

**Files:**
- Modify: `scripts/eval_em_lib.py`
- Modify: `tests/eval_em/test_compare.py`

- [ ] **Step 1: 创建测试文件**

写入 `tests/eval_em/test_compare.py`：

```python
"""Tests for EM vs RDS comparison logic."""
import pytest

from scripts.eval_em_lib import (
    compare_values,
    TOLERANCE_YUAN,
    PERFECT_TOLERANCE_YUAN,
    align_em_rds,
    compare_em_rds_one_stock,
)


# ---- Tolerance constants ----

def test_tolerance_constants():
    """1元容差必须与项目分精度规则一致。"""
    assert TOLERANCE_YUAN == 1.0
    assert PERFECT_TOLERANCE_YUAN == 0.01


# ---- compare_values ----

def test_compare_values_within_tolerance():
    """差值 ≤ 1.00 元 = match。"""
    severity, diff = compare_values(100.0, 100.5)
    assert severity == "good"
    assert diff == 0.5


def test_compare_values_perfect():
    """差值 ≤ 0.01 元 = perfect。"""
    severity, diff = compare_values(100.0, 100.0)
    assert severity == "perfect"
    assert diff == 0.0


def test_compare_values_exceeds_tolerance():
    """差值 > 1.00 元 = anomaly。"""
    severity, diff = compare_values(100.0, 102.0)
    assert severity == "anomaly"
    assert diff == 2.0


def test_compare_values_negative_diff():
    """绝对值差，无视正负。"""
    severity, diff = compare_values(100.0, 99.0)
    assert severity == "good"
    assert diff == 1.0


# ---- align_em_rds ----

def test_align_em_rds_by_field_name():
    """EM 和 RDS 都用 field_name 作为 key 对齐。"""
    em = {"货币资金": 100.0, "应收账款": 50.0, "EM独有字段": 30.0}
    rds = {"货币资金": 100.5, "应收账款": 60.0, "RDS独有字段": 20.0}
    aligned = align_em_rds(em, rds)
    assert set(aligned.keys()) == {"货币资金", "应收账款"}
    assert aligned["货币资金"]["em"] == 100.0
    assert aligned["货币资金"]["rds"] == 100.5


# ---- compare_em_rds_one_stock ----

def test_compare_em_rds_full_match():
    em = {"货币资金": 100.0, "应收账款": 50.0}
    rds = {"货币资金": 100.0, "应收账款": 50.0, "RDS独有": 200.0}
    result = compare_em_rds_one_stock(em, rds, "balance_sheet", "600000", 2022, "annual")
    assert result["matched"] == 2
    assert result["unmatched"] == 0
    assert result["missing_in_em"] == 1
    assert result["match_rate"] == 1.0


def test_compare_em_rds_partial_match():
    em = {"货币资金": 100.0, "应收账款": 50.0}
    rds = {"货币资金": 100.0, "应收账款": 100.0}  # 应收账款差 50 元
    result = compare_em_rds_one_stock(em, rds, "balance_sheet", "600000", 2022, "annual")
    assert result["matched"] == 1  # 仅货币资金
    assert result["unmatched"] == 1
    assert result["match_rate"] == 0.5
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
python -m pytest tests/eval_em/test_compare.py -v
```
预期：FAIL with `ImportError`。

- [ ] **Step 3: 实现比对函数**

追加到 `scripts/eval_em_lib.py`：

```python
# ----- EM vs RDS 比对 -----

TOLERANCE_YUAN = 1.0       # 1 元 = 匹配
PERFECT_TOLERANCE_YUAN = 0.01  # 0.01 元 = 完美（精确到分）


def compare_values(em_val: float, rds_val: float) -> Tuple[str, float]:
    """Compare two values using 1元 absolute tolerance.

    Returns:
        (severity, abs_diff)
        severity in {'perfect', 'good', 'anomaly'}
    """
    diff = abs(float(em_val) - float(rds_val))
    if diff <= PERFECT_TOLERANCE_YUAN:
        severity = "perfect"
    elif diff <= TOLERANCE_YUAN:
        severity = "good"
    else:
        severity = "anomaly"
    return severity, diff


def align_em_rds(em_data: dict, rds_data: dict) -> dict:
    """Align EM and RDS data by field_name (intersection).

    Returns:
        {field_name: {"em": float, "rds": float}}
    """
    common = set(em_data.keys()) & set(rds_data.keys())
    return {
        f: {"em": em_data[f], "rds": rds_data[f]}
        for f in common
    }


def compare_em_rds_one_stock(
    em_data: dict,
    rds_data: dict,
    statement_type: str,
    stock_code: str,
    year: int,
    period: str,
) -> dict:
    """Compare EM data against RDS for one stock/period.

    Returns:
        {
            "stock_code": str, "year": int, "period": str, "statement_type": str,
            "total_fields_em": int,
            "total_fields_rds": int,
            "common_fields": int,
            "matched": int,        # 差值 ≤ 1 元
            "unmatched": int,      # 差值 > 1 元
            "missing_in_em": int,  # RDS 有但 EM 没有
            "extra_in_em": int,    # EM 有但 RDS 没有
            "match_rate": float,   # matched / common_fields
            "value_accuracy": float,
            "field_coverage": float,  # common_fields / rds_fields
            "anomalies": [{field, em, rds, diff}],
        }
    """
    common = set(em_data.keys()) & set(rds_data.keys())
    aligned = align_em_rds(em_data, rds_data)

    matched = 0
    anomalies = []
    for field, vals in aligned.items():
        severity, diff = compare_values(vals["em"], vals["rds"])
        if severity in ("perfect", "good"):
            matched += 1
        else:
            anomalies.append({
                "field": field,
                "em": vals["em"],
                "rds": vals["rds"],
                "diff": diff,
            })

    total_common = len(common)
    total_em = len(em_data)
    total_rds = len(rds_data)
    missing_in_em = len(set(rds_data.keys()) - set(em_data.keys()))
    extra_in_em = len(set(em_data.keys()) - set(rds_data.keys()))

    return {
        "stock_code": stock_code,
        "year": year,
        "period": period,
        "statement_type": statement_type,
        "total_fields_em": total_em,
        "total_fields_rds": total_rds,
        "common_fields": total_common,
        "matched": matched,
        "unmatched": len(anomalies),
        "missing_in_em": missing_in_em,
        "extra_in_em": extra_in_em,
        "match_rate": matched / total_common if total_common else 0,
        "value_accuracy": matched / total_common if total_common else 0,
        "field_coverage": total_common / total_rds if total_rds else 0,
        "anomalies": anomalies,
    }
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
python -m pytest tests/eval_em/test_compare.py -v
```
预期：所有 test PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_compare.py
git commit -m "feat(eval_em): add value comparison with 1元 tolerance"
```

---

### Task 4.2：EM vs RDS 集成比对

**Files:**
- Modify: `scripts/eval_em_lib.py`

- [ ] **Step 1: 实现 `compare_em_rds_batch`**

追加到 `scripts/eval_em_lib.py`：

```python
def load_em_tidy(stock_code: str, statement_type: str, year: int, period: str, output_root: str) -> dict:
    """Load EM tidy CSV and pivot to {field_name: value}."""
    import pandas as pd
    path = os.path.join(output_root, statement_type, f"{stock_code}.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_code": str})
    df = df[(df["year"] == year) & (df["period"] == period)]
    return dict(zip(df["field_name"], df["value"]))


def compare_em_rds_batch(
    sample: dict,
    rds_loader,
    output_root: str,
    year: int = 2022,
    periods: Tuple[str, ...] = ("Q1", "half_year", "Q3", "annual"),
) -> dict:
    """Batch compare EM vs RDS for sample stocks across all periods and statements.

    Args:
        sample: dict with 'all_codes' and 'boards'.
        rds_loader: RdsLoader instance.
        output_root: EM data root.
        year: target year.
        periods: tuple of periods to compare.

    Returns:
        {
            "summary": {total_comparisons, total_matched, total_unmatched, ...},
            "per_stock": [compare_em_rds_one_stock result],
            "per_statement": {stmt: stats},
            "per_board": {board: stats},
        }
    """
    STATEMENTS = ("balance_sheet", "income_statement", "cash_flow")
    all_results = []
    per_statement = {s: {"matched": 0, "unmatched": 0, "common": 0} for s in STATEMENTS}
    per_board = {}

    # Initialize per-board
    for board, codes in sample.get("boards", {}).items():
        per_board[board] = {"matched": 0, "unmatched": 0, "common": 0, "stocks": 0}

    for stock_code in sample["all_codes"]:
        for stmt_type in STATEMENTS:
            for period in periods:
                em_data = load_em_tidy(stock_code, stmt_type, year, period, output_root)
                if not em_data:
                    continue  # No EM data, skip
                rds_data = rds_loader.load_stock_data(stock_code, year, stmt_type)
                # RDS loader may return data for a specific period; assume it has all fields
                # If period-specific, we'd need to filter. For now, use as-is.
                if not rds_data:
                    continue  # No RDS data
                # RDS data may be period-agnostic; we compare as-is
                result = compare_em_rds_one_stock(
                    em_data, rds_data, stmt_type, stock_code, year, period,
                )
                all_results.append(result)
                per_statement[stmt_type]["matched"] += result["matched"]
                per_statement[stmt_type]["unmatched"] += result["unmatched"]
                per_statement[stmt_type]["common"] += result["common_fields"]

    # Per-board aggregation
    for stock_code in sample["all_codes"]:
        # Find which board
        board = "unknown"
        for b, codes in sample.get("boards", {}).items():
            if stock_code in codes:
                board = b
                break
        for r in all_results:
            if r["stock_code"] == stock_code:
                per_board[board]["matched"] += r["matched"]
                per_board[board]["unmatched"] += r["unmatched"]
                per_board[board]["common"] += r["common_fields"]
                per_board[board]["stocks"] += 1
                break  # Count stock once

    # Compute aggregate stats
    total_matched = sum(per_statement[s]["matched"] for s in STATEMENTS)
    total_unmatched = sum(per_statement[s]["unmatched"] for s in STATEMENTS)
    total_common = sum(per_statement[s]["common"] for s in STATEMENTS)
    total_comparisons = len(all_results)

    return {
        "summary": {
            "total_comparisons": total_comparisons,
            "total_matched": total_matched,
            "total_unmatched": total_unmatched,
            "total_common_fields": total_common,
            "overall_match_rate": total_matched / total_common if total_common else 0,
        },
        "per_statement": per_statement,
        "per_board": per_board,
        "per_stock": all_results,
    }
```

- [ ] **Step 2: 提交**

```bash
git add scripts/eval_em_lib.py
git commit -m "feat(eval_em): add batch comparison with RdsLoader integration"
```

---

### Task 4.3：EM vs RDS 比对 CLI

**Files:**
- Create: `scripts/eval_em_compare_rds.py`

- [ ] **Step 1: 实现 CLI**

写入 `scripts/eval_em_compare_rds.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M4: Compare EM data against RDS ground truth for 200 stocks × 4 periods × 3 statements.

Usage:
    python scripts/eval_em_compare_rds.py

Output:
    data/exports_v2/em_evaluation/compare_rds_report.json
"""
import json
import os
import sys
from collections import Counter

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import compare_em_rds_batch  # noqa: E402

# Import RdsLoader
sys.path.insert(0, _PROJECT_ROOT)
from astock_fundamentals.sources.rds.rds_loader import RdsLoader  # noqa: E402

BASE = _PROJECT_ROOT
SAMPLE_PATH = os.path.join(BASE, "data", "exports_v2", "em_evaluation", "sample_200.json")
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "compare_rds_report.json")


def main() -> int:
    if not os.path.exists(SAMPLE_PATH):
        print(f"ERROR: Sample not found: {SAMPLE_PATH}")
        return 1

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)

    print("Loading RDS data...")
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    print(f"  Loaded RDS from {RDS_DIR}")

    print(f"Comparing {len(sample['all_codes'])} stocks × 4 periods × 3 statements...")
    result = compare_em_rds_batch(sample, rds, OUTPUT_ROOT, year=2022)

    # Print summary
    s = result["summary"]
    print(f"\n=== EM vs RDS 比对报告 ===")
    print(f"总比对数: {s['total_comparisons']} (股票×期次×报表)")
    print(f"匹配字段: {s['total_matched']}/{s['total_common_fields']} ({s['overall_match_rate'] * 100:.2f}%)")
    print()
    print("分表:")
    for stmt, stats in result["per_statement"].items():
        rate = stats["matched"] / stats["common"] * 100 if stats["common"] else 0
        print(f"  {stmt:20s}: {stats['matched']:5d}/{stats['common']:5d} ({rate:.1f}%)")
    print()
    print("分板块:")
    for board, stats in result["per_board"].items():
        rate = stats["matched"] / stats["common"] * 100 if stats["common"] else 0
        print(f"  {board:10s}: {stats['matched']:5d}/{stats['common']:5d} ({rate:.1f}%)  ({stats['stocks']} stocks)")

    # Top anomalies
    print("\n最大差异对 Top 10:")
    all_anomalies = []
    for r in result["per_stock"]:
        for a in r["anomalies"]:
            all_anomalies.append((a["diff"], r["stock_code"], r["statement_type"], r["period"], a))
    all_anomalies.sort(reverse=True)
    for diff, stock, stmt, period, a in all_anomalies[:10]:
        print(f"  {stock}/{stmt}/{period} {a['field']}: EM={a['em']:.2f} RDS={a['rds']:.2f} 差={diff:.2f}元")

    # Save
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行比对**

```bash
python scripts/eval_em_compare_rds.py
```
预期：输出匹配率和分表/分板块统计。

- [ ] **Step 3: 提交**

```bash
git add scripts/eval_em_compare_rds.py
git commit -m "feat(eval_em): add EM vs RDS comparison CLI"
```

---

## Phase 5：历史疑难数据 EM 重测（M5）

### Task 5.1：Sina 差异扫描器（TDD）

**Files:**
- Modify: `scripts/eval_em_lib.py`
- Modify: `tests/eval_em/test_historical.py`

- [ ] **Step 1: 创建测试文件**

写入 `tests/eval_em/test_historical.py`：

```python
"""Tests for historical sina vs RDS scanner."""
import os
import pandas as pd
import pytest

from scripts.eval_em_lib import scan_sina_anomalies


def test_scan_sina_anomalies_finds_diff(tmp_path):
    """差值 > 1 元的字段应被标记为异常。"""
    sina_csv = tmp_path / "sina.csv"
    df = pd.DataFrame({
        "stock_code": ["600000", "600000", "600001"],
        "year": [2022, 2022, 2022],
        "period": ["annual", "annual", "annual"],
        "statement_type": ["balance_sheet", "balance_sheet", "balance_sheet"],
        "field_name": ["货币资金", "应收账款", "货币资金"],
        "value": [100.0, 50.5, 100.0],
    })
    df.to_csv(sina_csv, index=False, encoding="utf-8-sig")

    # RDS: 600000 货币资金 100.0, 应收账款 50.5 (匹配)
    #      600000 应收账款 100.0 (差 49.5) -- but 600000 货币资金/应收账款 已在 df 中
    # We need 600001 to have RDS 100.0 (匹配)
    # And 600000 应收账款 在 RDS 中是 100.0 (差 49.5)
    rds_data_map = {
        ("600000", 2022, "balance_sheet"): {"货币资金": 100.0, "应收账款": 100.0},  # 应收账款差 49.5
        ("600001", 2022, "balance_sheet"): {"货币资金": 100.0},  # 匹配
    }

    def fake_rds_loader(code, year, stmt):
        return rds_data_map.get((code, year, stmt), {})

    anomalies = scan_sina_anomalies(str(sina_csv), fake_rds_loader, tolerance=1.0)

    # 600000/应收账款 应是异常（差 49.5）
    assert len(anomalies) == 1
    assert anomalies[0]["stock_code"] == "600000"
    assert anomalies[0]["field_name"] == "应收账款"
    assert abs(anomalies[0]["diff"] - 49.5) < 0.01


def test_scan_sina_anomalies_no_diff(tmp_path):
    """全部匹配 → 0 异常。"""
    sina_csv = tmp_path / "sina.csv"
    df = pd.DataFrame({
        "stock_code": ["600000"],
        "year": [2022],
        "period": ["annual"],
        "statement_type": ["balance_sheet"],
        "field_name": ["货币资金"],
        "value": [100.0],
    })
    df.to_csv(sina_csv, index=False, encoding="utf-8-sig")

    def fake_rds_loader(code, year, stmt):
        return {"货币资金": 100.0}

    anomalies = scan_sina_anomalies(str(sina_csv), fake_rds_loader, tolerance=1.0)
    assert len(anomalies) == 0


def test_scan_sina_anomalies_tolerance(tmp_path):
    """差值 0.5 元（≤ 1元）→ 不算异常。"""
    sina_csv = tmp_path / "sina.csv"
    df = pd.DataFrame({
        "stock_code": ["600000"],
        "year": [2022],
        "period": ["annual"],
        "statement_type": ["balance_sheet"],
        "field_name": ["货币资金"],
        "value": [100.5],
    })
    df.to_csv(sina_csv, index=False, encoding="utf-8-sig")

    def fake_rds_loader(code, year, stmt):
        return {"货币资金": 100.0}

    anomalies = scan_sina_anomalies(str(sina_csv), fake_rds_loader, tolerance=1.0)
    assert len(anomalies) == 0
```

- [ ] **Step 2: 运行测试，验证失败**

```bash
python -m pytest tests/eval_em/test_historical.py -v
```
预期：FAIL with `ImportError`。

- [ ] **Step 3: 实现 `scan_sina_anomalies`**

追加到 `scripts/eval_em_lib.py`：

```python
def scan_sina_anomalies(
    sina_csv_path: str,
    rds_loader_callable,
    tolerance: float = 1.0,
) -> list:
    """Scan sina cleaned CSV and find fields where |sina - rds| > tolerance.

    Args:
        sina_csv_path: path to sina_cleaned_*.csv.
        rds_loader_callable: function (code, year, stmt) -> {field_name: value}.
        tolerance: max allowed absolute diff (default 1.0).

    Returns:
        List of anomaly dicts:
            [{stock_code, year, period, statement_type, field_name, sina_val, rds_val, diff}]
    """
    if not os.path.exists(sina_csv_path):
        return []
    df = pd.read_csv(sina_csv_path, encoding="utf-8-sig", dtype={"stock_code": str})
    required = {"stock_code", "year", "period", "statement_type", "field_name", "value"}
    if not required.issubset(df.columns):
        return []

    anomalies = []
    # Cache RDS data per (code, year, stmt) to avoid repeated calls
    rds_cache: Dict[Tuple, dict] = {}

    for _, row in df.iterrows():
        code = str(row["stock_code"]).zfill(6)
        year = int(row["year"])
        stmt = row["statement_type"]
        field = row["field_name"]
        sina_val = float(row["value"])

        key = (code, year, stmt)
        if key not in rds_cache:
            try:
                rds_cache[key] = rds_loader_callable(code, year, stmt) or {}
            except Exception:
                rds_cache[key] = {}

        rds_data = rds_cache[key]
        if field not in rds_data:
            continue

        rds_val = float(rds_data[field])
        diff = abs(sina_val - rds_val)
        if diff > tolerance:
            anomalies.append({
                "stock_code": code,
                "year": year,
                "period": row["period"],
                "statement_type": stmt,
                "field_name": field,
                "sina_val": sina_val,
                "rds_val": rds_val,
                "diff": diff,
            })

    return anomalies
```

- [ ] **Step 4: 运行测试，验证通过**

```bash
python -m pytest tests/eval_em/test_historical.py -v
```
预期：3 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_historical.py
git commit -m "feat(eval_em): add sina vs RDS anomaly scanner"
```

---

### Task 5.2：EM 重测逻辑

**Files:**
- Modify: `scripts/eval_em_lib.py`

- [ ] **Step 1: 实现 `recheck_with_em`**

追加到 `scripts/eval_em_lib.py`：

```python
def recheck_with_em(anomalies: list, output_root: str, tolerance: float = 1.0) -> dict:
    """Re-check historical anomalies using EM data.

    For each sina anomaly, look up the EM value for the same (code, year, period, stmt, field)
    and compare against RDS.

    Returns:
        {
            "anomalies_count": int,
            "em_matched": int,        # EM 匹配 RDS 的数量
            "em_unmatched": int,      # EM 仍不匹配 RDS
            "em_no_data": int,        # EM 没有该字段
            "match_rate": float,      # em_matched / anomalies_count
            "improvement": float,     # (em_matched - sina_matched=0) / anomalies_count
            "details": [{..., "em_val": float|None, "em_severity": str}],
        }
    """
    STATEMENT_TO_FETCH = {
        "balance_sheet": fetch_em_balance_sheet,
        "income_statement": fetch_em_income_statement,
        "cash_flow": fetch_em_cash_flow,
    }

    details = []
    em_matched = 0
    em_unmatched = 0
    em_no_data = 0

    for anom in anomalies:
        code = anom["stock_code"]
        year = anom["year"]
        period = anom["period"]
        stmt = anom["statement_type"]
        field = anom["field_name"]

        # Load EM tidy for this (code, stmt, year, period)
        em_data = load_em_tidy(code, stmt, year, period, output_root)
        em_val = em_data.get(field)

        if em_val is None:
            em_severity = "no_data"
            em_no_data += 1
        else:
            em_severity, em_diff = compare_values(em_val, anom["rds_val"])
            if em_severity in ("perfect", "good"):
                em_matched += 1
            else:
                em_unmatched += 1

        details.append({
            **anom,
            "em_val": em_val,
            "em_severity": em_severity,
        })

    total = len(anomalies)
    return {
        "anomalies_count": total,
        "em_matched": em_matched,
        "em_unmatched": em_unmatched,
        "em_no_data": em_no_data,
        "match_rate": em_matched / total if total else 0,
        # Sina matched 0 (all are anomalies), so improvement = em_match_rate
        "improvement": em_matched / total if total else 0,
        "details": details,
    }
```

- [ ] **Step 2: 提交**

```bash
git add scripts/eval_em_lib.py
git commit -m "feat(eval_em): add EM recheck for historical anomalies"
```

---

### Task 5.3：历史数据 EM 重测 CLI

**Files:**
- Create: `scripts/eval_em_historical.py`

- [ ] **Step 1: 实现 CLI**

写入 `scripts/eval_em_historical.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M5: Re-test historical sina anomalies with EM data.

Scans sina_cleaned_*.csv for |sina - rds| > 1元 fields, then checks if EM matches RDS.

Usage:
    python scripts/eval_em_historical.py

Output:
    data/exports_v2/em_evaluation/historical_issues.json
"""
import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import scan_sina_anomalies, recheck_with_em  # noqa: E402

sys.path.insert(0, _PROJECT_ROOT)
from astock_fundamentals.sources.rds.rds_loader import RdsLoader  # noqa: E402

BASE = _PROJECT_ROOT
SINA_CSVS = [
    os.path.join(BASE, "data", "exports_v2", "sina_cleaned_balance_sheet.csv"),
    os.path.join(BASE, "data", "exports_v2", "sina_cleaned_income_statement.csv"),
    os.path.join(BASE, "data", "exports_v2", "sina_cleaned_cash_flow.csv"),
]
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
DECODE_PATH = os.path.join(BASE, "data", "decode_mappings_by_type.json")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "historical_issues.json")


def main() -> int:
    rds = RdsLoader(RDS_DIR, decode_map_path=DECODE_PATH)
    def rds_callable(code, year, stmt):
        return rds.load_stock_data(code, year, stmt) or {}

    all_anomalies = []
    for csv_path in SINA_CSVS:
        if not os.path.exists(csv_path):
            print(f"  WARN: {csv_path} not found, skipping")
            continue
        print(f"Scanning {csv_path}...")
        anomalies = scan_sina_anomalies(csv_path, rds_callable, tolerance=1.0)
        print(f"  Found {len(anomalies)} anomalies")
        all_anomalies.extend(anomalies)

    print(f"\nTotal anomalies: {len(all_anomalies)}")

    if not all_anomalies:
        print("No anomalies to recheck.")
        result = {
            "anomalies_count": 0,
            "em_matched": 0,
            "em_unmatched": 0,
            "em_no_data": 0,
            "match_rate": 0,
            "improvement": 0,
            "details": [],
        }
    else:
        print("Re-checking with EM data...")
        result = recheck_with_em(all_anomalies, OUTPUT_ROOT, tolerance=1.0)

    # Print summary
    print(f"\n=== 历史疑难数据 EM 重测 ===")
    print(f"疑难样本数: {result['anomalies_count']}")
    print(f"EM 匹配数: {result['em_matched']}")
    print(f"EM 仍不匹配: {result['em_unmatched']}")
    print(f"EM 无数据: {result['em_no_data']}")
    print(f"EM 匹配率: {result['match_rate'] * 100:.2f}%")
    print(f"EM 改善率 (vs sina 0%): {result['improvement'] * 100:.2f}%")

    # Save
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行并验证**

```bash
python scripts/eval_em_historical.py
```
预期：输出 sina 异常数和 EM 改善率。

- [ ] **Step 3: 提交**

```bash
git add scripts/eval_em_historical.py
git commit -m "feat(eval_em): add historical anomalies recheck CLI"
```

---

## Phase 6：报告生成（M6）

### Task 6.1：报告聚合器

**Files:**
- Modify: `scripts/eval_em_lib.py`
- Modify: `tests/eval_em/test_compare.py`（追加）

- [ ] **Step 1: 追加测试**

追加到 `tests/eval_em/test_compare.py`：

```python
from scripts.eval_em_lib import build_conclusion


def test_build_conclusion_recommend_main(tmp_path):
    """coverage > 95%, match_rate > 95% → recommend main。"""
    completeness = {
        "total_stocks": 200, "stocks_with_data": 198, "complete_stocks": 195,
        "coverage_rate": 0.99, "completeness_rate": 0.975,
    }
    compare = {
        "summary": {"total_matched": 9500, "total_common_fields": 10000, "overall_match_rate": 0.95}
    }
    historical = {"anomalies_count": 100, "em_matched": 80, "match_rate": 0.8}

    conclusion = build_conclusion(completeness, compare, historical)
    assert conclusion["recommendation"] == "main"
    assert "主力" in conclusion["text"] or "main" in conclusion["text"].lower()


def test_build_conclusion_recommend_assist(tmp_path):
    """中等 → assist。"""
    completeness = {
        "total_stocks": 200, "stocks_with_data": 150, "complete_stocks": 100,
        "coverage_rate": 0.75, "completeness_rate": 0.5,
    }
    compare = {
        "summary": {"total_matched": 7000, "total_common_fields": 10000, "overall_match_rate": 0.7}
    }
    historical = {"anomalies_count": 100, "em_matched": 50, "match_rate": 0.5}

    conclusion = build_conclusion(completeness, compare, historical)
    assert conclusion["recommendation"] in ("assist", "reject")
```

- [ ] **Step 2: 实现 `build_conclusion`**

追加到 `scripts/eval_em_lib.py`：

```python
def build_conclusion(completeness: dict, compare: dict, historical: dict) -> dict:
    """Build final recommendation based on metrics.

    Decision rules:
    - coverage_rate >= 0.95 AND match_rate >= 0.95 → 'main' (主力)
    - coverage_rate >= 0.7 AND match_rate >= 0.7  → 'assist' (辅助)
    - else → 'reject' (不建议)
    """
    cov = completeness.get("coverage_rate", 0)
    match = compare.get("summary", {}).get("overall_match_rate", 0)
    improve = historical.get("match_rate", 0)

    if cov >= 0.95 and match >= 0.95:
        rec = "main"
        text = "EM 渠道可作为主力数据来源"
    elif cov >= 0.7 and match >= 0.7:
        rec = "assist"
        text = "EM 渠道建议作为辅助渠道"
    else:
        rec = "reject"
        text = "EM 渠道不建议使用"

    return {
        "recommendation": rec,
        "text": text,
        "coverage_rate": cov,
        "match_rate": match,
        "improvement_rate": improve,
    }
```

- [ ] **Step 3: 运行测试，验证通过**

```bash
python -m pytest tests/eval_em/test_compare.py::test_build_conclusion_recommend_main tests/eval_em/test_compare.py::test_build_conclusion_recommend_assist -v
```
预期：2 个测试 PASS。

- [ ] **Step 4: 提交**

```bash
git add scripts/eval_em_lib.py tests/eval_em/test_compare.py
git commit -m "feat(eval_em): add conclusion builder with 3-tier recommendation"
```

---

### Task 6.2：报告生成 CLI

**Files:**
- Create: `scripts/eval_em_report.py`

- [ ] **Step 1: 实现 CLI**

写入 `scripts/eval_em_report.py`：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M6: Aggregate all evaluation outputs into a structured Markdown report.

Usage:
    python scripts/eval_em_report.py

Output:
    docs/audit/2026-06-10-em-channel-evaluation.md
"""
import json
import os
import sys
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.eval_em_lib import build_conclusion  # noqa: E402

BASE = _PROJECT_ROOT
OUTPUT_ROOT = os.path.join(BASE, "data", "exports_v2", "em_evaluation")
SAMPLE_PATH = os.path.join(OUTPUT_ROOT, "sample_200.json")
COMPLETE_PATH = os.path.join(OUTPUT_ROOT, "completeness.json")
COMPARE_PATH = os.path.join(OUTPUT_ROOT, "compare_rds_report.json")
HISTORICAL_PATH = os.path.join(OUTPUT_ROOT, "historical_issues.json")
REPORT_PATH = os.path.join(BASE, "docs", "audit", "2026-06-10-em-channel-evaluation.md")


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_report(sample: dict, completeness: dict, compare: dict, historical: dict) -> str:
    """Render the final Markdown report."""
    conclusion = build_conclusion(completeness, compare, historical)
    cov = completeness.get("coverage_rate", 0)
    comp_rate = completeness.get("completeness_rate", 0)
    s = compare.get("summary", {})
    overall_match = s.get("overall_match_rate", 0)
    total_matched = s.get("total_matched", 0)
    total_common = s.get("total_common_fields", 0)
    h = historical

    # Per-board table
    per_board_rows = []
    for board, stats in completeness.get("per_board", {}).items():
        per_board_rows.append(
            f"| {board} | {stats['total']} | {stats['with_data']} | {stats['complete']} |"
        )
    per_board_table = "\n".join(per_board_rows) if per_board_rows else "| (无) | - | - | - |"

    # Per-statement table
    per_stmt_rows = []
    for stmt, stats in compare.get("per_statement", {}).items():
        rate = stats["matched"] / stats["common"] * 100 if stats["common"] else 0
        per_stmt_rows.append(
            f"| {stmt} | {stats['matched']} | {stats['common']} | {rate:.2f}% |"
        )
    per_stmt_table = "\n".join(per_stmt_rows) if per_stmt_rows else "| (无) | - | - | - |"

    md = f"""# EM 渠道全面评估结论

**日期**: {datetime.now().strftime('%Y-%m-%d')}
**评估范围**: akshare-EM（东方财富）渠道对 A 股 2022 年 Q1/半年报/Q3/年报 × 资产负债表/利润表/现金流量表

## 1. 抽样覆盖性

- **总样本**: 200 只（沪市主板 {len(sample.get('boards', {}).get('sh_main', []))} / 深市主板 {len(sample.get('boards', {}).get('sz_main', []))} / 创业板 {len(sample.get('boards', {}).get('chinext', []))} / 科创板 {len(sample.get('boards', {}).get('star', []))}）
- **覆盖率**: {completeness.get('stocks_with_data', 0)}/200 = **{cov * 100:.2f}%**
- **完整率**: {completeness.get('complete_stocks', 0)}/200 = **{comp_rate * 100:.2f}%**

### 分板块

| 板块 | 总数 | 有数据 | 三表齐全 |
|------|------|--------|----------|
{per_board_table}

### 分表

| 报表 | 有数据的股票数 |
|------|----------------|
"""
    for stmt, count in completeness.get("per_statement", {}).items():
        md += f"| {stmt} | {count} |\n"

    md += f"""
## 2. 数据质量（vs RDS）

- **比对样本数**: {s.get('total_comparisons', 0)} (股票×期次×报表)
- **字段匹配率**: {total_matched}/{total_common} = **{overall_match * 100:.2f}%**（差值 ≤ 1 元）

### 分表

| 报表 | 匹配字段 | 总字段 | 匹配率 |
|------|----------|--------|--------|
{per_stmt_table}

## 3. 历史疑难数据 EM 重测

- **疑难样本数**: {h.get('anomalies_count', 0)}（sina 与 RDS 差值 > 1 元的字段）
- **EM 匹配数**: {h.get('em_matched', 0)}
- **EM 仍不匹配**: {h.get('em_unmatched', 0)}
- **EM 无数据**: {h.get('em_no_data', 0)}
- **EM 改善率**: **{h.get('improvement', 0) * 100:.2f}%**（vs sina 0% 匹配）

## 4. 最终结论

**{conclusion['text']}**

| 指标 | 实际值 | 阈值（main） | 阈值（assist） |
|------|--------|---------------|-----------------|
| 覆盖率 | {cov * 100:.2f}% | ≥ 95% | ≥ 70% |
| 字段匹配率 | {overall_match * 100:.2f}% | ≥ 95% | ≥ 70% |
| EM 改善率 | {h.get('improvement', 0) * 100:.2f}% | - | - |

## 5. 建议

- 数据文件: `data/exports_v2/em_evaluation/`
- 比对报告: `data/exports_v2/em_evaluation/compare_rds_report.json`
- 疑难重测: `data/exports_v2/em_evaluation/historical_issues.json`

## 6. 已知局限

- EM 渠道**不提供间接法 CF**（与 sina 一致），间接法 CF 仍需从 PDF 年报提取或使用其他渠道
- 抽样固定 seed={sample.get('seed', 42)}，结果可重现但不一定是全市场最优代表
- 评估仅覆盖 2022 年，2023+ 数据未测试

---
*报告由 `scripts/eval_em_report.py` 自动生成*
"""
    return md


def main() -> int:
    sample = load_json(SAMPLE_PATH)
    completeness = load_json(COMPLETE_PATH)
    compare = load_json(COMPARE_PATH)
    historical = load_json(HISTORICAL_PATH)

    if not all([sample, completeness, compare, historical]):
        print("ERROR: Some input files missing. Run previous steps first.")
        print(f"  sample: {SAMPLE_PATH} -> exists={os.path.exists(SAMPLE_PATH)}")
        print(f"  completeness: {COMPLETE_PATH} -> exists={os.path.exists(COMPLETE_PATH)}")
        print(f"  compare: {COMPARE_PATH} -> exists={os.path.exists(COMPARE_PATH)}")
        print(f"  historical: {HISTORICAL_PATH} -> exists={os.path.exists(HISTORICAL_PATH)}")
        return 1

    md = render_report(sample, completeness, compare, historical)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 生成并查看报告**

```bash
python scripts/eval_em_report.py
echo "---"
head -60 docs/audit/2026-06-10-em-channel-evaluation.md
```

- [ ] **Step 3: 提交**

```bash
git add scripts/eval_em_report.py docs/audit/2026-06-10-em-channel-evaluation.md
git commit -m "feat(eval_em): add report generator CLI + final markdown report"
```

---

## Phase 7：端到端验收

### Task 7.1：完整流水线验收

**Files:** （无新文件；运行所有脚本）

- [ ] **Step 1: 全量测试**

```bash
python -m pytest tests/eval_em/ -v
```
预期：所有 test PASS。

- [ ] **Step 2: 验证产物清单**

```bash
echo "=== Scripts ==="
ls -la scripts/eval_em_*.py scripts/eval_em_lib.py
echo ""
echo "=== Outputs ==="
ls -la data/exports_v2/em_evaluation/*.json
ls data/exports_v2/em_evaluation/balance_sheet/ | wc -l
ls data/exports_v2/em_evaluation/income_statement/ | wc -l
ls data/exports_v2/em_evaluation/cash_flow/ | wc -l
echo ""
echo "=== Final Report ==="
ls -la docs/audit/2026-06-10-em-channel-evaluation.md
```

- [ ] **Step 3: 查看报告最终结论**

```bash
grep -A 5 "## 4. 最终结论" docs/audit/2026-06-10-em-channel-evaluation.md
```

- [ ] **Step 4: 最终提交**

```bash
git status
git add -A
git commit -m "docs(eval_em): complete EM channel evaluation pipeline" --allow-empty
```

---

## 完成定义

- [ ] `docs/audit/2026-06-10-em-channel-evaluation.md` 文件存在且包含 4 个核心指标
- [ ] 报告给出明确最终结论（main / assist / reject）
- [ ] 所有 7 个单元测试模块通过
- [ ] 6 个 CLI 脚本独立可运行
- [ ] `sample_200.json` 固定 seed=42 可重现
- [ ] 对生产代码 0 处修改
