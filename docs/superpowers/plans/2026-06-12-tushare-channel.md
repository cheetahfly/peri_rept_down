# Tushare 数据渠道实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `peri_rept_down` 项目中实现 tushare 作为与 RDS/PDF/akshare/Guosen 同级的第 5 数据渠道，生成 tushare vs RDS 对比报告验证"源头=巨潮资讯"声明。

**Architecture:** 复用 Job 3 dual-channel 架构（normalize/extract/best_match）扩展为 tri-channel；TushareProvider 继承 BaseApiProvider 完整实现 3 个 get_*_statement；新增 scripts/tri_channel_cf_lib.py + tri_channel_cf_download.py；独立 download_tushare_full.py 用于 5K 全量拉取。

**Tech Stack:** Python 3.13, tushare>=1.4, pandas, pytest, pyyaml, akshare (复用 Job 3 工具库)

**Spec:** `docs/superpowers/specs/2026-06-12-tushare-channel-design.md`

---

## Phase 1: 基础与依赖

### Task 1.1: 加 tushare 依赖到 pyproject.toml

**Files:**
- Modify: `pyproject.toml` (dependencies block)

- [ ] **Step 1: 编辑 pyproject.toml 加入 tushare**

打开 `pyproject.toml`，在 `dependencies` 列表追加：
```toml
    "tushare>=1.4",
```

保持现有依赖不动。最终的 dependencies 块形如：
```toml
dependencies = [
    "requests>=2.28",
    "beautifulsoup4>=4.11",
    "pandas>=1.5",
    "lxml>=4.9",
    "pdfplumber>=0.9",
    "pyreadr>=0.4",
    "PyYAML>=6.0",
    "tushare>=1.4",
]
```

- [ ] **Step 2: 验证依赖能解析（不实际安装）**

Run: `python -c "import tomli; d = tomli.load(open('pyproject.toml', 'rb')); print([x for x in d['project']['dependencies'] if 'tushare' in x])"`
Expected: `['tushare>=1.4']`

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml
git commit -m "chore: add tushare>=1.4 to project dependencies"
```

---

### Task 1.2: 创建 .env.tushare.example 模板

**Files:**
- Create: `.env.tushare.example`

- [ ] **Step 1: 写入模板文件**

```bash
cat > .env.tushare.example <<'EOF'
# Tushare Pro API Token
# Get your token from: https://tushare.pro/user/token
# Required permission tier: 2000+ (for balancesheet/income/cashflow endpoints)
TUSHARE_TOKEN=your_tushare_token_here

# Rate limit config (optional, default 0.4s)
# Lower = faster but more likely to hit 403 rate limit
# Higher = slower but safer
TUSHARE_RATE_LIMIT_SLEEP=0.4
EOF
```

- [ ] **Step 2: 提交**

```bash
git add .env.tushare.example
git commit -m "docs: add .env.tushare.example token template"
```

---

## Phase 2: TushareProvider 完整实现

### Task 2.1: 替换 tushare_provider.py 骨架（含 _connect + token 检查）

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py` (48 行 → 完整实现)

- [ ] **Step 1: 写替换版本的 tushare_provider.py（部分 — 仅连接逻辑）**

完整替换文件内容：
```python
# -*- coding: utf-8 -*-
"""
Tushare数据源 - 通过tushare库获取A股财务数据

安装: pip install tushare

Tushare 提供结构化金融数据API（部分数据需积分）。
文档: https://tushare.pro/document/2

源头：Tushare 标榜"巨潮资讯"（cninfo）结构化财报数据，与 RDS 同源。
使用本 provider 后，请运行 scripts/tri_channel_cf_download.py 与 RDS 对比，
验证 exact_rate 假设。
"""
import time
from typing import Dict, Optional

import pandas as pd

from astock_fundamentals.sources.api import BaseApiProvider


class TushareProvider(BaseApiProvider):
    """Tushare 财务数据获取器"""
    name = "tushare"

    def __init__(self, token: str = "", rate_limit_sleep: float = 0.4):
        if not token:
            raise ValueError(
                "TushareProvider 需要 token。请通过 TUSHARE_TOKEN 环境变量或 --token 参数提供。"
            )
        self._token = token
        self._api = None
        self._sleep = rate_limit_sleep
        self._last_call_ts = 0.0

    def _connect(self):
        if self._api is not None:
            return
        try:
            import tushare as ts
            ts.set_token(self._token)
            self._api = ts.pro_api()
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")

    # _throttle / _fetch / _df_to_dict / _ts_code / _period
    # 在 Task 2.2-2.4 中实现
    # get_*_statement 在 Task 2.5-2.7 中实现
```

- [ ] **Step 2: 验证 token 缺失时立即报错**

Run: `PYTHONIOENCODING=utf-8 python -c "from astock_fundamentals.sources.api.tushare_provider import TushareProvider; TushareProvider(token='')" 2>&1`
Expected: `ValueError: TushareProvider 需要 token...`

- [ ] **Step 3: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py
git commit -m "feat(tushare): add TushareProvider skeleton with token validation"
```

---

### Task 2.2: 实现 _throttle() 限流方法

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py` (加 _throttle)

- [ ] **Step 1: 写第一个失败测试**

在 `tests/test_tushare_provider.py` 创建（如果文件不存在先创建）：
```python
# -*- coding: utf-8 -*-
"""TushareProvider 单元测试（mock tushare 库，无 token 依赖）"""
import sys
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, "astock_fundamentals")
sys.path.insert(0, "scripts")

from astock_fundamentals.sources.api.tushare_provider import TushareProvider


@pytest.fixture
def fake_tushare():
    """Patch tushare 模块以避免 import 错误"""
    fake = MagicMock()
    fake.set_token = MagicMock()
    fake.pro_api = MagicMock(return_value=MagicMock())
    sys.modules["tushare"] = fake
    yield fake
    del sys.modules["tushare"]


@pytest.fixture
def provider(fake_tushare):
    return TushareProvider(token="fake", rate_limit_sleep=0.1)


def test_throttle_sleeps_when_too_fast(provider):
    """_throttle 应该在两次连续调用之间 sleep"""
    provider._last_call_ts = time.time()  # 上次调用刚刚发生
    start = time.time()
    provider._throttle()
    elapsed = time.time() - start
    # 至少 sleep 0.05s（rate_limit_sleep=0.1，留 50% 余量）
    assert elapsed >= 0.05, f"throttle too fast: {elapsed}s"


def test_throttle_skips_when_enough_time_passed(provider):
    """_throttle 在间隔足够时不应 sleep"""
    provider._last_call_ts = time.time() - 1.0  # 1 秒前
    start = time.time()
    provider._throttle()
    elapsed = time.time() - start
    # 不应 sleep
    assert elapsed < 0.05, f"throttle unexpectedly slow: {elapsed}s"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v`
