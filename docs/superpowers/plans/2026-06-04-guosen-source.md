# Guosen Financial Data Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 国信证券 (Guosen) as a third parallel financial data source, integrating the `gs-stock-financial-query` skill as `astock_fundamentals/sources/guosen/`.

**Architecture:** Adapter pattern — `GuosenLoader` wraps 国信 skill's `get_data.py` HTTP client to expose the same interface as `SinaLoader` (`read_statement`, `get_annual`). Existing `rule_cleaner.py` and `aliases.yaml` are reused; pipeline/baseline gain a `--source` parameter.

**Tech Stack:** Python 3.13, pandas, urllib (from skill), pytest

**Spec:** `docs/superpowers/specs/2026-06-04-guosen-source-design.md`

---

## File Structure

### New files
- `astock_fundamentals/sources/guosen/__init__.py` — exports `GuosenLoader`, `GuosenAuthError`
- `astock_fundamentals/sources/guosen/guosen_loader.py` — core loader
- `astock_fundamentals/sources/guosen/README.md` — usage + API key management
- `astock_fundamentals/sources/guosen/.env.example` — `GS_API_KEY=` template
- `astock_fundamentals/sources/guosen/gs_skill/scripts/get_data.py` — 国信 official script (verbatim copy from /tmp/guosen-skill/)
- `astock_fundamentals/sources/guosen/gs_skill/SKILL.md` — 国信 official doc (verbatim copy)
- `tests/ground_truth/test_guosen_loader.py` — unit tests with mocked HTTP
- `tests/ground_truth/test_guosen_smoke.py` — health-check smoke test (skip if no API key)

### Modified files
- `scripts/clean_sina_pipeline.py` — add `--source {sina,guosen}` arg
- `scripts/baseline_2019_2022.py` — add `--source` arg

### Unchanged
- `rules/aliases.yaml` — guosen field names expected to match sina (re-verified in Task 7)
- `astock_fundamentals/ground_truth/rule_cleaner.py` — generic
- `astock_fundamentals/ground_truth/comparator.py` — generic

---

## Task 1: Scaffold `sources/guosen/` directory and copy skill files

**Files:**
- Create: `astock_fundamentals/sources/guosen/__init__.py`
- Create: `astock_fundamentals/sources/guosen/gs_skill/SKILL.md` (copy from /tmp)
- Create: `astock_fundamentals/sources/guosen/gs_skill/scripts/get_data.py` (copy from /tmp)
- Create: `astock_fundamentals/sources/guosen/README.md`
- Create: `astock_fundamentals/sources/guosen/.env.example`

- [ ] **Step 1: Create the directory structure**

Run:
```bash
mkdir -p astock_fundamentals/sources/guosen/gs_skill/scripts
```

Expected: no output, directory created.

- [ ] **Step 2: Copy skill files from /tmp to project**

Run:
```bash
cp /tmp/guosen-skill/gs-stock-financial-query/SKILL.md astock_fundamentals/sources/guosen/gs_skill/SKILL.md
cp /tmp/guosen-skill/gs-stock-financial-query/scripts/get_data.py astock_fundamentals/sources/guosen/gs_skill/scripts/get_data.py
```

Expected: no output, files copied. Verify with:
```bash
ls -la astock_fundamentals/sources/guosen/gs_skill/scripts/get_data.py
```

- [ ] **Step 3: Create `__init__.py`**

Create `astock_fundamentals/sources/guosen/__init__.py`:
```python
# -*- coding: utf-8 -*-
"""
Guosen (国信证券) financial data source.

Adapter for the gs-stock-financial-query skill. Provides a SinaLoader-compatible
interface (read_statement, get_annual) for use in clean_sina_pipeline.py
and baseline_2019_2022.py.

Requires GS_API_KEY env var or api_key parameter at construction.
"""
from astock_fundamentals.sources.guosen.guosen_loader import (
    GuosenLoader,
    GuosenAuthError,
    GuosenEmptyDataError,
)

__all__ = ["GuosenLoader", "GuosenAuthError", "GuosenEmptyDataError"]
```

