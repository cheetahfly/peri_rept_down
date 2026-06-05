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
    code = str(stock_code)
    # 5-digit HK codes (02020, 00700, 09988, etc.) are always HK
    if len(code) == 5:
        return "HK"
    code = code.zfill(6)
    if code.startswith(("600", "601", "603", "688")):
        return "SH"
    if code.startswith(("000", "002", "300", "200", "080")):
        return "SZ"
    return "HK"


# Statement type to (module function, kind) mapping
# kind is 'a' (A股) or 'hk' (港股)
STATEMENT_API = {
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
            for api_name in set(STATEMENT_API.values()):
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
        per_name = {nm: {} for nm in name_to_key}
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
        api_name = STATEMENT_API[(statement_type, kind)]
        if api_name not in self._skill_funcs:
            raise RuntimeError(f"GuosenLoader: skill function {api_name} not loaded")
        fn = self._skill_funcs[api_name]
        if kind == "a":
            response = fn(stock_code, market, "Q0", None, 1)
        else:
            response = fn(stock_code, None, None, 1)
        return self._api_response_to_df(response)