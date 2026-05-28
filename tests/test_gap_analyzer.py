# -*- coding: utf-8 -*-
"""Tests for GapAnalyzer class."""

from extraction.ground_truth.gap_analyzer import GapAnalyzer


def _make_report(missing_items=None, unmatched_items=None, value_diffs=None):
    """Helper to build a minimal detailed report dict."""
    return {
        "stock_code": "600519",
        "year": 2020,
        "statement_type": "balance_sheet",
        "coverage": 0.5,
        "value_accuracy": 0.5,
        "missing_items": missing_items or [],
        "unmatched_items": unmatched_items or [],
        "value_diffs": value_diffs or [],
    }


class TestGapAnalyzerAnalyze:
    """Tests for GapAnalyzer.analyze()."""

    def test_returns_empty_for_empty_report(self):
        ga = GapAnalyzer()
        report = _make_report()
        assert ga.analyze(report) == []

    def test_suggests_alias_for_similar_names(self):
        ga = GapAnalyzer(min_similarity=0.5)
        report = _make_report(
            missing_items=[{"name": "货币资金", "code": "F033N", "expected_value": 1000}],
            unmatched_items=[{"name": "货币资金合计", "code": None, "value": 1000}],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s["type"] == "alias_suggestion"
        assert s["standard_name"] == "货币资金"
        assert "货币资金合计" in s["variants"]

    def test_no_suggestion_when_below_threshold(self):
        ga = GapAnalyzer(min_similarity=0.99)
        report = _make_report(
            missing_items=[{"name": "货币资金"}],
            unmatched_items=[{"name": "应收账款"}],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 0

    def test_multiple_missing_items(self):
        ga = GapAnalyzer(min_similarity=0.5)
        report = _make_report(
            missing_items=[
                {"name": "货币资金", "code": "F033N"},
                {"name": "应收账款", "code": "F034N"},
            ],
            unmatched_items=[
                {"name": "货币资金合计", "code": None},
                {"name": "应收账款净额", "code": None},
            ],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 2
        names = {s["standard_name"] for s in suggestions}
        assert "货币资金" in names
        assert "应收账款" in names

    def test_unit_suggestion_for_10000x_ratio(self):
        ga = GapAnalyzer()
        report = _make_report(
            value_diffs=[{
                "name": "营业收入",
                "code": "F001N",
                "ground_truth_value": 100000000.0,
                "extracted_value": 10000.0,
            }],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s["type"] == "unit_suggestion"
        assert s["suggested_unit"] == "万元"
        assert s["reason"] == "value_off_by_10000x"

    def test_unit_suggestion_for_inverse_ratio(self):
        ga = GapAnalyzer()
        report = _make_report(
            value_diffs=[{
                "name": "总资产",
                "code": "F050N",
                "ground_truth_value": 100.0,
                "extracted_value": 1000000.0,
            }],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s["type"] == "unit_suggestion"
        assert s["suggested_unit"] == "亿元"
        assert s["reason"] == "value_off_by_1billion"

    def test_no_unit_suggestion_for_normal_diff(self):
        ga = GapAnalyzer()
        report = _make_report(
            value_diffs=[{
                "name": "存货",
                "code": "F040N",
                "ground_truth_value": 5000.0,
                "extracted_value": 5100.0,
            }],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 0

    def test_exact_name_match_gives_suggestion(self):
        ga = GapAnalyzer()
        report = _make_report(
            missing_items=[{"name": "ABC"}],
            unmatched_items=[{"name": "ABC"}],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "alias_suggestion"

    def test_missing_items_without_unmatched(self):
        ga = GapAnalyzer()
        report = _make_report(
            missing_items=[{"name": "货币资金", "code": "F033N"}],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 0

    def test_unmatched_items_without_missing(self):
        ga = GapAnalyzer()
        report = _make_report(
            unmatched_items=[{"name": "some_random_item"}],
        )
        suggestions = ga.analyze(report)
        assert len(suggestions) == 0


class TestGenerateYamlUpdates:
    """Tests for GapAnalyzer.generate_yaml_updates()."""

    def test_empty_suggestions(self):
        ga = GapAnalyzer()
        assert ga.generate_yaml_updates([]) == {}

    def test_alias_suggestion_produces_structure(self):
        ga = GapAnalyzer()
        suggestions = [{
            "type": "alias_suggestion",
            "standard_name": "货币资金",
            "code": "F033N",
            "variants": ["货币资金合计"],
            "reason": "unmatched_item_similar_to_missing",
        }]
        updates = ga.generate_yaml_updates(suggestions)
        assert "income_statement" in updates
        assert "货币资金" in updates["income_statement"]
        assert updates["income_statement"]["货币资金"] == ["货币资金合计"]

    def test_custom_statement_type(self):
        ga = GapAnalyzer()
        suggestions = [{
            "type": "alias_suggestion",
            "standard_name": "总资产",
            "code": "F050N",
            "variants": ["资产合计"],
            "reason": "test",
        }]
        updates = ga.generate_yaml_updates(suggestions, statement_type="balance_sheet")
        assert "balance_sheet" in updates
        assert "总资产" in updates["balance_sheet"]

    def test_unit_suggestions_ignored(self):
        ga = GapAnalyzer()
        suggestions = [{
            "type": "unit_suggestion",
            "standard_name": "存货",
            "suggested_unit": "万元",
            "reason": "value_off_by_10000x",
        }]
        updates = ga.generate_yaml_updates(suggestions)
        assert updates == {}

    def test_multiple_variants_accumulated(self):
        ga = GapAnalyzer()
        suggestions = [
            {
                "type": "alias_suggestion",
                "standard_name": "货币资金",
                "variants": ["货币资金合计"],
                "reason": "test",
            },
            {
                "type": "alias_suggestion",
                "standard_name": "货币资金",
                "variants": ["货币资金小计"],
                "reason": "test",
            },
        ]
        updates = ga.generate_yaml_updates(suggestions)
        assert len(updates["income_statement"]["货币资金"]) == 2


class TestNameSimilarity:
    """Tests for the _name_similarity helper used by GapAnalyzer."""

    def test_identical_names(self):
        ga = GapAnalyzer()
        assert ga._name_similarity("abc", "abc") == 1.0

    def test_substring_relationship(self):
        ga = GapAnalyzer()
        score = ga._name_similarity("abc", "abcdef")
        assert score > 0.7

    def test_completely_different(self):
        ga = GapAnalyzer()
        score = ga._name_similarity("货币资金", "应收账款")
        assert score < 0.7

    def test_similar_chinese_names(self):
        ga = GapAnalyzer()
        score = ga._name_similarity("货币资金", "货币资金合计")
        assert score > 0.7


class TestPrintReport:
    """Tests for GapAnalyzer.print_report()."""

    def test_returns_suggestions(self, capsys):
        ga = GapAnalyzer()
        suggestions = [
            {"type": "alias_suggestion", "standard_name": "X", "variants": ["Y"]},
            {"type": "unit_suggestion", "standard_name": "Z", "suggested_unit": "万元"},
        ]
        result = ga.print_report(suggestions)
        assert result == suggestions
        captured = capsys.readouterr()
        assert "GAP ANALYSIS REPORT" in captured.out
        assert "Alias suggestions: 1" in captured.out
        assert "Unit suggestions: 1" in captured.out

    def test_empty_suggestions(self, capsys):
        ga = GapAnalyzer()
        result = ga.print_report([])
        assert result == []
        captured = capsys.readouterr()
        assert "Alias suggestions: 0" in captured.out
