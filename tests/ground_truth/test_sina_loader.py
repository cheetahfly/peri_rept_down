# -*- coding: utf-8 -*-
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