Expected: 2 个 FAIL（AttributeError: _throttle）

- [ ] **Step 3: 实现 _throttle 方法**

在 tushare_provider.py 的 `TushareProvider` 类内（`_connect` 之后）追加：
```python
    def _throttle(self):
        """强制 sleep 间隔，避免触发 200 req/min 限流"""
        elapsed = time.time() - self._last_call_ts
        if elapsed < self._sleep:
            time.sleep(self._sleep - elapsed)
        self._last_call_ts = time.time()
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v`
Expected: 2 个 PASS

- [ ] **Step 5: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat(tushare): add _throttle rate-limit method + tests"
```

---

### Task 2.3: 实现 _ts_code() 转换函数

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py` (加 _ts_code + 测试)

- [ ] **Step 1: 加测试用例**

追加到 `tests/test_tushare_provider.py`：
```python
def test_ts_code_sh_prefix():
    """6xx 开头的股票加 .SH 后缀"""
    p = TushareProvider.__new__(TushareProvider)  # 不触发 token 检查
    assert p._ts_code("600519") == "600519.SH"
    assert p._ts_code("601318") == "601318.SH"
    assert p._ts_code("688981") == "688981.SH"


def test_ts_code_sz_prefix():
    """0xx/3xx 开头的股票加 .SZ 后缀"""
    p = TushareProvider.__new__(TushareProvider)
    assert p._ts_code("000001") == "000001.SZ"
    assert p._ts_code("300750") == "300750.SZ"
    assert p._ts_code("002415") == "002415.SZ"


def test_ts_code_unknown_market_raises():
    """未知前缀应抛 ValueError"""
    p = TushareProvider.__new__(TushareProvider)
    with pytest.raises(ValueError, match="Unknown market"):
        p._ts_code("999999")
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v`
Expected: 3 个 FAIL（AttributeError: _ts_code）

- [ ] **Step 3: 实现 _ts_code**

在 tushare_provider.py 的 `TushareProvider` 类内追加：
```python
    @staticmethod
    def _ts_code(stock_code: str) -> str:
        """600xxx → 600xxx.SH, 0xxxxx/3xxxxx → 0xxxxx.SZ"""
        if stock_code.startswith(("600", "601", "603", "605", "688")):
            return f"{stock_code}.SH"
        if stock_code.startswith(("000", "001", "002", "003", "300", "301")):
            return f"{stock_code}.SZ"
        raise ValueError(f"Unknown market for stock code: {stock_code}")
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v`
Expected: 5 个 PASS

- [ ] **Step 5: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat(tushare): add _ts_code stock→ts_code conversion + tests"
```

---

### Task 2.4: 实现 _period() 转换函数

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py`

- [ ] **Step 1: 加测试**

```python
def test_period_annual():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "annual") == "20201231"


def test_period_half():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "half") == "20200630"


def test_period_q1():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "q1") == "20200331"


def test_period_q3():
    p = TushareProvider.__new__(TushareProvider)
    assert p._period(2020, "q3") == "20200930"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k period`
Expected: 4 个 FAIL

- [ ] **Step 3: 实现 _period**

```python
    @staticmethod
    def _period(year: int, report_type: str) -> str:
        """年份 + 报告期 → tushare 周期字符串（YYYYMMDD）"""
        period_map = {
            "annual": "1231",
            "half": "0630",
            "q1": "0331",
            "q3": "0930",
        }
        suffix = period_map.get(report_type)
        if suffix is None:
            raise ValueError(f"Unknown report_type: {report_type}")
        return f"{year}{suffix}"
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k period`
Expected: 4 个 PASS

- [ ] **Step 5: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat(tushare): add _period year+report_type → YYYYMMDD + tests"
```

---

### Task 2.5: 实现 _fetch() 含重试 + 错误分类

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py`

- [ ] **Step 1: 加测试**

```python
def test_fetch_calls_throttle_and_returns_df(provider):
    """_fetch 调用前 throttle，调用后返回 DataFrame"""
    fake_df = pd.DataFrame({"a": [1, 2]})
    provider._api = MagicMock()
    provider._api.test_endpoint = MagicMock(return_value=fake_df)

    result = provider._fetch("test_endpoint", x=1)
    assert result.equals(fake_df)
    provider._api.test_endpoint.assert_called_once_with(x=1)


def test_fetch_retries_on_network_error_then_succeeds(provider):
    """网络错误指数退避，最终成功"""
    fake_df = pd.DataFrame({"a": [1]})
    provider._api = MagicMock()
    provider._api.test_endpoint = MagicMock(side_effect=[
        ConnectionError("net"),
        ConnectionError("net"),
        fake_df,
    ])
    result = provider._fetch("test_endpoint", x=1)
    assert result.equals(fake_df)
    assert provider._api.test_endpoint.call_count == 3


def test_fetch_does_not_retry_on_permission_error(provider):
    """权限错误不重试，立即抛"""
    provider._api = MagicMock()
    provider._api.test_endpoint = MagicMock(side_effect=Exception("积分不足"))
    with pytest.raises(Exception, match="积分不足"):
        provider._fetch("test_endpoint", x=1)
    assert provider._api.test_endpoint.call_count == 1
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k fetch`
Expected: 3 个 FAIL

- [ ] **Step 3: 实现 _fetch**

```python
    def _fetch(self, api_name: str, **kwargs) -> pd.DataFrame:
        """统一调用入口：throttle + 3 次指数退避（不重试权限错误）"""
        self._connect()
        self._throttle()
        for attempt in range(3):
            try:
                return getattr(self._api, api_name)(**kwargs)
            except Exception as e:
                err_msg = str(e)
                # 权限/积分错误不重试
                if "权限" in err_msg or "积分" in err_msg or "token" in err_msg.lower():
                    raise
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return pd.DataFrame()  # 不应到达此处
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k fetch`
Expected: 3 个 PASS

- [ ] **Step 5: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat(tushare): add _fetch with throttle + exponential backoff + tests"
```

---

### Task 2.6: 实现 _df_to_dict()

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py`

- [ ] **Step 1: 加测试**