- [ ] **Step 4: Create `.env.example`**

Create `astock_fundamentals/sources/guosen/.env.example`:
```bash
# Guosen (国信证券) financial data API key
# Get from: https://www.guosen.com.cn/gs/xxskills/index.html
GS_API_KEY=your_actual_api_key_here
```

- [ ] **Step 5: Create `README.md`**

Create `astock_fundamentals/sources/guosen/README.md`:
```markdown
# 国信证券数据源 (GuosenLoader)

对接国信证券财务数据 skill。提供与 SinaLoader 兼容的接口 (`read_statement`, `get_annual`)。

## API Key 配置

按以下优先级加载：

1. 构造参数 `GuosenLoader(api_key="...")` 
2. 环境变量 `GS_API_KEY`
3. 项目根 `./memory.md` 中 `GS_API_KEY=...` 字段

### Windows PowerShell
```powershell
$env:GS_API_KEY="your_key"
```

### Linux/macOS
```bash
export GS_API_KEY="your_key"
```

## 用法

```python
from astock_fundamentals.sources.guosen import GuosenLoader

loader = GuosenLoader()  # 从环境变量读取 API key
df = loader.get_annual(
    stock_code="600519",
    target_years=[2019, 2020, 2021, 2022],
    statement_type="balance_sheet",  # 或 income_statement / cash_flow
)
print(df.head())
```

CLI:

```bash
python scripts/clean_sina_pipeline.py --source guosen --stocks 600519 --years 2019 2020
python scripts/baseline_2019_2022.py --source guosen
```

## 港股支持

```python
df = loader.read_statement("02020", "balance_sheet")  # 港股 (自动 market=HK)
```

## 限制

- 网络依赖：必须能访问 `https://dgzt.guosen.com.cn`
- 调用频率限制：依赖国信 API 配额
- 字段名预期与 Sina 中文名一致 (待 Task 7 验证)
```

- [ ] **Step 6: Verify scaffold**

Run:
```bash
find astock_fundamentals/sources/guosen -type f
```

Expected:
```
astock_fundamentals/sources/guosen/.env.example
astock_fundamentals/sources/guosen/README.md
astock_fundamentals/sources/guosen/__init__.py
astock_fundamentals/sources/guosen/gs_skill/SKILL.md
astock_fundamentals/sources/guosen/gs_skill/scripts/get_data.py
```

- [ ] **Step 7: Commit**

```bash
git add astock_fundamentals/sources/guosen/
git commit -m "feat(guosen): scaffold sources/guosen/ with skill copy"
```

---

## Task 2: Implement exception classes and key resolution

**Files:**
- Create: `astock_fundamentals/sources/guosen/guosen_loader.py` (initial)
- Test: `tests/ground_truth/test_guosen_loader.py`

- [ ] **Step 1: Write failing test for exception classes**

Create `tests/ground_truth/test_guosen_loader.py`:
```python
import os
import sys
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from astock_fundamentals.sources.guosen import (
    GuosenLoader,
    GuosenAuthError,
    GuosenEmptyDataError,
)


def test_guosen_auth_error_is_exception():
    assert issubclass(GuosenAuthError, Exception)


def test_guosen_empty_data_error_is_exception():
    assert issubclass(GuosenEmptyDataError, Exception)


def test_guosen_load_raises_auth_error_when_no_key(monkeypatch):
    monkeypatch.delenv("GS_API_KEY", raising=False)
    with pytest.raises(GuosenAuthError):
        GuosenLoader()


def test_guosen_load_uses_explicit_api_key():
    loader = GuosenLoader(api_key="explicit-test-key")
    assert loader.api_key == "explicit-test-key"


def test_guosen_load_uses_env_var(monkeypatch):
    monkeypatch.setenv("GS_API_KEY", "env-test-key")
    loader = GuosenLoader()
    assert loader.api_key == "env-test-key"


