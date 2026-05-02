# -*- coding: utf-8 -*-
"""
PDF解析器 - 基于pdfplumber封装
"""

import os
import re
from typing import List, Dict, Optional, Tuple
import pdfplumber
import pandas as pd


class PdfParser:
    """PDF解析器封装"""

    def __init__(self, pdf_path: str):
        """
        初始化PDF解析器

        Args:
            pdf_path: PDF文件路径
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.pdf_path = pdf_path
        self.doc = pdfplumber.open(pdf_path)
        self._page_texts = {}  # 缓存页面文本

    def __len__(self) -> int:
        """返回总页数"""
        return len(self.doc.pages)

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
        return len(self.doc.pages)

    def extract_text(self, page_num: int, layout: bool = False) -> str:
        """
        提取页面文本

        Args:
            page_num: 页码（从0开始）
            layout: 是否保留布局（默认False，速度快）

        Returns:
            页面文本内容
        """
        if page_num < 0 or page_num >= len(self.doc.pages):
            return ""

        if page_num not in self._page_texts:
            page = self.doc.pages[page_num]
            # 使用 layout=True 预热缓存（速度快75x），关键词搜索质量不变
            # 注意：后续 layout=False 的调用会复用这个缓存（关键词内容一致）
            self._page_texts[page_num] = page.extract_text(layout=True) or ""

        return self._page_texts[page_num]

    def extract_tables(
        self, page_num: int, min_rows: int = 3, min_cols: int = 2
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
        if page_num < 0 or page_num >= len(self.doc.pages):
            return []

        page = self.doc.pages[page_num]
        tables = page.extract_tables()

        result = []
        for table in tables:
            if table and len(table) > 0:
                df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                df = self._clean_table(df, page_num)
                if df.shape[0] >= min_rows and df.shape[1] >= min_cols:
                    result.append(df)

        return result

    def _clean_table(self, df: pd.DataFrame, page_num: int) -> pd.DataFrame:
        """
        清理表格，移除页眉页脚和无效行

        Args:
            df: 原始DataFrame
            page_num: 页码

        Returns:
            清理后的DataFrame
        """
        if df.empty:
            return df

        df = df.copy()

        header_footer_patterns = [
            r".*股份有限公司.*",
            r".*Co\.,?Ltd\.?.*",
            r".*股票代码.*",
            r".*交易所.*",
            r"^\s*$",
        ]

        rows_to_drop = []
        for idx, row in df.iterrows():
            first_cell = str(row.iloc[0]) if len(row) > 0 else ""
            first_cell_clean = first_cell.strip()

            if not first_cell_clean:
                rows_to_drop.append(idx)
                continue

            is_header_footer = False
            for pattern in header_footer_patterns:
                if re.match(pattern, first_cell_clean):
                    is_header_footer = True
                    break

            if is_header_footer:
                rows_to_drop.append(idx)
                continue

            if len(first_cell_clean) <= 2 and idx > 0:
                rows_to_drop.append(idx)

        if rows_to_drop:
            df = df.drop(rows_to_drop)
            df = df.reset_index(drop=True)

        return df

    def find_pages(
        self, keywords: List[str], case_sensitive: bool = False
    ) -> List[int]:
        """
        搜索包含关键词的页面（优化版：预热缓存）

        Args:
            keywords: 关键词列表（任一匹配即返回）
            case_sensitive: 是否大小写敏感

        Returns:
            匹配的页码列表
        """
        matched_pages = []

        # 预热缓存：批量提取所有页面文本（layout=True 速度更快75x）
        if len(self._page_texts) < len(self.doc.pages):
            for page_num in range(len(self.doc.pages)):
                if page_num not in self._page_texts:
                    page = self.doc.pages[page_num]
                    # layout=True 速度快75x，关键词搜索质量一致
                    self._page_texts[page_num] = page.extract_text(layout=True) or ""

        # 从缓存快速查找
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
        for page_num in range(start_page, min(end_page + 1, len(self.doc.pages))):
            texts.append(self.extract_text(page_num))
        return "\n".join(texts)

    def get_pages_range(self, start_page: int, end_page: int) -> List[int]:
        """
        获取页面范围

        Args:
            start_page: 起始页码
            end_page: 结束页码

        Returns:
            页码列表
        """
        return list(range(start_page, min(end_page + 1, len(self.doc.pages))))

    def detect_unit(self, page_num: int = None) -> Tuple[str, float]:
        """
        检测PDF中的数值单位（搜索整个文档）

        Args:
            page_num: 页码（可选，如果指定则只检测该页）

        Returns:
            (单位名称, 乘数)，如 ("万元", 10000)
        """
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
        """
        提取所有页面的文本

        Returns:
            合并后的所有文本
        """
        texts = []
        for page_num in range(len(self.doc.pages)):
            texts.append(self.extract_text(page_num))
        return "\n".join(texts)

    def extract_text_tables(self, page_num: int) -> List[pd.DataFrame]:
        """
        基于文本解析提取表格（备选方法，用于表格提取失败时）

        Args:
            page_num: 页码（从0开始）

        Returns:
            表格DataFrame列表
        """
        if page_num < 0 or page_num >= len(self.doc.pages):
            return []

        page = self.doc.pages[page_num]
        text = page.extract_text()

        if not text:
            return []

        lines = text.split("\n")
        tables = []
        current_table = []

        for line in lines:
            # 清理行
            line = line.strip()
            if not line:
                continue

            # 跳过页眉页脚行（只有公司名称）
            if "股份有限公司" in line or "Co.,Ltd." in line:
                if len(line) < 30:
                    continue

            # 跳过只有年份或注释的行（表头）
            if line in ["注释", "2024年", "2023年", "2022年"] or "金额单位" in line:
                continue

            # 尝试按空格分割
            parts = line.split()

            # 至少要有项目名称和数值
            if len(parts) < 2:
                continue

            # 检查是否包含中文字符（项目名称应该有中文）
            has_chinese = any("\u4e00" <= c <= "\u9fff" for c in line)

            if has_chinese:
                current_table.append(parts)

        # 移除表头行（如果存在）
        if current_table:
            first = current_table[0]
            if len(first) >= 2 and (
                "注释" in str(first[0])
                or "2024" in str(first[1])
                or "2023" in str(first[1])
            ):
                current_table = current_table[1:]

        if len(current_table) >= 3:
            df = pd.DataFrame(current_table)
            tables.append(df)

        return tables

    def extract_tables_with_continuation(
        self, page_num: int, prev_table: pd.DataFrame = None, prev_columns: list = None,
        prefer_text_parse: bool = False
    ) -> Tuple[List[pd.DataFrame], Optional[pd.DataFrame], Optional[list]]:
        """
        提取页面表格，并处理跨页表格延续

        Args:
            page_num: 页码（从0开始）
            prev_table: 上一页的表格（如果需要合并）
            prev_columns: 上一页的列标题（用于跨页时保留列名）
            prefer_text_parse: 是否优先使用文本解析（适合复杂格式报表）

        Returns:
            (当前页表格列表, 延续到下一页的表格, 延续到下一页的列标题)
        """
        if page_num < 0 or page_num >= len(self.doc.pages):
            return [], None, None

        # 优先策略：prefer_text_parse=True 时先尝试文本解析（适合利润表等复杂格式）
        if prefer_text_parse:
            text_tables = self.extract_text_tables(page_num)
            if text_tables:
                tables = text_tables
            else:
                tables = self.extract_tables(page_num)
        else:
            tables = self.extract_tables(page_num)
            if not tables:
                tables = self.extract_text_tables(page_num)

        if not tables:
            return [], None, None

        result_tables = []
        continuation_table = None
        continuation_columns = None

        for i, df in enumerate(tables):
            if df.empty:
                continue

            df = self._clean_table(df, page_num)

            if df.shape[0] < 5 or df.shape[1] < 2:
                continue

            # 如果有上一页的列标题，并且当前表格列名不完整，尝试使用上一页的列标题
            if prev_columns and not self._has_complete_headers(df):
                df = self._apply_prev_columns(df, prev_columns)

            if prev_table is not None and not prev_table.empty:
                first_row_str = self._get_first_column_key(prev_table)
                current_first_row_str = self._get_first_column_key(df)

                if first_row_str and current_first_row_str:
                    if self._is_table_continuation(prev_table, df):
                        merged = self._merge_continuation_table(prev_table, df)
                        if merged is not None and not merged.empty:
                            continuation_table = merged
                            continuation_columns = (
                                list(df.columns) if df.columns is not None else None
                            )
                            continue

            result_tables.append(df)

            if i == len(tables) - 1:
                continuation_table = df
                continuation_columns = (
                    list(df.columns) if df.columns is not None else None
                )

        return result_tables, continuation_table, continuation_columns

    def _get_first_column_key(self, df: pd.DataFrame) -> str:
        """获取表格第一列第一行的关键值（用于判断跨页延续）"""
        if df.empty or df.shape[0] < 2:
            return None

        try:
            first_val = df.iloc[1, 0]
            if pd.notna(first_val):
                return str(first_val).strip()
        except (IndexError, ValueError):
            pass
        return None

    def _has_complete_headers(self, df: pd.DataFrame) -> bool:
        """
        检查表格是否有完整的列标题

        Args:
            df: 表格DataFrame

        Returns:
            是否有完整列标题
        """
        if df.empty or df.columns is None:
            return False

        header_keywords = [
            "项目",
            "期末",
            "期初",
            "本期",
            "上期",
            "余额",
            "金额",
            "发生",
        ]

        try:
            first_row_text = " ".join(
                [str(v) for v in df.iloc[0].values if pd.notna(v)]
            )
            return any(kw in first_row_text for kw in header_keywords)
        except (IndexError, ValueError):
            return False

    def _apply_prev_columns(self, df: pd.DataFrame, prev_columns: list) -> pd.DataFrame:
        """
        应用上一页的列标题到当前表格

        Args:
            df: 当前表格
            prev_columns: 上一页的列标题

        Returns:
            应用列标题后的表格
        """
        if df.empty or not prev_columns:
            return df

        df = df.copy()

        try:
            first_row = [str(v) for v in df.iloc[0].values if pd.notna(v)]
            first_row_str = " ".join(first_row)

            header_keywords = [
                "项目",
                "期末",
                "期初",
                "本期",
                "上期",
                "余额",
                "金额",
                "发生",
            ]
            is_header_row = any(kw in first_row_str for kw in header_keywords)

            if not is_header_row and len(prev_columns) >= len(df.columns):
                new_columns = prev_columns[: len(df.columns)]
                df.columns = new_columns
        except (IndexError, ValueError):
            pass

        return df

    def _is_table_continuation(
        self, prev_table: pd.DataFrame, curr_table: pd.DataFrame
    ) -> bool:
        """
        判断当前表格是否是上一页表格的延续

        跨页表格的标志：
        1. 第一列第一行的值在上一页最后一个值之后（如果是顺序编号）
        2. 列结构相似（列数相近）
        3. 表头重复出现
        """
        if prev_table.empty or curr_table.empty:
            return False

        if abs(prev_table.shape[1] - curr_table.shape[1]) > 1:
            return False

        header_patterns = [
            r"^项目$",
            r"^项目名称",
            r"期末|期初",
            r"本期|上期",
            r"余额|金额",
            r"2024|2023|2022",
            r"负债|资产|权益",
        ]

        try:
            prev_first_cell = str(prev_table.iloc[0, 0]).strip()
            curr_first_cell = str(curr_table.iloc[0, 0]).strip()

            for pattern in header_patterns:
                if re.match(pattern, curr_first_cell):
                    return True

            first_col_prev = [
                str(v) for v in prev_table.iloc[:, 0].values if pd.notna(v)
            ]
            first_col_curr = [
                str(v) for v in curr_table.iloc[:, 0].values if pd.notna(v)
            ]

            if first_col_prev and first_col_curr:
                if first_col_prev[-1] == first_col_curr[0]:
                    return True

                prev_numeric = self._extract_numeric_suffix(first_col_prev[-1])
                curr_numeric = self._extract_numeric_suffix(first_col_curr[0])
                if prev_numeric is not None and curr_numeric is not None:
                    if curr_numeric == prev_numeric + 1:
                        return True

        except (IndexError, ValueError):
            pass

        return False

    def _extract_numeric_suffix(self, text: str) -> Optional[int]:
        """提取文本末尾的数字"""
        if not text:
            return None
        match = re.search(r"(\d+)$", text.strip())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _merge_continuation_table(
        self, prev_table: pd.DataFrame, curr_table: pd.DataFrame
    ) -> pd.DataFrame:
        """
        合并跨页表格

        Args:
            prev_table: 上一页的表格
            curr_table: 当前页的表格

        Returns:
            合并后的表格
        """
        if prev_table.empty or curr_table.empty:
            return curr_table if not curr_table.empty else prev_table

        try:
            first_row_str = str(curr_table.iloc[0, 0]).strip()
            header_patterns = [
                r"^项目$",
                r"^项目名称",
                r"期末|期初",
                r"本期|上期",
                r"余额|金额",
            ]

            for pattern in header_patterns:
                if re.match(pattern, first_row_str):
                    curr_table = curr_table.iloc[1:]
                    break

            merged = pd.concat([prev_table, curr_table], ignore_index=True)
            return merged

        except (IndexError, ValueError):
            return curr_table if not curr_table.empty else prev_table
