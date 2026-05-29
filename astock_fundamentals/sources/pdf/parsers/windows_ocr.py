# -*- coding: utf-8 -*-
"""
Windows OCR 后端

使用 Windows.Media.Ocr API 进行 OCR 识别，
无需安装额外的 Tesseract 二进制文件。
"""

import io
from typing import Optional
from dataclasses import dataclass
import numpy as np

try:
    import pypdfium2 as pdfium
    from PIL import Image
    HAS_PYPDFIUM2 = True
except ImportError:
    HAS_PYPDFIUM2 = False


@dataclass
class WindowsOCRResult:
    """Windows OCR 识别结果"""
    text: str
    confidence: float
    words: list


class WindowsOCREngine:
    """
    Windows OCR 引擎

    使用 Windows.Media.Ocr API 进行中文和英文识别。
    无需安装 Tesseract，适用于 Windows 10+ 系统。
    """

    def __init__(self, language: str = "zh-CN"):
        """
        初始化 Windows OCR 引擎

        Args:
            language: OCR 语言代码 (zh-CN=简体中文, en=英文)
        """
        self.language = language
        self._engine: Optional[object] = None
        self._initialize()

    def _initialize(self):
        """初始化 OCR 引擎"""
        try:
            import System
            from Windows.Media.Ocr import OcrEngine
            from Windows.Graphics.Imaging import BitmapDecoder
            from Windows.Storage import Streams

            languages = OcrEngine.AvailableRecognizerLanguages
            for lang in languages:
                if lang.LanguageTag == self.language:
                    self._engine = OcrEngine.TryCreateFromLanguage(lang)
                    break

            if self._engine is None:
                self._engine = OcrEngine.TryCreateFromUserProfileLanguages()

        except ImportError:
            pass

    @property
    def is_available(self) -> bool:
        """检查 OCR 引擎是否可用"""
        return self._engine is not None

    def recognize_from_bytes(self, image_bytes: bytes) -> WindowsOCRResult:
        """
        从字节数据识别图像

        Args:
            image_bytes: 图像字节数据

        Returns:
            WindowsOCRResult 对象
        """
        if not self.is_available:
            return WindowsOCRResult(text="", confidence=0.0, words=[])

        try:
            import System
            from Windows.Graphics.Imaging import BitmapDecoder
            from Windows.Storage.Streams import DataReader

            stream = io.BytesIO(image_bytes)
            decoder = BitmapDecoder.CreateFromStreamAsync(stream)
            bitmap = decoder.GetAt(0)

            result = self._engine.RecognizeAsync(bitmap)

            text = result.Text
            words = []

            if hasattr(result, 'Lines'):
                for line in result.Lines:
                    for word in line.Words:
                        words.append({
                            'text': word.Text,
                            'bounding_box': (word.BoundingRect.X, word.BoundingRect.Y,
                                            word.BoundingRect.Width, word.BoundingRect.Height)
                        })

            confidence = 0.9 if text else 0.0

            return WindowsOCRResult(text=text, confidence=confidence, words=words)

        except Exception as e:
            return WindowsOCRResult(text=f"Windows OCR Error: {str(e)}", confidence=0.0, words=[])

    def recognize_from_pil_image(self, pil_image: Image.Image) -> WindowsOCRResult:
        """
        从 PIL Image 识别

        Args:
            pil_image: PIL Image 对象

        Returns:
            WindowsOCRResult 对象
        """
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        return self.recognize_from_bytes(buffered.getvalue())


class WindowsOCRParser:
    """
    Windows OCR 表格解析器

    使用 Windows OCR 从 PDF 中提取财务表格数据。
    适用于无法安装 Tesseract 的 Windows 环境。
    """

    TABLE_KEYWORDS = {
        "balance_sheet": ["资产负债表", "资产", "负债", "股东权益", "所有者权益"],
        "income_statement": ["利润表", "营业收入", "净利润", "营业成本"],
        "cash_flow": ["现金流量表", "经营活动", "投资活动", "筹资活动", "现金"]
    }

    def __init__(self, pdf_path: str, language: str = "zh-CN"):
        """
        初始化 Windows OCR 解析器

        Args:
            pdf_path: PDF 文件路径
            language: OCR 语言
        """
        self.pdf_path = pdf_path
        self.language = language
        self._ocr_engine = WindowsOCREngine(language)
        self._pdf: Optional[object] = None
        self._images = {}

    @property
    def is_available(self) -> bool:
        """检查 OCR 是否可用"""
        return self._ocr_engine.is_available if self._ocr_engine else False

    def _load_pdf(self):
        """加载 PDF 文档"""
        if not HAS_PYPDFIUM2:
            return

        if self._pdf is None:
            self._pdf = pdfium.PdfDocument(self.pdf_path)

    @property
    def page_count(self) -> int:
        """总页数"""
        self._load_pdf()
        if self._pdf:
            return len(self._pdf)
        return 0

    def render_page(self, page_num: int, scale: float = 2.0) -> Optional[Image.Image]:
        """
        渲染 PDF 页面为图像

        Args:
            page_num: 页码
            scale: 缩放比例

        Returns:
            PIL Image 对象
        """
        self._load_pdf()
        if page_num in self._images:
            return self._images[page_num]

        if not self._pdf:
            return None

        page = self._pdf[page_num]
        pil_image = page.render(scale=scale).to_pil()
        self._images[page_num] = pil_image
        return pil_image

    def ocr_page(self, page_num: int) -> WindowsOCRResult:
        """
        OCR 识别单页

        Args:
            page_num: 页码

        Returns:
            WindowsOCRResult 对象
        """
        image = self.render_page(page_num)
        if image is None:
            return WindowsOCRResult(text="", confidence=0.0, words=[])

        return self._ocr_engine.recognize_from_pil_image(image)

    def find_statement_pages(self, statement_type: str) -> list:
        """
        查找财务报表页面

        Args:
            statement_type: 报表类型

        Returns:
            页码列表
        """
        keywords = self.TABLE_KEYWORDS.get(statement_type, [])
        pages = []

        for i in range(self.page_count):
            result = self.ocr_page(i)
            for keyword in keywords:
                if keyword in result.text:
                    pages.append(i)
                    break

        return pages

    def extract_balance_sheet(self) -> str:
        """提取资产负债表文本"""
        pages = self.find_statement_pages("balance_sheet")
        if not pages:
            return ""

        result = self.ocr_page(pages[0])
        return result.text

    def extract_income_statement(self) -> str:
        """提取利润表文本"""
        pages = self.find_statement_pages("income_statement")
        if not pages:
            return ""

        result = self.ocr_page(pages[0])
        return result.text

    def extract_cash_flow(self) -> str:
        """提取现金流量表文本"""
        pages = self.find_statement_pages("cash_flow")
        if not pages:
            return ""

        result = self.ocr_page(pages[0])
        return result.text
