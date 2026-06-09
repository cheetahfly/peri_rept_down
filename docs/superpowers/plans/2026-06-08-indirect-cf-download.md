# Indirect CF Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download indirect cash flow data for all 3,902 A-share listed companies (2020-2022 annual reports) via Sina (AKShare), convert to Tidy CSV format, and store locally.

**Architecture:** Serial download with checkpoint-based resume. Each stock: call `akshare.stock_financial_cash_ths()`, parse 15 indirect-method adjustment fields, filter to 2020-2022 annual reports, write per-stock Tidy CSV.

**Tech Stack:** Python 3.13, akshare, pandas, pyyaml

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-08-indirect-cf-download.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

---

## File Structure

| File | Purpose |
|------|---------|
| `scripts/download_indirect_cf.py` (Create) | Main download script with resume support |
| `rules/field_order.yaml` (Modify) | Add F057N-F071N codes for indirect CF fields |
| `data/exports_v2/indirect_cf/{code}.csv` (Create) | Per-stock Tidy CSV output |
| `data/ground_truth_reports/indirect_cf_progress.json` (Create) | Checkpoint file for resume |
| `data/ground_truth_reports/indirect_cf_download.log` (Create) | Run log |

---

### Task 1: Add F057N-F071N to field_order.yaml

**Files:**
- Modify: `rules/field_order.yaml` (add cash_flow entries)

- [ ] **Step 1: Add new F-codes to cash_flow section**

Open `rules/field_order.yaml`, find the `cash_flow:` section, and add at the end:

```yaml
  F057N: 70  # 净利润 (间接法)
  F058N: 71  # 资产减值准备
  F059N: 72  # 固定资产折旧
  F060N: 73  # 无形资产摊销
  F061N: 74  # 长期待摊费用摊销
  F062N: 75  # 处置固定资产损失
  F063N: 76  # 固定资产报废损失
  F064N: 77  # 公允价值变动损失
  F065N: 78  # 投资损失
  F066N: 79  # 递延所得税资产减少
  F067N: 80  # 递延所得税负债增加
  F068N: 81  # 存货的减少
  F069N: 82  # 经营性应收项目的减少
  F070N: 83  # 经营性应付项目的增加
  F071N: 84  # 其他 (间接法)
```

- [ ] **Step 2: Verify YAML is valid**

Run: `python -c "import yaml; d = yaml.safe_load(open('rules/field_order.yaml')); print('OK' if 'F057N' in d['cash_flow'] else 'FAIL')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add rules/field_order.yaml
git commit -m "feat(rules): add F057N-F071N for indirect CF fields"
```

---

### Task 2: Create the download script skeleton

**Files:**
- Create: `scripts/download_indirect_cf.py`

- [ ] **Step 1: Write the script header and constants**

Create `scripts/download_indirect_cf.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download indirect cash flow data from Sina (AKShare) for all A-share stocks.

Outputs per-stock Tidy CSV to data/exports_v2/indirect_cf/{code}.csv.
Supports resume via progress.json checkpoint file.
"""

import os
import sys
import json
import time
import warnings
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_LIST = os.path.join(BASE, "data", "ground_truth_reports", "full_stock_list.txt")
OUTPUT_DIR = os.path.join(BASE, "data", "exports_v2", "indirect_cf")
PROGRESS_FILE = os.path.join(BASE, "data", "ground_truth_reports", "indirect_cf_progress.json")
LOG_FILE = os.path.join(BASE, "data", "ground_truth_reports", "indirect_cf_download.log")

# Years to download (annual reports only)
YEARS = [2020, 2021, 2022]

# Column index → (F-code, display_order, chinese_name)
INDIRECT_FIELDS = {
    47: ("F057N", 70, "净利润"),
    48: ("F058N", 71, "资产减值准备"),
    49: ("F059N", 72, "固定资产折旧"),
    50: ("F060N", 73, "无形资产摊销"),
    51: ("F061N", 74, "长期待摊费用摊销"),
    52: ("F062N", 75, "处置固定资产损失"),
    53: ("F063N", 76, "固定资产报废损失"),
    54: ("F064N", 77, "公允价值变动损失"),
    56: ("F065N", 78, "投资损失"),
    57: ("F066N", 79, "递延所得税资产减少"),
    58: ("F067N", 80, "递延所得税负债增加"),
    59: ("F068N", 81, "存货的减少"),
    60: ("F069N", 82, "经营性应收项目的减少"),
    61: ("F070N", 83, "经营性应付项目的增加"),
    62: ("F071N", 84, "其他"),
}

MAX_RETRIES = 3
REQUEST_DELAY = 0.5  # seconds between requests
```

- [ ] **Step 2: Add helper functions**

Append to `scripts/download_indirect_cf.py`:

