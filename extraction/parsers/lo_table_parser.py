# -*- coding: utf-8 -*-
"""
LibreOffice HTML 表格解析器

LibreOffice 将 PDF 转换为 HTML 时，会将表格拆散为多个 <p> 标签。
本解析器通过分析 <p> 标签的内容类型（项目名/附注/数值）来重构表格结构。
"""

import re
from typing import List, Optional
from bs4 import BeautifulSoup, Tag
import pandas as pd


class LibreOfficeTableParser:
    """LibreOffice HTML 表格解析器"""

    NUMERIC_PATTERN = re.compile(r"^-?[\d,]+(\.\d+)?%?$")
    NOTE_PATTERN = re.compile(r"^[\u4e00-\u9fff\d]+[、.][a-z\d]?(\([a-z]\))?$|^\d+[a-z]?(\([a-z]\))?$")
    DATE_LABEL_PATTERN = re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$|^\d{4}年\d{1,2}月\d{1,2}日$|^\d{4}年$|^\d{4}年\d{1,2}月$|^\d{1,2}月\d{1,2}日$")
    SECTION_HEADERS = {"资产", "负债", "股东权益", "所有者权益"}

    def __init__(self, html_path: str):
        if not html_path.endswith(".html"):
            raise ValueError("只支持 HTML 文件")
        self.html_path = html_path
        self.soup: Optional[BeautifulSoup] = None
        self._all_elements: List[Tag] = []
        self._load()

    def _load(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.soup = BeautifulSoup(content, "lxml")
        self._all_elements = self.soup.find_all("p")
        self._page_count = len(self.soup.find_all("h1", style="page-break-before:always")) + 1

    @property
    def page_count(self) -> int:
        return self._page_count

    def _is_numeric(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return False
        if self._is_note(text):
            return False
        return bool(self.NUMERIC_PATTERN.match(text))

    def _is_note(self, text: str) -> bool:
        text = text.strip()
        if not text or self.DATE_LABEL_PATTERN.match(text):
            return False
        return bool(self.NOTE_PATTERN.match(text))

    def _is_date_label(self, text: str) -> bool:
        return bool(self.DATE_LABEL_PATTERN.match(text.strip()))

    def _is_section_header(self, text: str) -> bool:
        return text.strip() in self.SECTION_HEADERS

    def _classify_element(self, elem: Tag) -> tuple:
        text = elem.get_text(strip=True)
        if not text:
            return (text, "empty")
        if self._is_numeric(text):
            return (text, "numeric")
        if self._is_note(text):
            return (text, "note")
        if self._is_date_label(text):
            return (text, "date_label")
        return (text, "item")

    def _find_table_start(self, keyword: str) -> int:
        for i, elem in enumerate(self._all_elements):
            if keyword in elem.get_text():
                return i
        return -1

    def _extract_table_from_position(self, start_idx: int, max_rows: int = 800) -> pd.DataFrame:
        classified = [self._classify_element(e) for e in self._all_elements[start_idx:start_idx + max_rows]]
        
        rows = []
        current_item = None
        pending_note = None
        values = []

        for i, (text, ptype) in enumerate(classified):
            if ptype == "empty":
                if current_item and len(values) >= 2:
                    row = [current_item]
                    if not pending_note:
                        row.append("")
                    else:
                        row.append(pending_note)
                    row.extend(values[:2])
                    rows.append(row)
                    current_item = None
                    pending_note = None
                    values = []
                continue

            if ptype == "item" and not self._is_section_header(text):
                if current_item and len(values) >= 2:
                    row = [current_item]
                    if not pending_note:
                        row.append("")
                    else:
                        row.append(pending_note)
                    row.extend(values[:2])
                    rows.append(row)
                current_item = text
                pending_note = None
                values = []
            elif ptype == "note":
                pending_note = text
            elif ptype == "numeric":
                values.append(text)

        if current_item and len(values) >= 2:
            row = [current_item]
            if not pending_note:
                row.append("")
            else:
                row.append(pending_note)
            row.extend(values[:2])
            rows.append(row)

        if not rows:
            return pd.DataFrame()

        max_cols = max(len(row) for row in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        df = pd.DataFrame(rows)
        
        if df.shape[1] == 3:
            df.columns = ["项目", "2025年数值", "2024年数值"]
        elif df.shape[1] == 4:
            df.columns = ["项目", "附注", "2025年数值", "2024年数值"]
        else:
            df.columns = [f"col_{i}" for i in range(df.shape[1])]
        
        return df

    def extract_balance_sheet(self) -> pd.DataFrame:
        idx = self._find_table_start("合并资产负债表")
        if idx >= 0:
            return self._extract_table_from_position(idx)
        return pd.DataFrame()

    def extract_income_statement(self) -> pd.DataFrame:
        idx = self._find_table_start("合并利润表")
        if idx >= 0:
            return self._extract_table_from_position(idx)
        return pd.DataFrame()

    def extract_cash_flow(self) -> pd.DataFrame:
        idx = self._find_table_start("合并现金流量表")
        if idx >= 0:
            return self._extract_table_from_position(idx)
        return pd.DataFrame()


def parse_lo_html(html_path: str) -> LibreOfficeTableParser:
    return LibreOfficeTableParser(html_path)