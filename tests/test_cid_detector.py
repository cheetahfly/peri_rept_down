# -*- coding: utf-8 -*-
"""
Tests for CIDFontDetector - full-page CID font detection
"""

import os
import pytest

from extraction.cid_detector import CIDFontDetector


class TestCIDFontDetector:
    """Test suite for CIDFontDetector."""

    @pytest.fixture
    def detector(self):
        """Create a CIDFontDetector instance for testing."""
        return CIDFontDetector()

    @pytest.fixture
    def pdf_path(self):
        """Path to the 601628 test PDF with known CID issues."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "data", "by_code", "601628", "601628_中国人寿_2024_年报.pdf")

    def test_scan_all_pages_detects_cid(self, detector, pdf_path):
        """Test full-page scan detects CID font beyond page 20."""
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test PDF not found: {pdf_path}")

        result = detector.scan_all_pages(pdf_path)

        # Ensure more than 20 pages were scanned
        assert len(result) > 20, f"Expected scan of >20 pages, got {len(result)}"

        # Verify CF pages (typically after page 50) are detected
        cid_pages = [p for p, score in result.items() if score > 0.15]
        assert len(cid_pages) > 0, "No CID pages detected in full-page scan"

    def test_threshold_lowered(self, detector):
        """Test threshold is lowered from 30% to 15%."""
        assert detector.threshold == 0.15

    def test_threshold_custom(self):
        """Test custom threshold value."""
        custom_detector = CIDFontDetector(threshold=0.25)
        assert custom_detector.threshold == 0.25

    def test_is_numeric(self, detector):
        """Test numeric text detection."""
        assert detector._is_numeric("123") is True
        assert detector._is_numeric("1,234.56") is True
        assert detector._is_numeric("(100)") is True
        assert detector._is_numeric("50%") is True
        assert detector._is_numeric("abc") is False
        assert detector._is_numeric("") is False

    def test_get_cid_pages(self, detector, pdf_path):
        """Test retrieving pages with CID probability above threshold."""
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test PDF not found: {pdf_path}")

        cid_pages = detector.get_cid_pages(pdf_path)

        # Should return pages above threshold
        result = detector.scan_all_pages(pdf_path)
        for page_num in cid_pages:
            assert result[page_num] >= detector.threshold

    def test_scan_all_pages_returns_dict(self, detector, pdf_path):
        """Test scan_all_pages returns proper dictionary structure."""
        if not os.path.exists(pdf_path):
            pytest.skip(f"Test PDF not found: {pdf_path}")

        result = detector.scan_all_pages(pdf_path)

        assert isinstance(result, dict)
        assert all(isinstance(k, int) for k in result.keys())
        assert all(isinstance(v, float) for v in result.values())
        assert all(0.0 <= v <= 1.0 for v in result.values())