```python
def test_df_to_dict_basic(provider):
    """标准 tushare 返回 → {item_name: value}"""
    df = pd.DataFrame({
        "ts_code": ["600519.SH"],
        "end_date": ["20201231"],
        "total_assets": [1000000.0],
        "total_liab": [400000.0],
    })
    result = provider._df_to_dict(df)
    # 包含 financial items
    assert result["total_assets"] == 1000000.0
    assert result["total_liab"] == 400000.0
    # metadata 列被排除
    assert "ts_code" not in result
    assert "end_date" not in result


def test_df_to_dict_empty(provider):
    """空 DataFrame → 空 dict"""
    assert provider._df_to_dict(pd.DataFrame()) == {}


def test_df_to_dict_nan_excluded(provider):
    """NaN 值应被排除"""
    df = pd.DataFrame({"total_assets": [float("nan")], "revenue": [100.0]})
    result = provider._df_to_dict(df)
    assert "total_assets" not in result
    assert result["revenue"] == 100.0
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k df_to_dict`
Expected: 3 个 FAIL

- [ ] **Step 3: 实现 _df_to_dict**

```python
    # tushare 返回字段中需要排除的元数据列
    _META_COLUMNS = {
        "ts_code", "end_date", "ann_date", "f_ann_date", "update_flag",
    }

    def _df_to_dict(self, df: pd.DataFrame) -> Dict[str, float]:
        """DataFrame → {item_name: value}，排除元数据列"""
        if df is None or df.empty:
            return {}
        result = {}
        for col in df.columns:
            if col in self._META_COLUMNS:
                continue
            val = df[col].iloc[0] if len(df) > 0 else None
            if pd.notna(val) and isinstance(val, (int, float)):
                result[col] = float(val)
        return result
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k df_to_dict`
Expected: 3 个 PASS

- [ ] **Step 5: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat(tushare): add _df_to_dict with metadata column exclusion + tests"
```

---

### Task 2.7: 实现 get_balance_sheet / get_income_statement / get_cash_flow

**Files:**
- Modify: `astock_fundamentals/sources/api/tushare_provider.py`

- [ ] **Step 1: 加测试**

```python
def test_get_balance_sheet_calls_balancesheet_endpoint(provider):
    """get_balance_sheet 应调 tushare 的 balancesheet 接口"""
    fake_df = pd.DataFrame({"total_assets": [100.0]})
    provider._api = MagicMock()
    provider._api.balancesheet = MagicMock(return_value=fake_df)
    result = provider.get_balance_sheet("600519", 2020, "annual")
    assert result == {"total_assets": 100.0}
    call_kwargs = provider._api.balancesheet.call_args.kwargs
    assert call_kwargs["ts_code"] == "600519.SH"
    assert call_kwargs["period"] == "20201231"
    assert call_kwargs["report_type"] == "annual"


def test_get_income_statement_calls_income_endpoint(provider):
    fake_df = pd.DataFrame({"total_revenue": [500.0]})
    provider._api = MagicMock()
    provider._api.income = MagicMock(return_value=fake_df)
    result = provider.get_income_statement("000001", 2021, "half")
    assert result == {"total_revenue": 500.0}
    call_kwargs = provider._api.income.call_args.kwargs
    assert call_kwargs["ts_code"] == "000001.SZ"
    assert call_kwargs["period"] == "20210630"


def test_get_cash_flow_calls_cashflow_endpoint(provider):
    fake_df = pd.DataFrame({"c_fr_sale_sg": [800.0]})
    provider._api = MagicMock()
    provider._api.cashflow = MagicMock(return_value=fake_df)
    result = provider.get_cash_flow("300750", 2022, "q3")
    assert result == {"c_fr_sale_sg": 800.0}
    call_kwargs = provider._api.cashflow.call_args.kwargs
    assert call_kwargs["ts_code"] == "300750.SZ"
    assert call_kwargs["period"] == "20220930"


def test_get_balance_sheet_empty_returns_empty_dict(provider):
    """空 DataFrame（报告期未发布）→ 空 dict"""
    provider._api = MagicMock()
    provider._api.balancesheet = MagicMock(return_value=pd.DataFrame())
    assert provider.get_balance_sheet("688981", 2018, "annual") == {}
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v -k "get_balance or get_income or get_cash"`
Expected: 4 个 FAIL

- [ ] **Step 3: 实现 3 个 get_*_statement**

在 tushare_provider.py 的 `TushareProvider` 类内追加：
```python
    def get_balance_sheet(self, stock_code: str, year: int,
                          report_type: str = "annual") -> Optional[Dict]:
        df = self._fetch(
            "balancesheet",
            ts_code=self._ts_code(stock_code),
            period=self._period(year, report_type),
            report_type=report_type,
        )
        return self._df_to_dict(df)

    def get_income_statement(self, stock_code: str, year: int,
                             report_type: str = "annual") -> Optional[Dict]:
        df = self._fetch(
            "income",
            ts_code=self._ts_code(stock_code),
            period=self._period(year, report_type),
            report_type=report_type,
        )
        return self._df_to_dict(df)

    def get_cash_flow(self, stock_code: str, year: int,
                      report_type: str = "annual") -> Optional[Dict]:
        df = self._fetch(
            "cashflow",
            ts_code=self._ts_code(stock_code),
            period=self._period(year, report_type),
            report_type=report_type,
        )
        return self._df_to_dict(df)
```

- [ ] **Step 4: 跑测试验证全部通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider.py -v`
Expected: 全部 PASS（应≥15 个测试）

- [ ] **Step 5: 提交**

```bash
git add astock_fundamentals/sources/api/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat(tushare): implement get_balance_sheet/income_statement/cash_flow + tests"
```

---

### Task 2.8: 导出 TushareProvider from sources.api package

**Files:**
- Modify: `astock_fundamentals/sources/api/__init__.py`

- [ ] **Step 1: 验证当前导入失败**

Run: `PYTHONIOENCODING=utf-8 python -c "from astock_fundamentals.sources.api import TushareProvider"`
Expected: `ImportError: cannot import name 'TushareProvider'`

- [ ] **Step 2: 修改 __init__.py 追加 export**

编辑 `astock_fundamentals/sources/api/__init__.py`：
- 现有内容保留
- 在文件底部追加：
```python
from astock_fundamentals.sources.api.tushare_provider import TushareProvider

__all__ = [
    "BaseApiProvider",
    "AKShareProvider",
    "TushareProvider",
    "WindProvider",
]
```

- [ ] **Step 3: 验证导入成功**

Run: `PYTHONIOENCODING=utf-8 python -c "from astock_fundamentals.sources.api import TushareProvider; print(TushareProvider.__name__)"`
Expected: `TushareProvider`

- [ ] **Step 4: 提交**

```bash
git add astock_fundamentals/sources/api/__init__.py
git commit -m "feat(api): export TushareProvider from sources.api package"
```

---

## Phase 3: tri_channel_cf_lib（提取 + 对比）

### Task 3.1: 创建 tri_channel_cf_lib.py 骨架

