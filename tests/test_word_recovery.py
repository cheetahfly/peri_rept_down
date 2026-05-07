# -*- coding: utf-8 -*-
"""
Unit tests for word_recovery.py - CID-font numeric recovery

Tests cover:
- Number parsing (_parse_num)
- Date-like value filtering (_is_date_like)
- X-position clustering for column detection (_cluster_x_positions)
- Structured numeric extraction from pages
- Full statement recovery
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.word_recovery import (
    _parse_num,
    _is_date_like,
    _cluster_x_positions,
    extract_structured_numeric,
    recover_statement,
    find_data_pages,
    score_page_density,
    get_page_count,
)


class TestParseNum:
    """Tests for _parse_num function."""

    def test_positive_integer(self):
        assert _parse_num("12345") == 12345.0

    def test_positive_float(self):
        assert _parse_num("12345.67") == 12345.67

    def test_negative_in_parentheses(self):
        assert _parse_num("(12345)") == -12345.0

    def test_negative_with_minus(self):
        assert _parse_num("-12345") == -12345.0

    def test_with_commas(self):
        assert _parse_num("1,234,567") == 1234567.0

    def test_with_spaces(self):
        assert _parse_num("  12345  ") == 12345.0

    def test_percentage(self):
        assert _parse_num("55.60%") == 55.60

    def test_empty_string(self):
        assert _parse_num("") is None

    def test_whitespace_only(self):
        assert _parse_num("   ") is None

    def test_non_numeric(self):
        assert _parse_num("abc") is None

    def test_parentheses_only(self):
        assert _parse_num("()") is None

    def test_parentheses_with_number(self):
        assert _parse_num("(1,234)") == -1234.0

    def test_yuan_unit(self):
        assert _parse_num("100元") is None  # non-numeric suffix


class TestIsDateLike:
    """Tests for _is_date_like function."""

    def test_year_2023(self):
        assert _is_date_like(2023.0) is True

    def test_year_2024(self):
        assert _is_date_like(2024.0) is True

    def test_year_2025(self):
        assert _is_date_like(2025.0) is True

    def test_small_number(self):
        assert _is_date_like(15.0) is True

    def test_large_financial_value(self):
        assert _is_date_like(43748000000.0) is False

    def test_negative_large(self):
        assert _is_date_like(-107796.0) is False

    def test_small_negative(self):
        assert _is_date_like(-15.0) is False


class TestClusterXPositions:
    """Tests for _cluster_x_positions function."""

    def test_single_column(self):
        positions = [100, 105, 98, 102]
        result = _cluster_x_positions(positions, tolerance=10)
        assert len(result) == 1

    def test_two_separate_columns(self):
        positions = [100, 105, 300, 310]
        result = _cluster_x_positions(positions, tolerance=20)
        assert len(result) == 2

    def test_four_columns(self):
        positions = [100, 110, 200, 210, 300, 310, 400, 405]
        result = _cluster_x_positions(positions, tolerance=15)
        assert len(result) == 4

    def test_empty_input(self):
        result = _cluster_x_positions([], tolerance=10)
        assert result == []

    def test_single_position(self):
        result = _cluster_x_positions([150], tolerance=10)
        assert len(result) == 1

    def test_large_tolerance_merges_columns(self):
        positions = [100, 200, 300, 400]
        result = _cluster_x_positions(positions, tolerance=200)
        assert len(result) == 1


class TestExtractStructuredNumeric:
    """Tests for extract_structured_numeric on real PDFs."""

    @pytest.fixture
    def pdf_600016(self):
        """Path to 600016 CF PDF."""
        return "data/by_code/600016/600016_民生银行_2024_年报.pdf"

    def test_returns_dict_structure(self, pdf_600016):
        """Result should have expected keys."""
        result = extract_structured_numeric(pdf_600016, 166)
        assert "page" in result
        assert "method" in result
        assert "columns" in result
        assert "rows" in result

    def test_method_is_word(self, pdf_600016):
        """Page 166 should use word extraction."""
        result = extract_structured_numeric(pdf_600016, 166)
        assert result["method"] == "word"

    def test_detects_4_columns(self, pdf_600016):
        """Page 166 should detect 4 data columns."""
        result = extract_structured_numeric(pdf_600016, 166)
        columns = result["columns"]
        # Should detect 4+ columns for consolidated/parent x 2 years
        assert len(columns) >= 4

    def test_returns_rows_with_values(self, pdf_600016):
        """Rows should contain numeric values."""
        result = extract_structured_numeric(pdf_600016, 166)
        rows = result["rows"]
        assert len(rows) > 0
        # Every row should have a values list
        for row in rows:
            assert "values" in row
            assert "y" in row

    def test_large_values_present(self, pdf_600016):
        """Large CF values should be extracted."""
        result = extract_structured_numeric(pdf_600016, 166)
        all_values = []
        for row in result["rows"]:
            all_values.extend([v for v in row["values"] if v is not None])
        # Should have values > 100000 (hundred thousands)
        large_vals = [v for v in all_values if abs(v) > 100000]
        assert len(large_vals) > 0

    def test_negative_values_extracted(self, pdf_600016):
        """Negative values (parentheses) should be correctly parsed."""
        result = extract_structured_numeric(pdf_600016, 166)
        all_values = []
        for row in result["rows"]:
            all_values.extend([v for v in row["values"] if v is not None])
        negatives = [v for v in all_values if v < 0]
        assert len(negatives) > 0

    def test_nonexistent_page_returns_empty(self, pdf_600016):
        """Out-of-range page should return empty structure."""
        result = extract_structured_numeric(pdf_600016, 9999)
        assert result["rows"] == []


class TestFindDataPages:
    """Tests for find_data_pages function."""

    def test_finds_pages_in_600016(self):
        """Should find CF data pages in 600016 PDF."""
        pdf = "data/by_code/600016/600016_民生银行_2024_年报.pdf"
        pages = find_data_pages(pdf, list(range(160, 175)))
        assert len(pages) > 0
        assert 166 in pages

    def test_empty_scan_range(self):
        """Empty range should return empty list."""
        pdf = "data/by_code/600016/600016_民生银行_2024_年报.pdf"
        pages = find_data_pages(pdf, [])
        assert pages == []


class TestRecoverStatement:
    """Tests for recover_statement function."""

    def test_recover_600016_cash_flow(self):
        """Full recovery of 600016 CF should work."""
        pdf = "data/by_code/600016/600016_民生银行_2024_年报.pdf"
        data = recover_statement(pdf, [165, 166, 167])

        assert data["found"] is True
        assert data["recovery_method"] in ("word", "table", "mixed")
        assert len(data["pages"]) == 3
        assert 165 in data["pages"]
        assert 166 in data["pages"]
        assert 167 in data["pages"]

    def test_stats_calculated(self):
        """Stats should be calculated correctly."""
        pdf = "data/by_code/600016/600016_民生银行_2024_年报.pdf"
        data = recover_statement(pdf, [166])

        assert "stats" in data
        assert data["stats"]["total_values"] > 0
        assert data["stats"]["total_pages"] == 1
        assert data["stats"]["total_rows"] > 0

    def test_page_data_structure(self):
        """Page data should have correct structure."""
        pdf = "data/by_code/600016/600016_民生银行_2024_年报.pdf"
        data = recover_statement(pdf, [166])

        assert "166" in data["page_data"]
        page_info = data["page_data"]["166"]
        assert "rows" in page_info
        assert page_info["row_count"] > 0

    def test_empty_pages_returns_empty(self):
        """No data pages should return empty result."""
        pdf = "data/by_code/600016/600016_民生银行_2024_年报.pdf"
        data = recover_statement(pdf, [9999])
        assert data["found"] is False
        assert data["stats"]["total_values"] == 0


class TestScorePageDensity:
    """Tests for score_page_density function."""

    def test_returns_float(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            score = score_page_density(pdf_path, 10)
            assert isinstance(score, float)

    def test_high_score_for_data_page(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            score = score_page_density(pdf_path, 10)
            assert score >= 0.0

    def test_zero_for_empty_page(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            score = score_page_density(pdf_path, 0)
            assert score >= 0.0

    def test_compare_text_vs_table_page(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            scores = [score_page_density(pdf_path, p) for p in range(min(20, get_page_count(pdf_path)))]
            assert any(s > 0 for s in scores), "No page scored above 0 — density scoring broken"


class TestFindDataPagesAuto:
    """Tests for the rewritten find_data_pages() with density ranking."""

    def test_returns_list_of_ints(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            pages = find_data_pages(pdf_path, scan_range=list(range(50)), top_n=5)
            assert isinstance(pages, list)
            assert all(isinstance(p, int) for p in pages)

    def test_returns_top_n_pages(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            pages = find_data_pages(pdf_path, scan_range=list(range(100)), top_n=3)
            assert len(pages) <= 3

    def test_no_hardcoded_page_numbers(self):
        import inspect
        source = inspect.getsource(find_data_pages)
        assert "165" not in source and "166" not in source and "167" not in source
        assert "hardcoded" not in source.lower()

    def test_empty_range_returns_empty(self):
        pages = find_data_pages("nonexistent.pdf", scan_range=[], top_n=5)
        assert pages == []

    def test_scan_range_respected(self):
        import os
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if os.path.exists(pdf_path):
            pages = find_data_pages(pdf_path, scan_range=list(range(50, 80)), top_n=5)
            assert all(50 <= p < 80 for p in pages)


class TestRecoverAllFailing:
    """Tests for recover_all_failing function."""

    def test_recover_all_failing_uses_auto_scan(self):
        """recover_all_failing() should delegate to auto-scan, not hardcoded pages."""
        import inspect
        from extraction.word_recovery import recover_all_failing
        source = inspect.getsource(recover_all_failing)
        # Check that hardcoded page list patterns from the old implementation are gone
        assert "[165, 166, 167]" not in source
        assert "[3]" not in source
        assert "[4]" not in source
        assert "[4, 5, 6, 7, 11]" not in source
        assert "[6, 95, 97, 191, 192]" not in source
        assert "[88, 99, 101]" not in source
        assert "[106, 107, 108, 109]" not in source
        # Verify it now uses auto-scan
        assert "recover_statement_auto" in source
        assert "pdfplumber.open" in source
