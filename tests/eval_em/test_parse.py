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


# ---- check_completeness ----

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
    for t in ("balance_sheet", "income_statement", "cash_flow"):
        (tmp_path / t).mkdir(parents=True, exist_ok=True)
        (tmp_path / t / "600000.csv").write_text("h\n", encoding="utf-8")
    (tmp_path / "balance_sheet" / "300001.csv").write_text("h\n", encoding="utf-8")
    # 688001: 无

    result = check_completeness(sample, str(tmp_path))
    assert result["total_stocks"] == 3
    assert result["stocks_with_data"] == 2
    assert result["complete_stocks"] == 1
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
    for t in ("balance_sheet", "income_statement", "cash_flow"):
        (tmp_path / t / "600000.csv").write_text("h\n", encoding="utf-8")
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