**Files:**
- Create: `scripts/tri_channel_cf_lib.py`

- [ ] **Step 1: 写文件骨架**

```python
# -*- coding: utf-8 -*-
"""
Tri-channel CF 对比工具库：tushare vs RDS 现金流/三表对比。

复用 scripts/dual_channel_cf_lib.py 的 normalize/extract/best_match 逻辑，
新增 tushare 提取与三渠道匹配。
"""
from typing import Dict, List

import pandas as pd

from astock_fundamentals.sources.api import TushareProvider
```

- [ ] **Step 2: 提交（先建空文件以便分支管理）**

```bash
git add scripts/tri_channel_cf_lib.py
git commit -m "feat(job5): create tri_channel_cf_lib.py skeleton"
```

---

### Task 3.2: 实现 extract_tushare_year_values

**Files:**
- Modify: `scripts/tri_channel_cf_lib.py`
- Create: `tests/test_tri_channel_cf.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_tri_channel_cf.py`：
```python
# -*- coding: utf-8 -*-
"""tri_channel_cf_lib 单元测试（mock TushareProvider）"""
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "scripts")
from tri_channel_cf_lib import extract_tushare_year_values  # noqa: E402


def test_extract_tushare_year_values_combines_three_statements():
    """extract 应调 provider 的 3 个 get_*，返回带表名前缀的 dict"""
    mock_provider = MagicMock()
    mock_provider.get_balance_sheet.return_value = {"total_assets": 100.0}
    mock_provider.get_income_statement.return_value = {"total_revenue": 500.0}
    mock_provider.get_cash_flow.return_value = {"c_fr_sale_sg": 300.0}

    result = extract_tushare_year_values(mock_provider, "600519", 2020)

    # 应包含 3 个 statement 的 key
    assert any("balance_sheet" in k for k in result)
    assert any("income_statement" in k for k in result)
    assert any("cash_flow" in k for k in result)
    # 值正确
    assert result["[balance_sheet] total_assets"] == 100.0
    assert result["[income_statement] total_revenue"] == 500.0
    assert result["[cash_flow] c_fr_sale_sg"] == 300.0
    # 调了 3 次
    mock_provider.get_balance_sheet.assert_called_once_with("600519", 2020)
    mock_provider.get_income_statement.assert_called_once_with("600519", 2020)
    mock_provider.get_cash_flow.assert_called_once_with("600519", 2020)


def test_extract_tushare_skips_empty_statements():
    """空 dict 语句应被跳过（不报异常）"""
    mock_provider = MagicMock()
    mock_provider.get_balance_sheet.return_value = None
    mock_provider.get_income_statement.return_value = {}
    mock_provider.get_cash_flow.return_value = {"x": 1.0}

    result = extract_tushare_year_values(mock_provider, "600519", 2020)
    assert "x" in result
    assert len([k for k in result if "balance_sheet" in k]) == 0
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v`
Expected: 2 个 FAIL（ImportError: extract_tushare_year_values）

- [ ] **Step 3: 实现 extract_tushare_year_values**

在 `scripts/tri_channel_cf_lib.py` 追加：
```python
def extract_tushare_year_values(provider: TushareProvider, stock_code: str, year: int) -> Dict[str, float]:
    """从 TushareProvider 拉取三表数据，返回带表名前缀的 dict。

    格式：{"[balance_sheet] total_assets": 100.0, ...}
    """
    out: Dict[str, float] = {}
    fetches = [
        ("balance_sheet", provider.get_balance_sheet),
        ("income_statement", provider.get_income_statement),
        ("cash_flow", provider.get_cash_flow),
    ]
    for stmt_type, get_fn in fetches:
        try:
            data = get_fn(stock_code, year)
        except Exception:
            continue
        if not data:
            continue
        for k, v in data.items():
            if isinstance(v, (int, float)):
                out[f"[{stmt_type}] {k}"] = float(v)
    return out
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v`
Expected: 2 个 PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/tri_channel_cf_lib.py tests/test_tri_channel_cf.py
git commit -m "feat(job5): add extract_tushare_year_values with 3-statement union + tests"
```

---

### Task 3.3: 实现 tri_match 复用 classify_diff

**Files:**
- Modify: `scripts/tri_channel_cf_lib.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_tri_channel_cf.py`：
```python
sys.path.insert(0, "scripts")
from tri_channel_cf_lib import tri_match  # noqa: E402
from dual_channel_cf_lib import classify_diff  # noqa: E402


def test_tri_match_against_rds_standard():
    """tri_match 对每个 RDS 项找 tushare 中最佳匹配"""
    rds_standard = {
        "净利润": 1_000_000.0,
        "资产总计": 5_000_000.0,
    }
    tushare_values = {
        "[income_statement] n_income": 1_000_000.0,  # exact match
        "[balance_sheet] total_assets": 5_000_500.0,  # close match
        "[cash_flow] c_fr_sale_sg": 800.0,  # not in RDS
    }
    rows = tri_match(tushare_values, rds_standard)
    assert len(rows) == len(rds_standard)
    # 至少一个 exact
    classes = [r["class"] for r in rows]
    assert "exact" in classes


def test_tri_match_handles_no_match():
    """RDS 有但 tushare 没的项标 no_match"""
    rds = {"x_special_item": 999.0}
    tushare = {"[cash_flow] y": 100.0}
    rows = tri_match(tushare, rds)
    no_match_rows = [r for r in rows if r["class"] == "no_match"]
    assert len(no_match_rows) >= 1
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v -k tri_match`
Expected: 2 个 FAIL

- [ ] **Step 3: 实现 tri_match**

追加到 `scripts/tri_channel_cf_lib.py`：
```python
def tri_match(tushare_values: Dict[str, float], rds_standard: Dict[str, float]) -> List[Dict]:
    """对每个 RDS 项在 tushare 中找最佳匹配，返回分类清单。

    返回 list of:
      {rds_name, rds_value, tushare_label, tushare_value, abs_diff, rel_err_pct, class, color}
    """
    from dual_channel_cf_lib import best_match, classify_diff

    rows = []
    for rds_name, rds_v in rds_standard.items():
        if rds_v is None:
            continue
        ts_label, ts_v, diff, rel = best_match(rds_v, tushare_values)
        cls, color = classify_diff(diff, rel)
        rows.append({
            "rds_name": rds_name,
            "rds_value": rds_v,
            "tushare_label": ts_label,
            "tushare_value": ts_v,
            "abs_diff": diff,
            "rel_err_pct": rel,
            "class": cls,
            "color": color,
        })
    return rows
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v`
Expected: 4 个 PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/tri_channel_cf_lib.py tests/test_tri_channel_cf.py
git commit -m "feat(job5): add tri_match reusing dual_channel classify_diff + tests"
```