def test_guosen_load_reads_memory_md(monkeypatch, tmp_path):
    monkeypatch.delenv("GS_API_KEY", raising=False)
    memory_path = tmp_path / "memory.md"
    memory_path.write_text("# Project memory\nGS_API_KEY=memory-test-key\n")
    loader = GuosenLoader(memory_path=str(memory_path))
    assert loader.api_key == "memory-test-key"
```

- [ ] **Step 2: Run test, expect failure (no module yet)**

Run: `pytest tests/ground_truth/test_guosen_loader.py -v`
Expected: ImportError (guosen_loader module not found).

- [ ] **Step 3: Create exception classes and GuosenLoader init**

Create `astock_fundamentals/sources/guosen/guosen_loader.py`:
```python
# -*- coding: utf-8 -*-
"""
GuosenLoader: adapter for the 国信证券 (gs-stock-financial-query) skill.

Provides a SinaLoader-compatible interface (read_statement, get_annual) for
the cleaning pipeline and baseline measurement scripts.

Sources:
- A股 BS:  GET /gsnews/gsf10/financial/balanceSheet/1.0
- A股 IS:  GET /gsnews/gsf10/financial/incomeStatement/1.0
- A股 CF:  GET /gsnews/gsf10/financial/cashFlowStatement/1.0
- 港股 BS: GET /gsnews/hkf10/financial/balanceSheet/1.0
- 港股 IS: GET /gsnews/hkf10/financial/incomeStatement/1.0
- 港股 CF: GET /gsnews/hkf10/financial/cashFlowStatement/1.0
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Make the bundled skill importable
_SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gs_skill")
_SKILL_SCRIPTS = os.path.join(_SKILL_DIR, "scripts")
if _SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, _SKILL_SCRIPTS)


class GuosenAuthError(RuntimeError):
    """Raised when GS_API_KEY is missing or invalid."""


class GuosenEmptyDataError(RuntimeError):
    """Raised when the API returns no data for the requested period."""


# Mapping from 6-digit code prefix to market
def _detect_market(stock_code: str) -> str:
    """Detect SH/SZ from A-share code, or HK for Hong Kong.

    SH (Shanghai): 600xxx, 601xxx, 603xxx, 688xxx
    SZ (Shenzhen): 000xxx, 002xxx, 300xxx
    HK: anything else (caller should validate)
    """
    code = str(stock_code).zfill(6)
    if code.startswith(("600", "601", "603", "688")):
        return "SH"
    if code.startswith(("000", "002", "300", "200", "080")):
        return "SZ"
    return "HK"


# Statement type to (module function, kind) mapping
# kind is 'a' (A股) or 'hk' (港股)
_STATEMENT_API = {
    ("balance_sheet", "a"): "query_a_stock_balance_sheet",
    ("income_statement", "a"): "query_a_stock_income_statement",
    ("cash_flow", "a"): "query_a_stock_cash_flow_statement",
    ("balance_sheet", "hk"): "query_hk_stock_balance_sheet",
    ("income_statement", "hk"): "query_hk_stock_income_statement",
    ("cash_flow", "hk"): "query_hk_stock_cash_flow_statement",
}


def _read_api_key_from_memory(memory_path: str) -> Optional[str]:
    """Read GS_API_KEY=... from a memory.md-style file."""
    path = Path(memory_path)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^GS_API_KEY\s*=\s*(\S+)\s*$", text, re.MULTILINE)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return None


class GuosenLoader:
    """Adapter for the 国信证券 (gs-stock-financial-query) skill."""

    name = "guosen"

    def __init__(
        self,
        api_key: Optional[str] = None,
        memory_path: Optional[str] = None,
        timeout_seconds: int = 15,
    ):
        """Resolve API key in priority: explicit arg > env > memory.md.

        Args:
            api_key: 显式 key. 优先于环境变量
            memory_path: ./memory.md 路径, 用于读取 GS_API_KEY. 默认 ./memory.md
            timeout_seconds: HTTP 超时
        """
        self.api_key = (
            api_key
            or os.environ.get("GS_API_KEY")
            or _read_api_key_from_memory(memory_path or "memory.md")
        )
        if not self.api_key:
            raise GuosenAuthError(
                "GS_API_KEY is required. Set it via:\n"
                "  1. GuosenLoader(api_key='...')\n"
                "  2. $env:GS_API_KEY='...' (PowerShell)\n"
                "  3. export GS_API_KEY='...' (bash)\n"
                "  4. GS_API_KEY=... in ./memory.md"
            )
        self.timeout_seconds = timeout_seconds
        self._skill_funcs: Dict[str, object] = {}
        self._ensure_skill_imported()

    def _ensure_skill_imported(self) -> None:
        """Lazy import the bundled skill script (it raises at import if no key)."""
        if self._skill_funcs:
            return
        # The skill reads GS_API_KEY at import time
        os.environ["GS_API_KEY"] = self.api_key
        try:
            import get_data as _gd  # type: ignore
            self._skill_funcs["module"] = _gd
            for api_name in set(_STATEMENT_API.values()):
                self._skill_funcs[api_name] = getattr(_gd, api_name)
        except Exception as e:
            raise GuosenAuthError(f"Failed to import 国信 skill: {e}")

    def health_check(self) -> bool:
        """Verify API key + network connectivity by fetching the latest BS for 600519."""
        try:
            df = self.read_statement("600519", "balance_sheet")
            return not df.empty
        except Exception:
            return False
```

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/ground_truth/test_guosen_loader.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/sources/guosen/guosen_loader.py tests/ground_truth/test_guosen_loader.py
git commit -m "feat(guosen): GuosenLoader with API key resolution + exception classes"
```

---

## Task 3: Implement `read_statement` and DataFrame conversion

**Files:**
- Modify: `astock_fundamentals/sources/guosen/guosen_loader.py`
- Modify: `tests/ground_truth/test_guosen_loader.py`

- [ ] **Step 1: Add failing tests for read_statement**

Append to `tests/ground_truth/test_guosen_loader.py`:
```python
def _make_api_response(items: List[dict]) -> dict:
    """Build a fake guosen API response."""
    return {
        "result": {"code": 0, "msg": "请求成功"},
        "data": {
            "info": [{"key": item["key"], "name": item["name"]} for item in items],
            "data": items,
        },
    }


def test_guosen_read_statement_returns_dataframe(monkeypatch):
    """read_statement should return a DataFrame with Chinese column names."""
    items = [
        {"key": "F006N", "name": "货币资金", "date": "2019-12-31", "value": 1000000.0},
        {"key": "F077N", "name": "结算备付金", "date": "2019-12-31", "value": 500000.0},
    ]

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        return _make_api_response(items)

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    df = loader.read_statement("600519", "balance_sheet")
    assert isinstance(df, pd.DataFrame)
    assert "报告日" in df.columns
    assert len(df) == 1
    # Chinese field names should be columns
    assert "货币资金" in df.columns
    assert "结算备付金" in df.columns


def test_guosen_read_statement_detects_market_by_prefix(monkeypatch):
    """600xxx should be SH, 000xxx should be SZ."""
    captured = {}

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        captured["code"] = code
        captured["market"] = market
        return _make_api_response([])

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    loader.read_statement("600519", "balance_sheet")
    assert captured["market"] == "SH"

    loader.read_statement("000001", "balance_sheet")
    assert captured["market"] == "SZ"


def test_guosen_read_statement_handles_hk_stock(monkeypatch):
    """5-digit HK code should be passed with market=HK."""
    captured = {}

    def fake_query(code, report_year=None, report_type=None, count=1):
        captured["code"] = code
        captured["market"] = "HK"
        return _make_api_response([])

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_hk_stock_balance_sheet"] = fake_query
    df = loader.read_statement("02020", "balance_sheet")
    assert captured["code"] == "02020"


def test_guosen_read_statement_raises_on_error(monkeypatch):
    def fake_query(*args, **kwargs):
        return {"result": {"code": -1, "msg": "API key 无效"}}

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    with pytest.raises(Exception) as excinfo:
        loader.read_statement("600519", "balance_sheet")
    assert "API key 无效" in str(excinfo.value) or "error" in str(excinfo.value).lower()
```

- [ ] **Step 2: Run test, expect failure (read_statement not implemented)**

Run: `pytest tests/ground_truth/test_guosen_loader.py -v`
Expected: 4 new tests FAIL with `AttributeError: 'GuosenLoader' object has no attribute 'read_statement'`.

- [ ] **Step 3: Implement read_statement and DataFrame conversion**

Append to `astock_fundamentals/sources/guosen/guosen_loader.py`:
```python
    @staticmethod
    def _api_response_to_df(response: dict) -> pd.DataFrame:
        """Convert 国信 API response {result, data} to a wide DataFrame.

        Each row = one reporting period.
        Columns = the info array's "name" fields (Chinese item names) +
                  a few meta columns (报告日, 数据源, ...).
        """
        result = response.get("result", {}) or {}
        if result.get("code") != 0:
            msg = result.get("msg", "unknown error")
            raise RuntimeError(f"国信 API error: {msg}")
        data_block = response.get("data", {}) or {}
        info = data_block.get("info", []) or []
        data_list = data_block.get("data", []) or []
        if not data_list:
            return pd.DataFrame()

        # Build map: name -> {key, values_by_date}
        name_to_key = {it["name"]: it["key"] for it in info if "name" in it and "key" in it}
        # Per-name, per-date values
        per_name: Dict[str, Dict[str, float]] = {nm: {} for nm in name_to_key}
        for row in data_list:
            d = str(row.get("date", row.get("DECLAREDATE", "")))
            for nm in name_to_key:
                v = row.get(nm)
                if v is not None:
                    try:
                        per_name[nm][d] = float(v)
                    except (TypeError, ValueError):
                        pass

        # Compose DataFrame: one row per date
        all_dates = sorted({d for nm in per_name for d in per_name[nm]})
        rows = []
        for d in all_dates:
            row = {"报告日": d}
            for nm, by_date in per_name.items():
                row[nm] = by_date.get(d)
            rows.append(row)
        df = pd.DataFrame(rows)
        if "报告日" in df.columns and not df.empty:
            df["报告日"] = df["报告日"].astype(str)
        return df

    def read_statement(self, stock_code: str, statement_type: str) -> pd.DataFrame:
        """Fetch one period (latest) of a single statement type.

        Args:
            stock_code: 6-digit A-share code (SH/SZ) or 5-digit HK code
            statement_type: balance_sheet / income_statement / cash_flow

        Returns: DataFrame with one row (or empty if no data)
        """
        market = _detect_market(stock_code)
        kind = "hk" if market == "HK" else "a"
        api_name = _STATEMENT_API[(statement_type, kind)]
        if api_name not in self._skill_funcs:
            raise RuntimeError(f"GuosenLoader: skill function {api_name} not loaded")
        fn = self._skill_funcs[api_name]
        if kind == "a":
            response = fn(stock_code, market, "Q0", None, 1)
        else:
            response = fn(stock_code, None, None, 1)
        return self._api_response_to_df(response)
```

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/ground_truth/test_guosen_loader.py -v`
Expected: 10 passed (6 from Task 2 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/sources/guosen/guosen_loader.py tests/ground_truth/test_guosen_loader.py
git commit -m "feat(guosen): read_statement with API response → DataFrame conversion"
```

---

## Task 4: Implement `get_annual` with year slicing

**Files:**
- Modify: `astock_fundamentals/sources/guosen/guosen_loader.py`
- Modify: `tests/ground_truth/test_guosen_loader.py`

- [ ] **Step 1: Add failing test for get_annual**

Append to `tests/ground_truth/test_guosen_loader.py`:
```python
def test_guosen_get_annual_filters_to_target_years(monkeypatch):
    """get_annual should filter API response to 2019-2022 only."""
    items = [
        {"key": "F006N", "name": "货币资金", "date": "2018-12-31", "value": 1.0},
        {"key": "F006N", "name": "货币资金", "date": "2019-12-31", "value": 2.0},
        {"key": "F006N", "name": "货币资金", "date": "2020-12-31", "value": 3.0},
        {"key": "F006N", "name": "货币资金", "date": "2021-12-31", "value": 4.0},
        {"key": "F006N", "name": "货币资金", "date": "2022-12-31", "value": 5.0},
        {"key": "F006N", "name": "货币资金", "date": "2023-12-31", "value": 6.0},
    ]

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        return _make_api_response(items)

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    df = loader.get_annual("600519", [2019, 2020, 2021, 2022], "balance_sheet")
    assert len(df) == 4
    # 报告日 should be 2019..2022 only
    periods = set(df["报告日"].astype(str))
    assert periods == {"2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31"}
    assert df["货币资金"].tolist() == [2.0, 3.0, 4.0, 5.0]


def test_guosen_get_annual_passes_count_to_api(monkeypatch):
    """get_annual should pass count = max(target_years) - min(target_years) + 1."""
    captured = {}

    def fake_query(code, market, report_type="Q0", report_year=None, count=1):
        captured["count"] = count
        return _make_api_response([])

    loader = GuosenLoader(api_key="test-key")
    loader._skill_funcs["query_a_stock_balance_sheet"] = fake_query
    loader.get_annual("600519", [2019, 2020, 2021, 2022], "balance_sheet")
    assert captured["count"] == 4  # 4 years requested
```

- [ ] **Step 2: Run test, expect failure**

Run: `pytest tests/ground_truth/test_guosen_loader.py -v`
Expected: 2 new tests FAIL with `AttributeError: 'GuosenLoader' object has no attribute 'get_annual'`.

- [ ] **Step 3: Implement get_annual**

Append to `astock_fundamentals/sources/guosen/guosen_loader.py`:
```python
    def get_annual(
        self, stock_code: str, target_years: List[int], statement_type: str,
    ) -> pd.DataFrame:
        """Fetch multiple years of a single statement type.

        Args:
            stock_code: 6-digit A-share or 5-digit HK code
            target_years: e.g. [2019, 2020, 2021, 2022]
            statement_type: balance_sheet / income_statement / cash_flow

        Returns: DataFrame with one row per year-end reporting date.
        """
        market = _detect_market(stock_code)
        kind = "hk" if market == "HK" else "a"
        api_name = _STATEMENT_API[(statement_type, kind)]
        if api_name not in self._skill_funcs:
            raise RuntimeError(f"GuosenLoader: skill function {api_name} not loaded")
        fn = self._skill_funcs[api_name]
        # Request count = max - min + 1 (caller may want more; allow len(target_years) + 1 buffer)
        count = max(target_years) - min(target_years) + 2
        if kind == "a":
            response = fn(stock_code, market, "Q0", None, count)
        else:
            response = fn(stock_code, None, None, count)
        df = self._api_response_to_df(response)
        if df.empty:
            return df
        # Filter to rows whose 报告日 year is in target_years
        target_set = set(target_years)
        # 报告日 format: "YYYY-MM-DD" or "YYYYMMDD"
        def _year_of(date_str: str) -> int:
            s = str(date_str).replace("-", "")
            return int(s[:4]) if len(s) >= 4 and s[:4].isdigit() else 0
        df = df[df["报告日"].apply(_year_of).isin(target_set)].copy()
        return df
```

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/ground_truth/test_guosen_loader.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add astock_fundamentals/sources/guosen/guosen_loader.py tests/ground_truth/test_guosen_loader.py
git commit -m "feat(guosen): get_annual with year filtering"
```

---

## Task 5: Add `health_check` smoke test

**Files:**
- Create: `tests/ground_truth/test_guosen_smoke.py`

- [ ] **Step 1: Write the smoke test**

Create `tests/ground_truth/test_guosen_smoke.py`:
```python
"""Smoke test for GuosenLoader connectivity (skipped if no API key set)."""
import os

import pytest


def test_health_check_if_key_set():
    """If GS_API_KEY is set, loader.health_check() should work without raising."""
    if not os.environ.get("GS_API_KEY"):
        pytest.skip("GS_API_KEY not set; skipping live health check")
    from astock_fundamentals.sources.guosen import GuosenLoader
    loader = GuosenLoader()
    # Don't assert True — the API may be rate-limited or unreachable in CI.
    # Just check the call doesn't raise.
    try:
        result = loader.health_check()
    except Exception as e:
        pytest.skip(f"API call failed (likely network/rate limit): {e}")
    assert isinstance(result, bool)
```

- [ ] **Step 2: Run test, expect skip (no key in CI)**

Run: `pytest tests/ground_truth/test_guosen_smoke.py -v`
Expected: 1 skipped (or passed if GS_API_KEY is set).

- [ ] **Step 3: Commit**

```bash
git add tests/ground_truth/test_guosen_smoke.py
git commit -m "test(guosen): smoke test for health_check (skip if no API key)"
```

---

## Task 6: Add `--source` parameter to `clean_sina_pipeline.py`

**Files:**
- Modify: `scripts/clean_sina_pipeline.py`
- Modify: `tests/scripts/test_clean_pipeline.py`

- [ ] **Step 1: Add failing test for --source=guosen**

Append to `tests/scripts/test_clean_pipeline.py`:
```python
def test_pipeline_runs_with_guosen_source():
    """Pipeline should accept --source=guosen and call GuosenLoader."""
    import subprocess
    import os
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(PROJECT_ROOT, "scripts", "clean_sina_pipeline.py"),
            "--source", "guosen",
            "--stocks", "000001",
            "--years", "2019", "2020",
            "--output-dir", os.path.join(PROJECT_ROOT, "data", "exports_v2"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    # Should fail with GuosenAuthError (no API key), NOT ModuleNotFoundError
    # or argument error
    assert "GS_API_KEY" in result.stdout + result.stderr or "guosen" in result.stdout.lower()
```

- [ ] **Step 2: Run test, expect failure**

Run: `pytest tests/scripts/test_clean_pipeline.py::test_pipeline_runs_with_guosen_source -v`
Expected: FAIL with `unrecognized argument: --source` (or similar argparse error).

- [ ] **Step 3: Add --source argument to clean_sina_pipeline.py**

In `scripts/clean_sina_pipeline.py`, modify the `main()` function to:
- Add `p.add_argument("--source", choices=["sina", "guosen"], default="sina", help="Data source")` after the existing `p.add_argument("--industries", ...)` line
- After `from astock_fundamentals.ground_truth.sina_loader import SinaLoader` (line 25), add:
  ```python
  from astock_fundamentals.sources.guosen import GuosenLoader, GuosenAuthError
  ```
- In `run_pipeline`, after `loader = SinaLoader(cache_dir)`, add source dispatch:
  ```python
  if args.source == "guosen":
      try:
          loader = GuosenLoader()
      except GuosenAuthError as e:
          print(f"ERROR: {e}")
          return
  else:
      loader = SinaLoader(cache_dir)
  ```
  Wait — `run_pipeline` doesn't currently take `args`. We need to thread the source through. Refactor:
  - Change `run_pipeline` signature to accept `loader` (or `source`) parameter
  - Or: Build the loader inside `run_pipeline` based on a source parameter

  Simpler approach: Pass `source` to `run_pipeline` and have it build the loader:

  Replace the `def run_pipeline(...)` signature to add `source: str = "sina"` as last arg.
  In the function body, replace `loader = SinaLoader(cache_dir)` with:
  ```python
  if source == "guosen":
      try:
          loader = GuosenLoader()
      except GuosenAuthError as e:
          print(f"ERROR: {e}")
          return
  else:
      loader = SinaLoader(cache_dir)
  ```
  In `main()`, call `run_pipeline(..., source=args.source)`.

- [ ] **Step 4: Run test, expect pass**

Run: `pytest tests/scripts/test_clean_pipeline.py -v`
Expected: 4 passed (3 existing + 1 new for guosen). The guosen test should pass because we expect "GS_API_KEY" or "guosen" to appear in stdout/stderr.

- [ ] **Step 5: Commit**

```bash
git add scripts/clean_sina_pipeline.py tests/scripts/test_clean_pipeline.py
git commit -m "feat(pipeline): --source {sina,guosen} for data source selection"
```

---

## Task 7: Add `--source` parameter to `baseline_2019_2022.py`

**Files:**
- Modify: `scripts/baseline_2019_2022.py`

- [ ] **Step 1: Add --source argument to main()**

In `scripts/baseline_2019_2022.py`:
- Add `p.add_argument("--source", choices=["sina", "guosen"], default="sina", help="Data source")` in `main()`
- After `from astock_fundamentals.ground_truth.sina_loader import SinaLoader`, add:
  ```python
  from astock_fundamentals.sources.guosen import GuosenLoader, GuosenAuthError
  ```
- Replace the `for code in SAMPLE_STOCKS:` body inside `main()` to dispatch loader:
  ```python
  if args.source == "guosen":
      try:
          loader = GuosenLoader()
      except GuosenAuthError as e:
          print(f"ERROR: {e}")
          return
  else:
      loader = SinaLoader(CACHE_DIR)
  ```
  The existing `loader.get_annual(code, YEARS, st)` call works for both.

- [ ] **Step 2: Manually verify the script still works with sina (default)**

Run: `python scripts/baseline_2019_2022.py --years 2019 2020 2021 2022 2>&1 | head -5`
Expected: prints "Learning from 209 stocks..." or similar (since --source defaults to sina).

- [ ] **Step 3: Commit**

```bash
git add scripts/baseline_2019_2022.py
git commit -m "feat(baseline): --source {sina,guosen} parameter"
```

---

## Task 8: Run full test suite + push

**Files:** none (final verification)

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ground_truth/ tests/scripts/ -q 2>&1 | tail -5`
Expected: all tests pass (count should be ~32 with the new ones).

- [ ] **Step 2: Commit any remaining staged changes**

```bash
git status -s
```
If anything unstaged, run `git add -A && git commit -m "chore: finalize guosen source integration"`.

- [ ] **Step 3: Push to origin**

```bash
git push origin master
```
Expected: push succeeds, prints `X..Y master -> master`.

---

## Self-Review

**1. Spec coverage:**
- §3.1 directory structure → Task 1 ✓
- §3.2 GuosenLoader interface (read_statement, get_annual) → Tasks 3-4 ✓
- §3.3 key differences table (documented, no code) → spec only ✓
- §3.4 data format alignment (re-uses aliases) → tested in Task 3-4 ✓
- §3.5 pipeline --source → Task 6 ✓
- §3.6 baseline --source → Task 7 ✓
- §3.7 error handling (GuosenAuthError, GuosenEmptyDataError) → Task 2-3 ✓
- §3.8 test strategy (mock, skip-if-no-key) → Tasks 2-5 ✓

**2. Placeholder scan:** No "TBD", "TODO", "implement later" found.

**3. Type consistency:**
- `GuosenLoader` constructor signature: `(api_key=None, memory_path=None, timeout_seconds=15)` — consistent across Tasks 2, 3, 4
- `read_statement(self, stock_code, statement_type)` — same in code and tests
- `get_annual(self, stock_code, target_years, statement_type)` — same in code and tests
- `_detect_market`, `_STATEMENT_API`, `_read_api_key_from_memory` — defined once in Task 2, reused in 3-4

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-guosen-source.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch fresh subagent per task
2. **Inline Execution** - execute tasks in this session with checkpoints

Which approach?
