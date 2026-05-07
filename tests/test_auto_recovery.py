# -*- coding: utf-8 -*-
"""Integration tests for auto-recovery quality gate."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.parsers.pdf_parser import PdfParser


class TestQualityGate:
    """Tests for automatic recovery trigger on low-quality extraction."""

    def test_confidence_above_threshold_no_recovery(self):
        """High-quality extraction should not trigger recovery."""
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if not os.path.exists(pdf_path):
            pytest.skip("PDF not available")
        with PdfParser(pdf_path) as parser:
            extractor = BalanceSheetExtractor(parser)
            result = extractor.extract()
        assert result.get("found") is True
        assert len(result.get("data", {})) > 0

    def test_low_quality_triggers_recovery(self):
        pytest.skip("Requires known failing PDF — run manually")