---

## Phase 4: tri_channel_cf_download（CLI 入口）

### Task 4.1: 创建 CLI 骨架 + token 解析

**Files:**
- Create: `scripts/tri_channel_cf_download.py`

- [ ] **Step 1: 写骨架**

```python
# -*- coding: utf-8 -*-
"""
Tri-channel CF 比对器：tushare vs RDS 逐项对比 + HTML 报告。

用法：
  python scripts/tri_channel_cf_download.py --stock 600519 --year 2020
  python scripts/tri_channel_cf_download.py --stocks-file stocks.txt --year 2022
  TUSHARE_TOKEN=xxx python scripts/tri_channel_cf_download.py --stock 600519 --year 2020
"""
import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from astock_fundamentals.sources.api import TushareProvider  # noqa: E402
from astock_fundamentals.sources.rds.rds_loader import RdsLoader  # noqa: E402

OUT_DIR = "data/exports_v2/cash_flow_tri_channel"
RDS_DIR = "D:/Research/Quant/SETL/cninfo/data_backup"
os.makedirs(OUT_DIR, exist_ok=True)


def resolve_token(args_token: str = "") -> str:
    """token 解析优先级：--token > TUSHARE_TOKEN env > 错误退出"""
    if args_token:
        return args_token
    env_token = os.environ.get("TUSHARE_TOKEN", "")
    if env_token:
        return env_token
    sys.exit("ERROR: Tushare token required. Pass --token or set TUSHARE_TOKEN env.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", help="single stock code, e.g. 600519")
    ap.add_argument("--stocks-file", help="text file with one stock code per line")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--token", default="", help="Tushare token (overrides env)")
    args = ap.parse_args()

    token = resolve_token(args.token)
    print(f"Token resolved, length: {len(token)}")

    # process_stock / build_merged_csv / build_report_html 在后续 tasks 添加
```

- [ ] **Step 2: 验证 token 缺失时报错退出**

Run: `unset TUSHARE_TOKEN; PYTHONIOENCODING=utf-8 python scripts/tri_channel_cf_download.py --stock 600519 --year 2020 2>&1 | tail -3`
Expected: `ERROR: Tushare token required...`

- [ ] **Step 3: 提交**

```bash
git add scripts/tri_channel_cf_download.py
git commit -m "feat(job5): create tri_channel_cf_download.py CLI skeleton with token resolution"
```

---

### Task 4.2: 实现 load_rds_standard() 辅助函数

**Files:**
- Modify: `scripts/tri_channel_cf_download.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_tri_channel_cf.py` 追加：
```python
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, "scripts")
import tri_channel_cf_download  # noqa: E402


def test_load_rds_standard_uses_rds_loader():
    """load_rds_standard 调用 RdsLoader.load_stock_data_tidy"""
    with patch.object(tri_channel_cf_download, "RdsLoader") as mock_cls:
        mock_loader = MagicMock()
        mock_loader.load_stock_data_tidy.return_value = [
            {"item_name": "净利润", "value": 100.0, "report_type": "annual"},
            {"item_name": "其他项", "value": 50.0, "report_type": "annual"},
        ]
        mock_cls.return_value = mock_loader

        result = tri_channel_cf_download.load_rds_standard("600519", 2020)

    # 应调 3 次（BS/IS/CF）
    assert mock_loader.load_stock_data_tidy.call_count == 3
    # 应包含前缀避免重名
    assert any("balance_sheet" in k.lower() for k in result)
    assert any("income_statement" in k.lower() for k in result)
    assert any("cash_flow" in k.lower() for k in result)
    # 值正确（净利润=100）
    income_keys = [k for k in result if "income_statement" in k and "净利润" in k]
    assert len(income_keys) == 1
    assert result[income_keys[0]] == 100.0
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v -k load_rds`
Expected: FAIL（AttributeError: load_rds_standard）

- [ ] **Step 3: 实现 load_rds_standard**

追加到 `scripts/tri_channel_cf_download.py`：
```python
def load_rds_standard(stock_code: str, year: int) -> Dict[str, float]:
    """用 RdsLoader 加载 3 张报表的 annual 数据，返回带表名前缀的 dict"""
    loader = RdsLoader(RDS_DIR)
    out: Dict[str, float] = {}
    for stmt_type in ["balance_sheet", "income_statement", "cash_flow"]:
        try:
            tidy = loader.load_stock_data_tidy(stock_code, year, stmt_type)
        except Exception:
            continue
        for r in tidy:
            if r.get("report_type") != "annual":
                continue
            v = r.get("value")
            if v is None:
                continue
            name = r.get("item_name", "")
            if name:
                out[f"[{stmt_type}] {name}"] = float(v)
    return out
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v -k load_rds`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/tri_channel_cf_download.py tests/test_tri_channel_cf.py
git commit -m "feat(job5): add load_rds_standard helper + tests"
```

---

### Task 4.3: 实现 process_stock()

**Files:**
- Modify: `scripts/tri_channel_cf_download.py`

- [ ] **Step 1: 写失败测试**

```python
def test_process_stock_returns_status_dict():
    """process_stock 返回 status dict 包含 counts 与 status 字段"""
    with patch.object(tri_channel_cf_download, "TushareProvider") as mock_ts_cls, \
         patch.object(tri_channel_cf_download, "RdsLoader") as mock_rds_cls:
        # Mock tushare
        mock_ts = MagicMock()
        mock_ts.get_balance_sheet.return_value = {"total_assets": 100.0}
        mock_ts.get_income_statement.return_value = {"total_revenue": 200.0}
        mock_ts.get_cash_flow.return_value = {}
        mock_ts_cls.return_value = mock_ts

        # Mock RDS
        mock_rds = MagicMock()
        mock_rds.load_stock_data_tidy.return_value = []
        mock_rds_cls.return_value = mock_rds

        # 直接调 process_stock 而不通过 main
        with patch.object(tri_channel_cf_download, "build_merged_csv"), \
             patch.object(tri_channel_cf_download, "build_report_html"):
            result = tri_channel_cf_download.process_stock("600519", 2020, token="fake")

    assert result["stock"] == "600519"
    assert result["year"] == 2020
    assert result["status"] == "OK"
    assert "counts" in result
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v -k process_stock`
Expected: FAIL

- [ ] **Step 3: 实现 process_stock**

追加到 `scripts/tri_channel_cf_download.py`：
```python
def process_stock(stock: str, year: int, token: str) -> Dict:
    """单只股票 × 单年处理：拉 tushare + RDS + 比对 + 输出报告"""
    try:
        provider = TushareProvider(token=token)
    except Exception as e:
        return {"stock": stock, "year": year, "status": "TOKEN_ERROR", "error": str(e)}

    try:
        tushare_values = extract_tushare_year_values(provider, stock, year)
    except Exception as e:
        return {"stock": stock, "year": year, "status": "EXCEPTION", "error": str(e)}

    if not tushare_values:
        return {"stock": stock, "year": year, "status": "NO_TUSHARE_DATA"}

    rds_standard = load_rds_standard(stock, year)
    if not rds_standard:
        return {"stock": stock, "year": year, "status": "NO_RDS_DATA",
                "tushare_field_count": len(tushare_values)}

    rows = tri_match(tushare_values, rds_standard)

    merged_csv = os.path.join(OUT_DIR, f"{stock}_{year}_tushare_vs_rds.csv")
    report_html = os.path.join(OUT_DIR, f"{stock}_{year}_tushare_vs_rds.html")
    build_merged_csv(stock, year, rows, merged_csv)
    build_report_html(stock, year, rows, tushare_values, report_html)

    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {
        "stock": stock, "year": year, "status": "OK",
        "counts": counts, "merged_csv": merged_csv, "report_html": report_html,
    }