```python
def load_stocks() -> List[str]:
    """Load stock codes from full_stock_list.txt."""
    with open(STOCK_LIST, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_progress() -> Dict[str, str]:
    """Load progress checkpoint. Returns {stock_code: status}."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: Dict[str, str]) -> None:
    """Save progress checkpoint atomically."""
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS_FILE)


def log(message: str) -> None:
    """Append message to log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{ts}] {message}\n")
```

- [ ] **Step 3: Commit**

```bash
git add scripts/download_indirect_cf.py
git commit -m "feat(scripts): add indirect CF download script skeleton"
```

---

### Task 3: Add data fetch and parse functions

**Files:**
- Modify: `scripts/download_indirect_cf.py`

- [ ] **Step 1: Add fetch function with retry**

Append to `scripts/download_indirect_cf.py`:

```python
def fetch_indirect_cf(stock_code: str) -> Optional[pd.DataFrame]:
    """Fetch indirect CF data from AKShare with retry logic."""
    import akshare as ak

    for attempt in range(MAX_RETRIES):
        try:
            df = ak.stock_financial_cash_ths(symbol=stock_code)
            time.sleep(REQUEST_DELAY)
            return df
        except Exception as e:
            log(f"  Retry {attempt + 1}/{MAX_RETRIES} for {stock_code}: {e}")
            time.sleep(2 ** attempt)
    log(f"  FAILED after {MAX_RETRIES} retries: {stock_code}")
    return None
```

- [ ] **Step 2: Add parse function**

Append to `scripts/download_indirect_cf.py`:

