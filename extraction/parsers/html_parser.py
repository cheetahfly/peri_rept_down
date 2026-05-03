# -*- coding: utf-8 -*-
"""
HTML解析器 - 用于解析pdf2htmlEX或LibreOffice转换后的HTML

这些工具可以将自定义字体编码的PDF转换为可读的HTML，
解决pdfplumber/PyMuPDF无法处理的乱码问题。
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
import pandas as pd


class HtmlParser:
    """HTML解析器封装"""

    def __init__(self, html_path: str):
        """
        初始化HTML解析器

        Args:
            html_path: HTML文件路径
        """
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"HTML文件不存在: {html_path}")

        self.html_path = html_path
        self.soup = None
        self._cached_pages = None  # 缓存页面列表
        self._load_html()

    def _load_html(self):
        """加载HTML文件"""
        with open(self.html_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.soup = BeautifulSoup(content, "html.parser")
        self._cached_pages = None  # 重置缓存

    def _get_pages(self):
        """获取页面列表（带缓存）"""
        if self._cached_pages is None:
            self._cached_pages = self.soup.find_all("div", class_="page")
        return self._cached_pages

    @property
    def page_count(self) -> int:
        """获取总页数（基于page元素）"""
        pages = self._get_pages()
        if pages:
            return len(pages)
        return 1

    def extract_text(self, page_num: int = 0) -> str:
        """
        提取页面文本

        Args:
            page_num: 页码（从0开始）

        Returns:
            页面文本内容
        """
        pages = self._get_pages()

        if not pages:
            return self.soup.get_text()

        if page_num < 0 or page_num >= len(pages):
            return ""

        page = pages[page_num]
        return page.get_text(separator="\n", strip=True)

    def extract_tables(
        self, page_num: int = 0, min_rows: int = 3, min_cols: int = 2
    ) -> List[pd.DataFrame]:
        """
        提取页面表格

        Args:
            page_num: 页码（从0开始）
            min_rows: 最少行数
            min_cols: 最少列数

        Returns:
            表格DataFrame列表
        """
        pages = self._get_pages()

        if not pages:
            return []

        if page_num < 0 or page_num >= len(pages):
            return []

        page = pages[page_num]
        tables = page.find_all("table")

        result = []
        for table in tables:
            df = self._parse_html_table(table)
            if df is not None and df.shape[0] >= min_rows and df.shape[1] >= min_cols:
                result.append(df)

        return result

    def _parse_html_table(self, table) -> Optional[pd.DataFrame]:
        """
        解析HTML表格为DataFrame

        Args:
            table: BeautifulSoup table元素

        Returns:
            DataFrame或None
        """
        try:
            rows = table.find_all("tr")
            if not rows:
                return None

            data = []
            for row in rows:
                cells = row.find_all(["td", "th"])
                if cells:
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    data.append(row_data)

            if not data:
                return None

            max_cols = max(len(row) for row in data)
            for row in data:
                while len(row) < max_cols:
                    row.append("")

            df = pd.DataFrame(data[1:], columns=data[0] if data else None)
            return df

        except Exception:
            return None

    def extract_text_tables(self, page_num: int = 0) -> List[pd.DataFrame]:
        """
        从LibreOffice转换的HTML中提取文本表格（使用空白字符分割）

        Args:
            page_num: 页码（从0开始）

        Returns:
            表格DataFrame列表
        """
        pages = self._get_pages()
        if not pages:
            text = self.soup.get_text()
            return self._parse_text_to_tables(text)

        if page_num < 0 or page_num >= len(pages):
            return []

        page = pages[page_num]
        text = page.get_text(separator="\n", strip=True)
        return self._parse_text_to_tables(text)

    def _parse_text_to_tables(self, text: str) -> List[pd.DataFrame]:
        """
        将文本解析为表格

        Args:
            text: 文本内容

        Returns:
            表格DataFrame列表
        """
        if not text:
            return []

        lines = text.split("\n")
        tables = []
        current_table = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_table and len(current_table) >= 3:
                    df = pd.DataFrame(current_table)
                    tables.append(df)
                    current_table = []
                continue

            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 2:
                current_table.append(parts)

        if current_table and len(current_table) >= 3:
            df = pd.DataFrame(current_table)
            tables.append(df)

        return tables

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
        pages = self._get_pages()
        if not pages:
            text = self.soup.get_text()
            if not case_sensitive:
                text = text.lower()
            if any(
                kw in text if case_sensitive else kw.lower() in text for kw in keywords
            ):
                return [0]
            return []

        matched_pages = []
        for i, page in enumerate(pages):
            text = page.get_text()
            if not case_sensitive:
                text = text.lower()
                search_keywords = [k.lower() for k in keywords]
            else:
                search_keywords = keywords

            if any(kw in text for kw in search_keywords):
                matched_pages.append(i)

        return matched_pages

    def extract_all_text(self) -> str:
        """
        提取所有页面的文本

        Returns:
            合并后的所有文本
        """
        pages = self._get_pages()
        if not pages:
            return self.soup.get_text(separator="\n", strip=True)

        texts = []
        for page in pages:
            texts.append(page.get_text(separator="\n", strip=True))
        return "\n\n".join(texts)

    def extract_text_range(self, start_page: int, end_page: int) -> str:
        """
        提取多个页面的文本

        Args:
            start_page: 起始页码（包含）
            end_page: 结束页码（包含）

        Returns:
            合并后的文本
        """
        pages = self._get_pages()
        if not pages:
            return self.soup.get_text(separator="\n", strip=True)

        texts = []
        for i in range(start_page, min(end_page + 1, len(pages))):
            texts.append(pages[i].get_text(separator="\n", strip=True))
        return "\n\n".join(texts)

    def get_pages_range(self, start_page: int, end_page: int) -> List[int]:
        """
        获取页面范围

        Args:
            start_page: 起始页码
            end_page: 结束页码

        Returns:
            页码列表
        """
        pages = self._get_pages()
        total = len(pages) if pages else 1
        return list(range(start_page, min(end_page + 1, total)))