```

- [ ] **Step 4: 跑测试验证通过（需先 stub build_*_csv/html）**

测试中已 patch `build_merged_csv` 和 `build_report_html`，可以 PASS：
Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v -k process_stock`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/tri_channel_cf_download.py tests/test_tri_channel_cf.py
git commit -m "feat(job5): add process_stock end-to-end function + tests"
```

---

### Task 4.4: 实现 build_merged_csv + build_report_html（双层警告）

**Files:**
- Modify: `scripts/tri_channel_cf_download.py`

- [ ] **Step 1: 实现 build_merged_csv**

```python
def build_merged_csv(stock: str, year: int, rows: List[Dict], out_path: str) -> None:
    """合并表：每行一个 RDS 项 + 对应 tushare 匹配 + class"""
    import pandas as pd
    df = pd.DataFrame(rows)
    df.insert(0, "stock_code", stock)
    df.insert(1, "report_year", year)
    df.insert(2, "source", "tushare_vs_rds")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
```

- [ ] **Step 2: 实现 build_report_html（含双层警告）**

```python
def build_report_html(stock: str, year: int, rows: List[Dict],
                      tushare_values: Dict[str, float], out_path: str) -> None:
    """生成 HTML 报告，含双层警告横幅 + 彩色对比表"""
    color_css = {
        "exact": "#c8eac8", "sub_yuan": "#f4e4b4", "rounded": "#ffe0a3",
        "large_error": "#f5c2c2", "no_match": "#e8e8e8",
    }
    body = []
    for r in rows:
        bg = color_css.get(r["class"], "#fff")
        rds_v = f"{r['rds_value']:,.2f}" if r['rds_value'] is not None else ""
        ts_v = f"{r['tushare_value']:,.2f}" if r['tushare_value'] is not None else ""
        diff = f"{r['abs_diff']:,.2f}" if r['abs_diff'] is not None else ""
        rel = f"{r['rel_err_pct']:.4f}%" if r['rel_err_pct'] is not None else ""
        body.append(
            f'<tr style="background:{bg}">'
            f'<td>{r["rds_name"]}</td><td class="num">{rds_v}</td>'
            f'<td>{r["tushare_label"] or ""}</td><td class="num">{ts_v}</td>'
            f'<td class="num">{diff}</td><td class="num">{rel}</td>'
            f'<td>{r["class"]}</td></tr>'
        )
    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    summary_line = " · ".join(f"{k}={v}" for k, v in counts.items())

    # 双层警告
    warning_banner1 = """<div class="summary" style="border-left-color:#d73a49;background:#ffe0e0;">
<strong>⚠ 警告 1：</strong>即使 tushare 与 RDS exact_rate 很高，两者可能是同一上游（巨潮资讯）的两次提取。
差异通常源于字段命名 / 精度（rounded 类）。
</div>"""
    warning_banner2 = f"""<div class="summary" style="border-left-color:#0366d6;background:#e3f2fd;">
<strong>ℹ 警告 2：</strong>tushare 标榜源头=巨潮资讯（与 RDS 同源）。本次对比共 {sum(counts.values())} 项；
如果 exact 占比 < 50%，假设"同源"不成立，tushare 可能是第三方转载。
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{stock} {year} tushare vs RDS</title>
<style>
body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; padding: 20px; }}
h1 {{ color: #1a1a2e; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ padding: 6px 10px; border: 1px solid #e1e4e8; }}
th {{ background: #1a1a2e; color: #fff; }}
.num {{ text-align: right; font-family: Consolas, monospace; }}
.summary {{ padding: 12px; border-left: 4px solid; margin: 12px 0; }}
</style></head><body>
<h1>{stock} - {year} tushare vs RDS 逐项对比</h1>
{warning_banner1}
{warning_banner2}
<div class="summary" style="background:#fff8db;border-left-color:#f0ad4e;">
<strong>项目分布：</strong> {summary_line}<br>
<strong>tushare 字段总数：</strong> {len(tushare_values)}
</div>
<table>
<thead><tr><th>RDS 项目</th><th>RDS 值</th><th>tushare 匹配字段</th><th>tushare 值</th>
<th>差异(元)</th><th>相对误差</th><th>类别</th></tr></thead>
<tbody>{"".join(body)}</tbody>
</table>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
```

- [ ] **Step 3: 加测试**

```python
def test_build_report_html_contains_double_warnings():
    """build_report_html 应含双层警告横幅"""
    import tempfile
    rows = [{"rds_name": "净利润", "rds_value": 100.0, "tushare_label": "x",
             "tushare_value": 100.0, "abs_diff": 0.0, "rel_err_pct": 0.0,
             "class": "exact", "color": "green"}]
    tushare_values = {"[income_statement] x": 100.0}
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        path = f.name
    try:
        tri_channel_cf_download.build_report_html("600519", 2020, rows, tushare_values, path)
        with open(path, encoding="utf-8") as f:
            html = f.read()
        assert "警告 1" in html
        assert "警告 2" in html
        assert "exact" in html
    finally:
        os.unlink(path)
```

- [ ] **Step 4: 跑测试验证通过**

Run: `PYTHONIOENCODING=utf-8 pytest tests/test_tri_channel_cf.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add scripts/tri_channel_cf_download.py tests/test_tri_channel_cf.py
git commit -m "feat(job5): add build_merged_csv + build_report_html (双层警告) + tests"
```

---

### Task 4.5: 完整 main() — 批量 + run_summary

**Files:**
- Modify: `scripts/tri_channel_cf_download.py`

- [ ] **Step 1: 替换 main() 函数**

```python
def main():
    import json
    import time

    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", help="single stock code, e.g. 600519")
    ap.add_argument("--stocks-file", help="text file with one stock code per line")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--token", default="", help="Tushare token (overrides env)")
    args = ap.parse_args()

    token = resolve_token(args.token)
    print(f"Token resolved, length: {len(token)}")

    if args.stock:
        stocks = [args.stock]
    elif args.stocks_file:
        with open(args.stocks_file) as f:
            stocks = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    else:
        sys.exit("ERROR: --stock or --stocks-file required")

    results = []
    for code in stocks:
        r = process_stock(code, args.year, token)
        results.append(r)
        print(f"  [{code}] {r['status']}: {r.get('counts', r.get('error', ''))}")
        time.sleep(0.5)  # 额外安全余量

    out = os.path.join(OUT_DIR, f"_run_summary_{args.year}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证 CLI 帮助正常**

Run: `PYTHONIOENCODING=utf-8 python scripts/tri_channel_cf_download.py --help 2>&1 | head -10`
Expected: 显示 usage 信息（不需 token，因为 main 没真正调 API）

- [ ] **Step 3: 提交**

```bash
git add scripts/tri_channel_cf_download.py
git commit -m "feat(job5): add main() with batch processing + run_summary output"
```

---

## Phase 5: 端到端 — 需要真实 token

### Task 5.1: live smoke test（需用户提供 token）

**Files:**
- Create: `tests/test_tushare_provider_live.py`

- [ ] **Step 1: 用户提供 token**

通过环境变量：
```bash
export TUSHARE_TOKEN=<user-provided-token>
```

（用户将独立提供 token）

- [ ] **Step 2: 写 live test（pytest.skip 当 token 缺失）**

```python
# -*- coding: utf-8 -*-
"""TushareProvider live smoke test（需 TUSHARE_TOKEN 环境变量）

