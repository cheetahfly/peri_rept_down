# -*- coding: utf-8 -*-
"""End-to-end integration tests for the auto-recovery pipeline."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.extractors.balance_sheet import BalanceSheetExtractor
from extraction.extractors.income_statement import IncomeStatementExtractor
from extraction.extractors.cash_flow import CashFlowExtractor
from extraction.parsers.pdf_parser import PdfParser


class TestFullRecoveryPipeline:
    """Full pipeline: extract -> quality check -> auto recovery -> replace."""

    @pytest.mark.parametrize("extractor_class,stmt_type", [
        (BalanceSheetExtractor, "balance_sheet"),
        (IncomeStatementExtractor, "income_statement"),
        (CashFlowExtractor, "cash_flow"),
    ])
    def test_extraction_produces_found_result(self, extractor_class, stmt_type):
        """Standard PDFs should produce found=True without triggering recovery."""
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if not os.path.exists(pdf_path):
            pytest.skip("PDF not available")
        with PdfParser(pdf_path) as parser:
            extractor = extractor_class(parser)
            result = extractor.extract()
        assert result.get("found") is True
        assert len(result.get("data", {})) > 0

    def test_recovered_flag_absent_for_good_extraction(self):
        """High-quality extraction should not have 'recovered' flag set."""
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if not os.path.exists(pdf_path):
            pytest.skip("PDF not available")
        with PdfParser(pdf_path) as parser:
            extractor = BalanceSheetExtractor(parser)
            result = extractor.extract()
        # recovered flag should not be present or should be falsy
        assert not result.get("recovered", False)

    def test_extractors_all_produce_non_empty_data(self):
        """All three extractors should produce data with actual values."""
        pdf_path = "data/by_code/000001/000001_平安银行_2024_年报.pdf"
        if not os.path.exists(pdf_path):
            pytest.skip("PDF not available")
        with PdfParser(pdf_path) as parser:
            for ExtractorClass, name in [
                (BalanceSheetExtractor, "BS"),
                (IncomeStatementExtractor, "IS"),
                (CashFlowExtractor, "CF"),
            ]:
                extractor = ExtractorClass(parser)
                result = extractor.extract()
                assert len(result.get("data", {})) > 0, f"{name} produced no data"