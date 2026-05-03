# -*- coding: utf-8 -*-
"""
混合PDF解析器 - 自动检测乱码并切换解析策略

当检测到PDF文本提取出现乱码时，自动尝试切换到其他解析器。
支持多种模式，按优先级依次尝试：
1. pdfplumber (默认，用于正常PDF)
2. PyMuPDF (用于pdfplumber失败的CID字体PDF)
3. HtmlParser (用于pdf2htmlEX输出，带<table>标签)
4. LibreOfficeTableParser (用于LibreOffice输出，<p>标签结构)
5. OCRTableParser (用于OCR识别，自定义字体编码PDF)
"""

import os
import tempfile
import shutil
from typing import List, Optional, Tuple
import pandas as pd

from extraction.parsers.pdf_parser import PdfParser
from extraction.parsers.html_parser import HtmlParser
from extraction.parsers.lo_table_parser import LibreOfficeTableParser
from extraction.parsers.html_converter import convert_pdf_to_html, is_garbled_text

try:
    from extraction.parsers.pymupdf_parser import PyMuPDFParser
    HAS_PYMUPDF = True
except ImportError:
    PyMuPDFParser = None
    HAS_PYMUPDF = False

try:
    from extraction.parsers.ocr_parser import OCRTableParser
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    OCRTableParser = None


