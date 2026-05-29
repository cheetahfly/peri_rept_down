# -*- coding: utf-8 -*-
"""
PDF parsers for financial report extraction.
"""

from astock_fundamentals.sources.pdf.parsers.pdf_parser import PdfParser
from astock_fundamentals.sources.pdf.parsers.html_parser import HtmlParser
from astock_fundamentals.sources.pdf.parsers.html_converter import (
    PdfToHtmlConverter,
    convert_pdf_to_html,
    is_garbled_text,
)
from astock_fundamentals.sources.pdf.parsers.hybrid_parser import HybridParser

try:
    from astock_fundamentals.sources.pdf.parsers.pymupdf_parser import PyMuPDFParser
    HAS_PYMUPDF = True
except ImportError:
    PyMuPDFParser = None
    HAS_PYMUPDF = False

try:
    from astock_fundamentals.sources.pdf.parsers.ocr_parser import (
        OCRTableParser,
        ImageOrcParser,
        OCRSpaceParser,
        CloudOCRParser,
        OCREngineType,
    )
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    OCRTableParser = None
    ImageOrcParser = None
    OCRSpaceParser = None
    CloudOCRParser = None
    OCREngineType = None

__all__ = [
    "PdfParser",
    "HtmlParser",
    "PdfToHtmlConverter",
    "convert_pdf_to_html",
    "is_garbled_text",
    "HybridParser",
    "PyMuPDFParser",
    "HAS_PYMUPDF",
    "OCRTableParser",
    "ImageOrcParser",
    "OCRSpaceParser",
    "CloudOCRParser",
    "OCREngineType",
    "HAS_OCR",
]
