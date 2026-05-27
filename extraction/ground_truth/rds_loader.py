# -*- coding: utf-8 -*-
"""
RDS ground truth data loader.

Loads CNINFO structured financial data from RDS files and maps
field codes (F006N) to Chinese financial statement item names.

IMPORTANT: Each statement type has its own field code mapping!
- F006N in income_statement = "其中：营业收入"
- F006N in balance_sheet = "货币资金"
- F006N in cash_flow = "销售商品、提供劳务收到的现金"
"""

import json
import os
from typing import Dict, List, Optional, Tuple

import pyreadr


# Financial company stock codes (use _f tables)
FINANCIAL_CODES = {
    "000001", "601318", "600036",  # Banks and insurance
}

# Table mapping: (is_financial, statement_type) -> filename
TABLE_MAP = {
    (True, "income_statement"): "pl_f.rds",
    (True, "balance_sheet"): "b_f.rds",
    (True, "cash_flow"): "cf_f.rds",
    (False, "income_statement"): "pl_o.rds",
    (False, "balance_sheet"): "b_o.rds",
    (False, "cash_flow"): "cf_o.rds",
}

# Meta columns (not financial data)
META_COLS = {"SECCODE", "SECNAME", "ORGNAME", "DECLAREDATE", "STARTDATE", "ENDDATE", "MEMO"}

# Map statement type to report_type for period filtering
PERIOD_TO_REPORT_TYPE = {
    "12-31": "annual",
    "06-30": "half_year",
    "03-31": "quarter_q1",
    "09-30": "quarter_q3",
}


class RdsLoader:
    """Load and parse CNINFO RDS ground truth data.

    IMPORTANT: Each statement type has its own field code mapping!
    - F006N in income_statement = "其中：营业收入"
    - F006N in balance_sheet = "货币资金"
    - F006N in cash_flow = "销售商品、提供劳务收到的现金"
    """

    def __init__(self, data_dir: str, decode_map_path: str = None):
        self.data_dir = data_dir
        self._decode_maps = self._load_decode_maps(decode_map_path)
        self._cache: Dict[str, object] = {}

    def _load_decode_maps(self, path: str = None) -> Dict[str, Dict[str, str]]:
        """Load decode mappings by statement type from decode_mappings_by_type.json."""
        if path is None:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.path.join(base, "data", "decode_mappings_by_type.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback to old single mapping
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            fallback_path = os.path.join(base, "data", "decode_mappings.json")
            with open(fallback_path, "r", encoding="utf-8") as f:
                single_map = json.load(f)
                return {
                    "income_statement": single_map,
                    "balance_sheet": single_map,
                    "cash_flow": single_map,
                }

    def _load_rds(self, filename: str):
        if filename not in self._cache:
            path = os.path.join(self.data_dir, filename)
            result = pyreadr.read_r(path)
            self._cache[filename] = list(result.values())[0]
        return self._cache[filename]

    def _is_financial(self, stock_code: str) -> bool:
        return stock_code in FINANCIAL_CODES

    def _field_to_name(self, field_code: str, statement_type: str) -> Optional[str]:
        """Get Chinese name for a field code based on statement type."""
        decode_map = self._decode_maps.get(statement_type, {})
        return decode_map.get(field_code)

    def load_stock_data(
        self,
        stock_code: str,
        year: int,
        statement_type: str,
    ) -> Dict[str, float]:
        """
        Load ground truth data for a specific stock/year/statement.

        Returns: {item_name: value} where item_name is Chinese and value is in yuan.
        """
        is_fin = self._is_financial(stock_code)
        filename = TABLE_MAP.get((is_fin, statement_type))
        if filename is None:
            return {}

        df = self._load_rds(filename)
        subset = df[df["SECCODE"] == stock_code]

        # Filter by year - find the row closest to year-end
        target_date = f"{year}-12-31"
        row = subset[subset["ENDDATE"] == target_date]
        if len(row) == 0:
            # Try Q1 of next year as proxy for annual
            target_date = f"{year + 1}-03-31"
            row = subset[subset["ENDDATE"] == target_date]
        if len(row) == 0:
            return {}

        row = row.iloc[0]

        # Get the decode map for this statement type
        decode_map = self._decode_maps.get(statement_type, {})

        # Extract data columns (F-fields) and map to Chinese names
        data = {}
        for col in df.columns:
            if col in META_COLS:
                continue
            # Only load fields that have a mapping in this statement type's decode map
            if col not in decode_map:
                continue
            val = row[col]
            if val is not None and str(val) != "nan":
                name = decode_map[col]
                try:
                    data[name] = float(val)
                except (ValueError, TypeError):
                    pass

        return data

    def load_stock_all_types(
        self, stock_code: str, year: int
    ) -> Dict[str, Dict[str, float]]:
        """Load all statement types for a stock/year."""
        result = {}
        for st in ["income_statement", "balance_sheet", "cash_flow"]:
            data = self.load_stock_data(stock_code, year, st)
            if data:
                result[st] = data
        return result

    def list_periods(self, stock_code: str) -> List[str]:
        """List all available periods for a stock in the RDS."""
        is_fin = self._is_financial(stock_code)
        filename = TABLE_MAP.get((is_fin, "income_statement"))
        if filename is None:
            return []

        df = self._load_rds(filename)
        subset = df[df["SECCODE"] == stock_code]
        return sorted(subset["ENDDATE"].unique().tolist())

    def list_available_years(self, stock_code: str) -> List[int]:
        """List years with annual data available."""
        periods = self.list_periods(stock_code)
        years = set()
        for p in periods:
            if hasattr(p, "year"):
                years.add(p.year)
            elif isinstance(p, str) and len(p) >= 4:
                try:
                    years.add(int(p[:4]))
                except ValueError:
                    pass
        return sorted(years)