class HybridParser:
    """
    混合PDF解析器

    优先使用pdfplumber提取文本，如果检测到乱码，
    则自动尝试PyMuPDF -> HTML -> OCR。
    """

    def __init__(self, pdf_path: str, force_html: bool = False, force_lo: bool = False, force_ocr: bool = False, force_pymupdf: bool = False):
        """
        初始化混合解析器

        Args:
            pdf_path: PDF文件路径
            force_html: 是否强制使用HTML模式(pdf2htmlEX)
            force_lo: 是否强制使用LibreOffice模式
            force_ocr: 是否强制使用OCR模式
            force_pymupdf: 是否强制使用PyMuPDF模式
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.pdf_path = pdf_path
        self.force_html = force_html
        self.force_lo = force_lo
        self.force_ocr = force_ocr
        self.force_pymupdf = force_pymupdf
        self._pdf_parser: Optional[PdfParser] = None
        self._pymupdf_parser: Optional[PyMuPDFParser] = None
        self._html_parser: Optional[HtmlParser] = None
        self._lo_parser: Optional[LibreOfficeTableParser] = None
        self._ocr_parser: Optional[OCRTableParser] = None
        self._use_html = False
        self._use_lo = False
        self._use_ocr = False
        self._use_pymupdf = False
        self._html_path: Optional[str] = None
        self._temp_dir: Optional[str] = None
        self._parsing_method = "pdfplumber"

    def _initialize(self):
        """初始化解析器"""
        if self._pdf_parser is None:
            self._pdf_parser = PdfParser(self.pdf_path)
            self._check_and_convert_if_needed()

    def _check_and_convert_if_needed(self):
        """检查是否需要切换解析策略"""
        if self.force_ocr:
            self._initialize_ocr()
            return

        if self.force_lo:
            self._convert_to_lo()
            return

        if self.force_html:
            self._convert_to_html()
            return

        if self.force_pymupdf:
            self._initialize_pymupdf()
            return

        # 检查多个页面，如果任何一页检测到乱码就切换解析器
        # CID字体的乱码可能在某些页面上特别明显
        garbled_pages = []
        for page_num in range(min(20, self._pdf_parser.page_count)):
            page_text = self._pdf_parser.extract_text(page_num)
            if len(page_text) > 50 and is_garbled_text(page_text):
                garbled_pages.append(page_num)

        if garbled_pages:
            print(f"pdfplumber检测到{len(garbled_pages)}页乱码(页{garbled_pages[:5]}...)，尝试PyMuPDF...")
            if HAS_PYMUPDF:
                self._initialize_pymupdf()
                if not self._use_pymupdf:
                    print(f"PyMuPDF也失败，尝试HTML转换...")
                    self._convert_to_html()
            else:
                print(f"PyMuPDF不可用，尝试HTML转换...")
                self._convert_to_html()

    def _initialize_pymupdf(self):
        """初始化PyMuPDF解析器"""
        if not HAS_PYMUPDF:
            print("PyMuPDF不可用")
            return

        try:
            self._pymupdf_parser = PyMuPDFParser(self.pdf_path)
            # 测试PyMuPDF是否能正常提取文本 - 检查多个页面包括内容页
            # 只检查前面的页面，因为后面的页面可能本来就是乱码（如页眉页脚）
            page_count = self._pymupdf_parser.page_count
            test_pages = [0, 1, 2, 3, 4, min(10, page_count-1)]
            sample_text = ""
            for p in test_pages:
                sample_text += self._pymupdf_parser.extract_text(p)

            if is_garbled_text(sample_text):
                print("PyMuPDF也检测到乱码，关闭并回退")
                self._pymupdf_parser.close()
                self._pymupdf_parser = None
                return

            self._use_pymupdf = True
            self._parsing_method = "pymupdf"
            print("PyMuPDF解析器初始化成功")
        except (OSError, ValueError, RuntimeError) as e:
            print(f"PyMuPDF初始化失败: {e}")
            if self._pymupdf_parser:
                self._pymupdf_parser.close()
                self._pymupdf_parser = None

    def _initialize_ocr(self):
        """初始化OCR解析器"""
        if not HAS_OCR:
            print("OCR模块不可用，请安装pytesseract和Tesseract OCR")
            return

        self._ocr_parser = OCRTableParser(self.pdf_path)
        if self._ocr_parser.has_tesseract:
            self._use_ocr = True
            print(f"OCR解析器初始化成功 (Tesseract available)")
        else:
            print("Tesseract OCR未安装，请先安装Tesseract")

    def _convert_to_html(self):
        """转换为HTML"""
        # 清理旧的临时目录
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)
        self._temp_dir = tempfile.mkdtemp()
        success, result = convert_pdf_to_html(self.pdf_path, self._temp_dir)

        if success:
            self._html_path = result
            self._use_html = True
            self._html_parser = HtmlParser(result)
            print(f"HTML转换成功: {result}")
        else:
            print(f"HTML转换失败: {result}")

    def _convert_to_lo(self):
        """转换为HTML (LibreOffice模式)"""
        # 清理旧的临时目录
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)
        self._temp_dir = tempfile.mkdtemp()
        pdf_path_abs = os.path.abspath(self.pdf_path)
        success, result = convert_pdf_to_html(pdf_path_abs, self._temp_dir)

        if success:
            self._html_path = result
            self._use_lo = True
            self._lo_parser = LibreOfficeTableParser(result)
            print(f"LibreOffice HTML解析器初始化成功: {result}")
        else:
            # 如果转换失败，检查PDF同目录下是否存在已转换的HTML
            pdf_dir = os.path.dirname(self.pdf_path)
            pdf_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
            potential_html = os.path.join(pdf_dir, pdf_name + ".html")
            if os.path.exists(potential_html):
                self._html_path = potential_html
                self._use_lo = True
                self._lo_parser = LibreOfficeTableParser(potential_html)
                print(f"使用现有HTML文件: {potential_html}")
            else:
                print(f"HTML转换失败，且未找到现有HTML文件: {result}")

    @property
    def page_count(self) -> int:
        """总页数"""
        self._initialize()
        if self._use_ocr and self._ocr_parser:
            return self._ocr_parser.page_count
        if self._use_lo and self._lo_parser:
            return self._lo_parser.page_count if hasattr(self._lo_parser, 'page_count') else 1
        if self._use_html and self._html_parser:
            return self._html_parser.page_count
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.page_count
        return self._pdf_parser.page_count

    @property
    def parsing_method(self) -> str:
        """当前使用的解析方法"""
        return self._parsing_method

    def extract_text(self, page_num: int) -> str:
        """
        提取页面文本

        Args:
            page_num: 页码（从0开始）

        Returns:
            页面文本内容
        """
        self._initialize()
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.extract_text(page_num)
        if self._use_html and self._html_parser:
            return self._html_parser.extract_text(page_num)
        return self._pdf_parser.extract_text(page_num)

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
        self._initialize()
        # PyMuPDF doesn't support table extraction, fall back to pdfplumber for tables
        if self._use_pymupdf and self._pymupdf_parser:
            tables = self._pdf_parser.extract_tables(page_num, min_rows, min_cols)
            if tables:
                return tables
        if self._use_html and self._html_parser:
            return self._html_parser.extract_tables(page_num, min_rows, min_cols)
        return self._pdf_parser.extract_tables(page_num, min_rows, min_cols)

    def find_pages(
        self, keywords: List[str], case_sensitive: bool = False
    ) -> List[int]:
        """
        搜索包含关键词的页面

        Args:
            keywords: 关键词列表
            case_sensitive: 是否大小写敏感

        Returns:
            匹配的页码列表
        """
        self._initialize()
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.find_pages(keywords, case_sensitive)
        if self._use_html and self._html_parser:
            return self._html_parser.find_pages(keywords, case_sensitive)
        return self._pdf_parser.find_pages(keywords, case_sensitive)

    def extract_text_range(self, start_page: int, end_page: int) -> str:
        """
        提取多个页面的文本

        Args:
            start_page: 起始页码
            end_page: 结束页码

        Returns:
            合并后的文本
        """
        self._initialize()
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.extract_text_range(start_page, end_page)
        if self._use_html and self._html_parser:
            return self._html_parser.extract_text_range(start_page, end_page)
        return self._pdf_parser.extract_text_range(start_page, end_page)

    def get_pages_range(self, start_page: int, end_page: int) -> List[int]:
        """
        获取页面范围

        Args:
            start_page: 起始页码
            end_page: 结束页码

        Returns:
            页码列表
        """
        self._initialize()
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.get_pages_range(start_page, end_page)
        if self._use_html and self._html_parser:
            return self._html_parser.get_pages_range(start_page, end_page)
        return self._pdf_parser.get_pages_range(start_page, end_page)

    def extract_all_text(self) -> str:
        """
        提取所有页面的文本

        Returns:
            合并后的所有文本
        """
        self._initialize()
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.extract_all_text()
        if self._use_html and self._html_parser:
            return self._html_parser.extract_all_text()
        return self._pdf_parser.extract_all_text()

    def extract_tables_with_continuation(
        self, page_num: int, prev_table: pd.DataFrame = None, prev_columns: list = None
    ) -> Tuple[List[pd.DataFrame], Optional[pd.DataFrame], Optional[list]]:
        """
        提取页面表格，并处理跨页表格延续

        Args:
            page_num: 页码（从0开始）
            prev_table: 上一页的表格
            prev_columns: 上一页的列标题

        Returns:
            (当前页表格列表, 延续到下一页的表格, 延续到下一页的列标题)
        """
        self._initialize()
        # PyMuPDF doesn't support table extraction, fall back to pdfplumber for tables
        # Use prefer_text_parse=True for complex financial tables
        if self._use_pymupdf and self._pymupdf_parser:
            result = self._pdf_parser.extract_tables_with_continuation(
                page_num, prev_table, prev_columns, prefer_text_parse=True
            )
            if result[0]:  # If we got tables from pdfplumber
                return result
        if self._use_html and self._html_parser:
            return self._html_parser.extract_tables(page_num, 3, 2), None, None
        return self._pdf_parser.extract_tables_with_continuation(
            page_num, prev_table, prev_columns, prefer_text_parse=True
        )

    def detect_unit(self, page_num: int = None) -> Tuple[str, float]:
        """
        检测文档中的数值单位

        Args:
            page_num: 页码（可选）

        Returns:
            (单位名称, 乘数)
        """
        self._initialize()
        if self._use_pymupdf and self._pymupdf_parser:
            return self._pymupdf_parser.detect_unit(page_num)
        if self._use_html and self._html_parser:
            return (
                self._html_parser.detect_unit(page_num)
                if hasattr(self._html_parser, "detect_unit")
                else ("元", 1)
            )
        return self._pdf_parser.detect_unit(page_num)

    def close(self):
        """关闭解析器并清理临时文件"""
        if self._pdf_parser:
            self._pdf_parser.close()
            self._pdf_parser = None

        if self._pymupdf_parser:
            self._pymupdf_parser.close()
            self._pymupdf_parser = None

        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)
            self._temp_dir = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @property
    def is_using_html(self) -> bool:
        """是否使用HTML模式"""
        return self._use_html

    @property
    def is_using_lo(self) -> bool:
        """是否使用LibreOffice模式"""
        return self._use_lo

    @property
    def is_using_ocr(self) -> bool:
        """是否使用OCR模式"""
        return self._use_ocr

    @property
    def is_using_pymupdf(self) -> bool:
        """是否使用PyMuPDF模式"""
        return self._use_pymupdf

    @property
    def html_path(self) -> Optional[str]:
        """获取HTML文件路径（如果已转换）"""
        return self._html_path

    def extract_balance_sheet(self) -> pd.DataFrame:
        """
        提取资产负债表（LibreOffice模式专用）

        Returns:
            资产负债表DataFrame
        """
        self._initialize()
        if self._use_lo and self._lo_parser:
            return self._lo_parser.extract_balance_sheet()
        return pd.DataFrame()

    def extract_income_statement(self) -> pd.DataFrame:
        """
        提取利润表（LibreOffice模式专用）

        Returns:
            利润表DataFrame
        """
        self._initialize()
        if self._use_lo and self._lo_parser:
            return self._lo_parser.extract_income_statement()
        return pd.DataFrame()

    def extract_cash_flow(self) -> pd.DataFrame:
        """
        提取现金流量表（LibreOffice模式专用）

        Returns:
            现金流量表DataFrame
        """
        self._initialize()
        if self._use_lo and self._lo_parser:
            return self._lo_parser.extract_cash_flow()
        return pd.DataFrame()

    def extract_balance_sheet_ocr(self) -> pd.DataFrame:
        """
        使用OCR提取资产负债表

        Returns:
            资产负债表DataFrame
        """
        self._initialize()
        if self._use_ocr and self._ocr_parser:
            return self._ocr_parser.extract_balance_sheet()
        return pd.DataFrame()

    def extract_income_statement_ocr(self) -> pd.DataFrame:
        """
        使用OCR提取利润表

        Returns:
            利润表DataFrame
        """
        self._initialize()
        if self._use_ocr and self._ocr_parser:
            return self._ocr_parser.extract_income_statement()
        return pd.DataFrame()

    def extract_cash_flow_ocr(self) -> pd.DataFrame:
        """
        使用OCR提取现金流量表

        Returns:
            现金流量表DataFrame
        """
        self._initialize()
        if self._use_ocr and self._ocr_parser:
            return self._ocr_parser.extract_cash_flow()
        return pd.DataFrame()