使用方式：
  export TUSHARE_TOKEN=your_token
  pytest tests/test_tushare_provider_live.py -v
"""
import os
import sys
import time

import pandas as pd
import pytest

sys.path.insert(0, "astock_fundamentals")
from astock_fundamentals.sources.api import TushareProvider


@pytest.mark.skipif(
    not os.environ.get("TUSHARE_TOKEN"),
    reason="TUSHARE_TOKEN not set — skipping live test",
)
def test_live_get_cash_flow_one_stock():
    """live: 1 只股 × 1 年 CF（验证 token 有效 + 字段非空）"""
    token = os.environ["TUSHARE_TOKEN"]
    provider = TushareProvider(token=token)
    result = provider.get_cash_flow("600519", 2020, "annual")
    assert result, "live call returned empty dict"
    assert isinstance(result, dict)
    # 应有 c_fr_sale_sg 之类的字段
    assert any("c_fr" in k or "n_cash" in k for k in result), \
        f"unexpected keys: {list(result.keys())[:5]}"
    print(f"\n  Got {len(result)} fields: {list(result.keys())[:5]}")
```

- [ ] **Step 3: 跑测试（需 TUSHARE_TOKEN）**

Run: `TUSHARE_TOKEN=xxx PYTHONIOENCODING=utf-8 pytest tests/test_tushare_provider_live.py -v`
Expected:
- 若 token 缺失：SKIP
- 若 token 有效：PASS（拿到 ≥1 个 CF 字段）

- [ ] **Step 4: 报告结果给用户**

向用户报告：
- token 有效？拿到的字段数？
- 速率（请求耗时）？
- 是否需要调整 rate_limit_sleep？

- [ ] **Step 5: 提交**

```bash
git add tests/test_tushare_provider_live.py
git commit -m "test(tushare): add live smoke test (skip-on-no-token)"
```

---

### Task 5.2: 小批量 5-10 只股对比（需 token）

**Files:**
- Create: `tmp/test_stocks_tushare.txt`

- [ ] **Step 1: 用户提供 token**

```bash
export TUSHARE_TOKEN=<user-provided-token>
```

- [ ] **Step 2: 创建测试股票清单**

```bash
cat > tmp/test_stocks_tushare.txt <<'EOF'
600519
600887
000651
688981
300750
600036
EOF
```

- [ ] **Step 3: 跑 tri-channel 对比（2020 年）**

Run: `TUSHARE_TOKEN=xxx PYTHONIOENCODING=utf-8 python scripts/tri_channel_cf_download.py --stocks-file tmp/test_stocks_tushare.txt --year 2020 2>&1 | tail -20`
Expected: 6 只股票全部 status=OK，生成 6 个 HTML 报告

- [ ] **Step 4: 验证假设"源头=巨潮资讯"**

Run: `PYTHONIOENCODING=utf-8 python -c "
import json
with open('data/exports_v2/cash_flow_tri_channel/_run_summary_2020.json',encoding='utf-8') as f:
    summary = json.load(f)
for s in summary:
    if s['status'] == 'OK':
        c = s['counts']
        total = sum(c.values())
        exact = c.get('exact', 0)
        rate = exact / total * 100 if total else 0
        print(f'  {s[\"stock\"]}: exact={exact}/{total} ({rate:.1f}%)')
"`
Expected: 
- 若 rate > 80%：源头假设成立
- 若 rate < 50%：源头假设不成立
- 50-80%：需进一步调查

- [ ] **Step 5: 提交运行产物**

```bash
git add data/exports_v2/cash_flow_tri_channel/ tmp/test_stocks_tushare.txt
git commit -m "test(tushare): small-batch 6-stock tushare vs RDS comparison (2020)"
```

---

### Task 5.3: 写 6 只股对比基线报告

**Files:**
- Create: `docs/audit/2026-06-12-tushare-vs-rds-baseline.md`

- [ ] **Step 1: 从 _run_summary_2020.json 生成报告**

模板（用户填写实际数字）：
```markdown
# Tushare vs RDS 对比基线报告

**日期**：2026-06-12
**样本**：6 只 A 股 × 2020 年报 × 3 表
**目的**：验证 Tushare 标榜"源头=巨潮资讯（与 RDS 同源）"声明

## 1. 汇总

| 股票 | exact | large_error | total | exact_rate |
|------|---:|---:|---:|---:|
| (实际数据) | ... | ... | ... | ... |

## 2. 假设检验

- **H₀**: tushare 源头 = 巨潮资讯（与 RDS 同源）
- **结论**: (基于 exact_rate 是否 > 80%)

## 3. 详细分类

- exact 占 (XX%)
- sub_yuan 占 (XX%)
- rounded 占 (XX%)
- large_error 占 (XX%)
- no_match 占 (XX%)

## 4. 已知差异

（如有：列出"rds 字段名 vs tushare 字段名"映射差异的 top 5）

## 5. 下一步

（基于结论：扩展到 5K 全量 / 修复差异 / 不再使用 tushare）
```

- [ ] **Step 2: 提交**

```bash
git add docs/audit/2026-06-12-tushare-vs-rds-baseline.md
git commit -m "docs(tushare): baseline report for tushare vs RDS comparison (6 stocks, 2020)"
```

---

## Phase 6: 5K 全量拉取（独立任务，可选）

### Task 6.1: download_tushare_full.py 骨架

**Files:**
- Create: `scripts/download_tushare_full.py`

- [ ] **Step 1: 写脚本骨架（含 checkpoint 断点续传）**

```python
# -*- coding: utf-8 -*-
"""
5,000 只 A 股全量 tushare 拉取脚本（拿到 token 后手动跑）。

