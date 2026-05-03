# -*- coding: utf-8 -*-
"""
PyMuPDF PDF解析器 - 作为pdfplumber的备选

PyMuPDF (fitz) 在某些CID自定义字体PDF上可能有不同的解码策略。
"""

import os
import re
from typing import List, Dict, Optional, Tuple
import fitz  # PyMuPDF
import pandas as pd


class PyMuPDFParser:
    """PyMuPDF解析器封装，提供与PdfParser相似的接口"""

    def __init__(self, pdf_path: str):
        """
        初始化PyMuPDF解析器

        Args:
            pdf_path: PDF文件路径
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self._page_texts = {}  # 缓存页面文本

    def __len__(self) -> int:
        """返回总页数"""
        return len(self.doc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """关闭PDF文档"""
        if hasattr(self, "doc") and self.doc:
            self.doc.close()

    @property
    def page_count(self) -> int:
        """总页数"""
        return len(self.doc)

    def extract_text(self, page_num: int, layout: bool = False) -> str:
        """
        提取页面文本

        Args:
            page_num: 页码（从0开始）
            layout: 是否保留布局（默认False，速度快）

        Returns:
            页面文本内容
        """
        if page_num < 0 or page_num >= len(self.doc):
            return ""

        if page_num not in self._page_texts:
            page = self.doc[page_num]
            # PyMuPDF get_text returns text with layout info when mode is appropriate
            self._page_texts[page_num] = page.get_text("text") or ""

        return self._page_texts[page_num]

    def extract_tables(
        self, page_num: int, min_rows: int = 3, min_cols: int = 2
    ) -> List[pd.DataFrame]:
        """
        提取页面表格

        PyMuPDF不提供直接的表格提取API，这里返回空列表。
        表格提取实际由HybridParser委托给pdfplumber处理。

        Args:
            page_num: 页码（从0开始）
            min_rows: 最少行数
            min_cols: 最少列数

        Returns:
            表格DataFrame列表（始终为空，表格提取由pdfplumber负责）
        """
        # PyMuPDF不提供直接的表格提取API
        # 表格提取由HybridParser委托给pdfplumber处理
        return []

    def find_pages(
        self, keywords: List[str], case_sensitive: bool = False
    ) -> List[int]:
        """
        搜索包含关键词的页面

        Args:
            keywords: 关键词列表（任一匹配即返回）
            case_sensitive: 是否大小写敏感

        Returns:
            匹配的页码列表
        """
        matched_pages = []

        # 预热缓存
        if len(self._page_texts) < len(self.doc):
            for page_num in range(len(self.doc)):
                if page_num not in self._page_texts:
                    self._page_texts[page_num] = self.doc[page_num].get_text("text") or ""

        for page_num, text in self._page_texts.items():
            if not case_sensitive:
                text_lower = text.lower()
                search_keywords = [k.lower() for k in keywords]
            else:
                text_lower = text
                search_keywords = keywords

            if any(kw in text_lower for kw in search_keywords):
                matched_pages.append(page_num)

        return sorted(matched_pages)

    def extract_text_range(self, start_page: int, end_page: int) -> str:
        """
        提取多个页面的文本

        Args:
            start_page: 起始页码（包含）
            end_page: 结束页码（包含）

        Returns:
            合并后的文本
        """
        texts = []
        for page_num in range(start_page, min(end_page + 1, len(self.doc))):
            texts.append(self.extract_text(page_num))
        return "\n".join(texts)

    def get_pages_range(self, start_page: int, end_page: int) -> List[int]:
        """获取页面范围"""
        return list(range(start_page, min(end_page + 1, len(self.doc))))

    def detect_unit(self, page_num: int = None) -> Tuple[str, float]:
        """检测PDF中的数值单位"""
        from extraction.config import UNIT_MULTIPLIERS

        search_pages = range(self.page_count) if page_num is None else [page_num]

        unit_keywords = ["元", "万元", "亿元", "千元", "百万", "万亿"]

        for p in search_pages:
            text = self.extract_text(p)
            if not text:
                continue

            for keyword in unit_keywords:
                if keyword in text:
                    if keyword in UNIT_MULTIPLIERS:
                        return keyword, UNIT_MULTIPLIERS[keyword]

        return ("元", 1)

    def extract_all_text(self) -> str:
        """提取所有页面的文本"""
        texts = []
        for page_num in range(len(self.doc)):
            texts.append(self.extract_text(page_num))
        return "\n".join(texts)
