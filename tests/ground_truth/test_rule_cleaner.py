# -*- coding: utf-8 -*-
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


def test_load_real_yaml_rules_has_sina_block():
    rules = load_cleaning_rules()
    assert hasattr(rules, "aliases")
    assert isinstance(rules.aggregations, dict)


def test_sina_aliases_2019_2022_loaded_into_balance_sheet():
    rules = load_cleaning_rules()
    # After Task 7 added the sina_aliases_2019_2022 block,
    # load_cleaning_rules should merge it into rules.aliases[statement_type]
    assert "balance_sheet" in rules.aliases