用法：
  TUSHARE_TOKEN=xxx python scripts/download_tushare_full.py --years 2020-2022

输出：
  data/exports_v2/tushare_full/{ts_code}_{year}_{stmt_type}.csv
  data/tushare_full_checkpoint.json（断点续传）
"""
import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from astock_fundamentals.sources.api import TushareProvider  # noqa: E402

OUT_DIR = "data/exports_v2/tushare_full"
CHECKPOINT_PATH = "data/tushare_full_checkpoint.json"
os.makedirs(OUT_DIR, exist_ok=True)


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            return set(tuple(x) for x in json.load(f).get("done", []))
    return set()


def save_checkpoint(done):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(list(done))}, f, ensure_ascii=False, indent=2)


def get_stock_list():
    """获取 A 股全量股票清单（用 akshare）"""
    import akshare as ak
    df = ak.stock_zh_a_spot_em()
    return df["代码"].astype(str).tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2020-2022", help="year range, e.g. 2020-2022")
    ap.add_argument("--resume", action="store_true", help="resume from checkpoint")
    ap.add_argument("--rate-limit-sleep", type=float, default=0.4)
    args = ap.parse_args()

    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        sys.exit("ERROR: TUSHARE_TOKEN env required")

    years = list(range(int(args.years.split("-")[0]),
                       int(args.years.split("-")[1]) + 1))
    stocks = get_stock_list()
    provider = TushareProvider(token=token, rate_limit_sleep=args.rate_limit_sleep)
    done = load_checkpoint() if args.resume else set()
    print(f"Total stocks: {len(stocks)}, years: {years}, done: {len(done)}")

    stmt_methods = [
        ("balance_sheet", provider.get_balance_sheet),
        ("income_statement", provider.get_income_statement),
        ("cash_flow", provider.get_cash_flow),
    ]

    success = 0
    failed = 0
    for i, stock in enumerate(stocks):
        ts_code = TushareProvider._ts_code(stock)
        for year in years:
            for stmt_type, get_fn in stmt_methods:
                key = (stock, str(year), stmt_type)
                if key in done:
                    continue
                try:
                    data = get_fn(stock, year)
                except Exception as e:
                    failed += 1
                    done.add(key)  # 即使失败也标记，避免重试
                    continue
                if data:
                    df = pd.DataFrame(list(data.items()), columns=["item", "value"])
                    df.insert(0, "ts_code", ts_code)
                    df.insert(1, "year", year)
                    df.insert(2, "statement_type", stmt_type)
                    out_path = os.path.join(OUT_DIR, f"{ts_code}_{year}_{stmt_type}.csv")
                    df.to_csv(out_path, index=False, encoding="utf-8-sig")
                    success += 1
                done.add(key)

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(stocks)}, success={success}, failed={failed}")
            save_checkpoint(done)

    save_checkpoint(done)
    print(f"\nDone: {success} success, {failed} failed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 提交（不实际跑）**

```bash
git add scripts/download_tushare_full.py
git commit -m "feat(tushare): add 5K full-pull script with checkpoint resume"
```

---

### Task 6.2: 5K 全量拉取执行（手动）

- [ ] **Step 1: 用户决定是否运行 5K 全量拉取**

向用户报告：
- 5K × 3 年 × 3 表 ≈ 45,000 请求
- 估算 ~5 小时（sleep 0.4s）
- 期间需要电脑稳定联网
- 数据量约 5,000 × 9 个 CSV ≈ 30MB

询问：是否现在运行？或者拆成 3 次（每年 1 次）？

- [ ] **Step 2: 执行拉取**

```bash
nohup python scripts/download_tushare_full.py --years 2020-2022 --resume > tmp/tushare_full.log 2>&1 &
echo "PID: $!"
```

或者按用户决定的方式分批：
```bash
python scripts/download_tushare_full.py --years 2020-2020
python scripts/download_tushare_full.py --years 2021-2021
python scripts/download_tushare_full.py --years 2022-2022
```

- [ ] **Step 3: 写拉取摘要**

完成后写 `docs/audit/2026-06-12-tushare-full-pull-summary.md`：
```markdown
# Tushare 5K 全量拉取摘要

**日期**：2026-06-12
**耗时**：(实际)
**成功率**：(X/Y)
**失败股票清单**：(如有)

## 字段统计

- BS: 平均 X 字段/股
- IS: 平均 Y 字段/股
- CF: 平均 Z 字段/股
```

- [ ] **Step 4: 提交**

```bash
git add data/exports_v2/tushare_full/ docs/audit/2026-06-12-tushare-full-pull-summary.md data/tushare_full_checkpoint.json
git commit -m "feat(tushare): 5K full pull complete + summary report"
```

---

## 最终验证 Checklist

完成所有 task 后：
- [ ] `pytest tests/ -v` 全部 PASS
- [ ] CLAUDE.md §0.6 禁忌未踩
- [ ] 没有擅自切换方案
- [ ] 每个 task 独立 commit
- [ ] docs/audit/2026-06-12-tushare-vs-rds-baseline.md 存在
- [ ] 分支已 push
- [ ] PR 创建（用户提供后）

## 阻塞汇报模板

| 情况 | 行动 |
|------|------|
| Token 失效 | "TUSHARE_TOKEN 报 (X) 错误，请检查。" |
| 403 限流 | "已 sleep 0.4s 仍触发 403，建议 sleep 调到 0.6。" |
| 权限不足 | "调 (X) 接口报积分不足，tushare 2000 档位下该接口不可用。" |
| 股票不存在 | "tushare 不覆盖 (X) 股票（可能退市或未上市）。" |
| 网络错误 | "网络超时，已重试 3 次仍失败。" |
