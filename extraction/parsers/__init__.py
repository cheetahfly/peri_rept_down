# -*- coding: utf-8 -*-
"""
PDF解析器模块
"""

from extraction.parsers.pdf_parser import PdfParser
from extraction.parsers.html_parser import HtmlParser
from extraction.parsers.html_converter import (
    PdfToHtmlConverter,
    convert_pdf_to_html,
    is_garbled_text,
)
from extraction.parsers.hybrid_parser import HybridParser

try:
    from extraction.parsers.ocr_parser import (
        OCRTableParser,
        ImageOrcParser,
        OCRSpaceParser,
        CloudOCRParser,
        OCREngineType,
    )
    HAS_OCR = True
except ImportError as e:
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
    "OCRTableParser",
    "ImageOrcParser",
    "OCRSpaceParser",
    "CloudOCRParser",
    "OCREngineType",
    "HAS_OCR",
]