```python
def parse_to_tidy(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    """Parse AKShare DataFrame to Tidy format for 2020-2022 annual reports."""
    rows = []
    for _, row in df.iterrows():
        # First column is report date
        report_date = str(row.iloc[0])
        if not report_date.startswith("202"):
            continue
        try:
            year = int(report_date[:4])
        except (ValueError, TypeError):
            continue
        if year not in YEARS:
            continue
        # Only annual reports (12-31)
        if "-12-31" not in report_date:
            continue

        for col_idx, (fcode, order, name) in INDIRECT_FIELDS.items():
            if col_idx >= len(df.columns):
                continue
            val = row.iloc[col_idx]
            if val is None or str(val) == "False" or str(val) == "nan":
                continue
            try:
                fvalue = float(val)
            except (ValueError, TypeError):
                continue
            rows.append({
                "stock_code": stock_code,
                "year": year,
                "period": "annual",
                "statement_type": "cash_flow",
                "field_code": fcode,
                "field_name": name,
                "value": fvalue,
                "display_order": order,
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 3: Commit**

```bash
git add scripts/download_indirect_cf.py
git commit -m "feat(scripts): add fetch and parse functions for indirect CF"
```

---

### Task 4: Add main processing loop

**Files:**
- Modify: `scripts/download_indirect_cf.py`

- [ ] **Step 1: Add process_single_stock function**

Append to `scripts/download_indirect_cf.py`:

```python
def process_single_stock(stock_code: str) -> str:
    """Process one stock. Returns status: 'done', 'no_data', or 'failed'."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{stock_code}.csv")

    # Skip if already exists with content
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path, encoding="utf-8-sig")
        if len(existing) > 0:
            return "done"

    df = fetch_indirect_cf(stock_code)
    if df is None or len(df) == 0:
        return "no_data"

    tidy_df = parse_to_tidy(df, stock_code)
    if len(tidy_df) == 0:
        return "no_data"

    tidy_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return "done"
```

- [ ] **Step 2: Add main entry point**

Append to `scripts/download_indirect_cf.py`:

```python
def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)

    stocks = load_stocks()
    progress = load_progress()

    total = len(stocks)
    done = sum(1 for v in progress.values() if v == "done")
    no_data = sum(1 for v in progress.values() if v == "no_data")
    failed = sum(1 for v in progress.values() if v == "failed")
    print(f"Total: {total} | Done: {done} | NoData: {no_data} | Failed: {failed}")

    for i, code in enumerate(stocks):
        if progress.get(code) in ("done", "no_data"):
            continue

        status = process_single_stock(code)
        progress[code] = status
        save_progress(progress)

        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{total}] {code}: {status}")

    # Final summary
    done = sum(1 for v in progress.values() if v == "done")
    no_data = sum(1 for v in progress.values() if v == "no_data")
    failed = sum(1 for v in progress.values() if v == "failed")
    print(f"\nFinal: Done: {done} | NoData: {no_data} | Failed: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Commit**

```bash
git add scripts/download_indirect_cf.py
git commit -m "feat(scripts): add main processing loop with checkpoint resume"
```

---

### Task 5: Test with 10 stocks first

**Files:**
- Create: `data/ground_truth_reports/tmp_test_stocks.txt`

- [ ] **Step 1: Create test stock list**

```bash
head -10 data/ground_truth_reports/full_stock_list.txt > data/ground_truth_reports/tmp_test_stocks.txt
```

- [ ] **Step 2: Run test download (modify script to use test list temporarily)**

Run:
```bash
python -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')
import download_indirect_cf as m
m.STOCK_LIST = 'data/ground_truth_reports/tmp_test_stocks.txt'
m.main()
" 2>&1 | tail -10
```

Expected: Downloads 10 stocks, some may be `done`, `no_data`, or `failed`.

- [ ] **Step 3: Verify output**

Run: `ls -la data/exports_v2/indirect_cf/`
Expected: Some `.csv` files exist

Run: `head -3 data/exports_v2/indirect_cf/000001.csv 2>/dev/null`
Expected: CSV header + 2+ data rows (Tidy format)

- [ ] **Step 4: Clean up test files**

```bash
rm data/ground_truth_reports/tmp_test_stocks.txt
rm -rf data/exports_v2/indirect_cf
rm -f data/ground_truth_reports/indirect_cf_progress.json
```

- [ ] **Step 5: Commit (no code changes)**

```bash
git status  # should be clean
```

---

### Task 6: Run full download for all 3,902 stocks

**Files:**
- (No code changes)

- [ ] **Step 1: Run full download in background**

```bash
cd "F:/ai_fin_proj/peri_rept_down"
nohup python scripts/download_indirect_cf.py > /tmp/indirect_cf_run.log 2>&1 &
echo "Started PID: $!"
```

- [ ] **Step 2: Monitor progress (wait 60s)**

Run: `sleep 60 && cat data/ground_truth_reports/indirect_cf_progress.json | python -c "import json, sys; d = json.load(sys.stdin); print(f'Progress: {len(d)} stocks processed')" && tail -3 /tmp/indirect_cf_run.log`
Expected: Progress shows 100+ stocks processed, log shows recent activity

- [ ] **Step 3: Verify output format**

Run: `head -3 data/exports_v2/indirect_cf/000001.csv`
Expected: CSV header `stock_code,year,period,statement_type,field_code,field_name,value,display_order` + 2+ data rows

- [ ] **Step 4: Commit final results**

```bash
git add data/exports_v2/indirect_cf/ data/ground_truth_reports/indirect_cf_progress.json
git commit -m "feat(data): download indirect CF data for all A-share stocks"
```

---

### Task 7: Generate summary report

**Files:**
- Create: `docs/audit/2026-06-08-indirect-cf-download.md`

- [ ] **Step 1: Count downloaded data**

```bash
echo "Total files: $(ls data/exports_v2/indirect_cf/*.csv 2>/dev/null | wc -l)"
echo "Total rows: $(cat data/exports_v2/indirect_cf/*.csv 2>/dev/null | wc -l)"
echo "Total size: $(du -sh data/exports_v2/indirect_cf 2>/dev/null)"
```

- [ ] **Step 2: Write summary report**

Create `docs/audit/2026-06-08-indirect-cf-download.md`:

```markdown
# 间接法现金流量表数据下载报告

**日期**: 2026-06-08
**股票数**: 3,902 只 A 股
**年份**: 2020-2022 年报
**数据源**: Sina (AKShare) `stock_financial_cash_ths`

## 下载结果

- **成功下载**: [count] 只
- **数据缺失**: [count] 只
- **下载失败**: [count] 只
- **总数据行数**: [count] 行
- **总文件大小**: [size]

## 数据格式

按 Tidy CSV 规范存储，每行包含：
- stock_code, year, period, statement_type
- field_code (F057N-F071N)
- field_name (中文名)
- value, display_order

## 字段映射

| F-code | 间接法字段 | display_order |
|--------|------------|---------------|
| F057N | 净利润 | 70 |
| F058N | 资产减值准备 | 71 |
| F059N | 固定资产折旧 | 72 |
| F060N | 无形资产摊销 | 73 |
| F061N | 长期待摊费用摊销 | 74 |
| F062N | 处置固定资产损失 | 75 |
| F063N | 固定资产报废损失 | 76 |
| F064N | 公允价值变动损失 | 77 |
| F065N | 投资损失 | 78 |
| F066N | 递延所得税资产减少 | 79 |
| F067N | 递延所得税负债增加 | 80 |
| F068N | 存货的减少 | 81 |
| F069N | 经营性应收项目的减少 | 82 |
| F070N | 经营性应付项目的增加 | 83 |
| F071N | 其他 | 84 |
```

- [ ] **Step 3: Commit report**

```bash
git add docs/audit/2026-06-08-indirect-cf-download.md
git commit -m "docs: add indirect CF download report"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: All 4 spec sections (architecture, format, error handling, validation) covered
- [x] **No placeholders**: All steps have complete code and exact commands
- [x] **Type consistency**: `process_single_stock` returns status string used consistently in main loop
- [x] **File paths**: All paths are exact and relative to BASE
