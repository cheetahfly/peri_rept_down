# -*- coding: utf-8 -*-
"""
CID Font Detector - Full-page scanning for CID-font encoded PDFs

Detects CID-font encoded pages throughout entire PDF documents,
not just the first 20 pages as previously implemented.
"""

from typing import Dict
import re

import pdfplumber

from extraction.parsers.html_converter import is_garbled_text


class CIDFontDetector:
    """Detector for CID-font encoded pages in PDF documents."""

    def __init__(self, threshold: float = 0.15):
        """
        Initialize CID font detector.

        Args:
            threshold: Detection threshold for CID probability (default 0.15, lowered from 0.30)
        """
        self.threshold = threshold

    def scan_all_pages(self, pdf_path: str) -> Dict[int, float]:
        """
        Scan all pages of a PDF and return CID probability for each page.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary mapping page number (0-indexed) to CID probability score
        """
        results = {}
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            for page_num in range(total):
                score = self._calculate_cid_probability(pdf, page_num)
                results[page_num] = score
        return results

    def _calculate_cid_probability(self, pdf: pdfplumber.PDF, page_num: int) -> float:
        """
        Calculate the CID probability score for a single page.

        Args:
            pdf: The pdfplumber PDF object
            page_num: Page number (0-indexed)

        Returns:
            CID probability score between 0.0 and 1.0
        """
        page = pdf.pages[page_num]
        text = page.extract_text() or ""

        # Primary check: garbled text detection
        if len(text) > 50 and is_garbled_text(text):
            return 1.0

        # Secondary check: numeric density detection for financial pages
        words = page.extract_words()
        numeric_count = sum(1 for w in words if self._is_numeric(w['text']))
        if len(words) > 0 and numeric_count / len(words) > 0.5:
            return 0.3  # Possibly a financial statement page

        return 0.0

    def _is_numeric(self, text: str) -> bool:
        """
        Check if text represents a numeric value.

        Args:
            text: Text to check

        Returns:
            True if text is purely numeric (digits, commas, dots, parentheses, etc.)
        """
        return bool(re.match(r'^[\d,\.\-()%]+$', text.strip()))

    def get_cid_pages(self, pdf_path: str) -> list:
        """
        Get list of page numbers that likely contain CID-font encoded content.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of page numbers (0-indexed) with CID probability above threshold
        """
        results = self.scan_all_pages(pdf_path)
        return [page_num for page_num, score in results.items() if score >= self.threshold]