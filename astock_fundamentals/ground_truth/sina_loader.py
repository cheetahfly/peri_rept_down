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