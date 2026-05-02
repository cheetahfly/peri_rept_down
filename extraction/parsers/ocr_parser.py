# -*- coding: utf-8 -*-
"""
OCR表格解析器

使用 OCR 技术从 PDF 中提取文本，支持多种后端：
1. Tesseract OCR (需要安装)
2. OCR.space 云OCR服务
3. Windows OCR

OCR 工作流程：
1. PDF → 图像 (使用 pypdfium2)
2. 图像 → OCR 文本
3. 文本 → 表格结构
"""

import io
import os
import tempfile
import time
import base64
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import re

import pypdfium2 as pdfium


@dataclass
class OCRResult:
    """OCR 识别结果"""
    text: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None


class OCRTableParser:
    """
    OCR 表格解析器

    使用 OCR 从 PDF 中提取财务表格数据。
    适用于 PDF 编码问题导致文本提取乱码的情况。
    """

    TABLE_KEYWORDS = {
        "balance_sheet": ["资产负债表", "资产", "负债", "股东权益", "所有者权益"],
        "income_statement": ["利润表", "营业收入", "净利润", "营业成本"],
        "cash_flow": ["现金流量表", "经营活动", "投资活动", "筹资活动", "现金"]
    }

    NUMERIC_PATTERN = re.compile(r"^[-]?[\d,]+(\.\d+)?$")

    def __init__(self, pdf_path: str, tesseract_cmd: Optional[str] = None):
        """
        初始化 OCR 表格解析器

        Args:
            pdf_path: PDF 文件路径
            tesseract_cmd: Tesseract 命令路径 (可选)
        """
        self.pdf_path = pdf_path
        self.tesseract_cmd = tesseract_cmd or self._find_tesseract()
        self._pdf: Optional[pdfium.PdfDocument] = None
        self._images: Dict[int, Image.Image] = {}

    def _find_tesseract(self) -> Optional[str]:
        """查找 Tesseract 安装路径"""
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\tesseract\tesseract.exe",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        try:
            import shutil
            result = shutil.which("tesseract")
            return result
        except Exception:
            return None

    @property
    def has_tesseract(self) -> bool:
        """检查 Tesseract 是否可用"""
        return self.tesseract_cmd is not None and os.path.exists(self.tesseract_cmd)

    def _load_pdf(self):
        """加载 PDF 文档"""
        if self._pdf is None:
            self._pdf = pdfium.PdfDocument(self.pdf_path)

    @property
    def page_count(self) -> int:
        """总页数"""
        self._load_pdf()
        return len(self._pdf)

    def render_page(self, page_num: int, scale: float = 2.0):
        """
        渲染 PDF 页面为图像

        Args:
            page_num: 页码 (从0开始)
            scale: 缩放比例

        Returns:
            PIL Image 对象
        """
        self._load_pdf()
        if page_num in self._images:
            return self._images[page_num]

        page = self._pdf[page_num]
        pil_image = page.render(scale=scale).to_pil()
        self._images[page_num] = pil_image
        return pil_image

    def ocr_page_tesseract(self, page_num: int, lang: str = "chi_sim+eng") -> OCRResult:
        """
        使用 Tesseract OCR 识别页面

        Args:
            page_num: 页码
            lang: 语言代码 (chi_sim=简体中文, eng=英文)

        Returns:
            OCRResult 对象
        """
        if not self.has_tesseract:
            return OCRResult(text="", confidence=0.0)

        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

            image = self.render_page(page_num)

            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config="--psm 6"  # Assume uniform block of text
            )

            data = pytesseract.image_to_data(
                image,
                lang=lang,
                output_type=pytesseract.Output.DICT
            )

            confidences = [int(c) for c in data["conf"] if c != "-1"]
            avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0

            return OCRResult(text=text, confidence=avg_confidence)

        except Exception as e:
            return OCRResult(text=f"OCR Error: {str(e)}", confidence=0.0)

    def ocr_page_cloud(self, page_num: int, api_key: Optional[str] = None) -> OCRResult:
        """
        使用云 OCR API 识别页面 (OCR.space)

        Args:
            page_num: 页码
            api_key: OCR.space API 密钥

        Returns:
            OCRResult 对象
        """
        try:
            import requests
            from PIL import Image
            import base64

            image = self.render_page(page_num)
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            url = "https://api.ocr.space/parse/image"
            headers = {"apikey": api_key} if api_key else {}
            data = {"base64Image": f"data:image/png;base64,{img_base64}"}

            response = requests.post(url, data=data, headers=headers, timeout=30)
            result = response.json()

            if result.get("ParsedResults"):
                text = "\n".join(
                    pr["ParsedText"] for pr in result["ParsedResults"]
                )
                confidence = sum(
                    pr.get("TextOverlay", {}).get("MeanConfidence", 0)
                    for pr in result["ParsedResults"]
                ) / len(result["ParsedResults"]) / 100
                return OCRResult(text=text, confidence=confidence)

            return OCRResult(text="", confidence=0.0)

        except Exception as e:
            return OCRResult(text=f"Cloud OCR Error: {str(e)}", confidence=0.0)

    def find_financial_statement_pages(self, statement_type: str) -> List[int]:
        """
        查找财务报表页面

        Args:
            statement_type: 报表类型 (balance_sheet/income_statement/cash_flow)

        Returns:
            匹配的页码列表
        """
        keywords = self.TABLE_KEYWORDS.get(statement_type, [])
        matching_pages = []

        for i in range(self.page_count):
            try:
                if self.has_tesseract:
                    result = self.ocr_page_tesseract(i)
                else:
                    continue

                for keyword in keywords:
                    if keyword in result.text:
                        matching_pages.append(i)
                        break
            except Exception:
                continue

        return matching_pages

    def _parse_text_to_table(self, text: str) -> pd.DataFrame:
        """
        将 OCR 文本解析为表格

        Args:
            text: OCR 识别的文本

        Returns:
            表格 DataFrame
        """
        lines = text.split("\n")
        rows = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = re.split(r"\s{2,}", line)

            if len(parts) >= 2:
                cleaned_parts = []
                for part in parts:
                    part = part.strip()
                    if part:
                        cleaned_parts.append(part)

                if len(cleaned_parts) >= 2:
                    rows.append(cleaned_parts)

        if not rows:
            return pd.DataFrame()

        max_cols = max(len(row) for row in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        df = pd.DataFrame(rows)

        if df.shape[1] == 4:
            df.columns = ["项目", "附注", "2025年", "2024年"]
        elif df.shape[1] == 3:
            df.columns = ["项目", "2025年", "2024年"]
        elif df.shape[1] == 2:
            df.columns = ["项目", "数值"]
        else:
            df.columns = [f"col_{i}" for i in range(df.shape[1])]

        return df

    def extract_balance_sheet(self, start_page: Optional[int] = None) -> pd.DataFrame:
        """
        提取资产负债表

        Args:
            start_page: 起始页码 (如果已知)

        Returns:
            资产负债表 DataFrame
        """
        if start_page is None:
            pages = self.find_financial_statement_pages("balance_sheet")
            if not pages:
                return pd.DataFrame()
            start_page = pages[0]

        if self.has_tesseract:
            result = self.ocr_page_tesseract(start_page)
            return self._parse_text_to_table(result.text)

        return pd.DataFrame()

    def extract_income_statement(self, start_page: Optional[int] = None) -> pd.DataFrame:
        """
        提取利润表

        Args:
            start_page: 起始页码 (如果已知)

        Returns:
            利润表 DataFrame
        """
        if start_page is None:
            pages = self.find_financial_statement_pages("income_statement")
            if not pages:
                return pd.DataFrame()
            start_page = pages[0]

        if self.has_tesseract:
            result = self.ocr_page_tesseract(start_page)
            return self._parse_text_to_table(result.text)

        return pd.DataFrame()

    def extract_cash_flow(self, start_page: Optional[int] = None) -> pd.DataFrame:
        """
        提取现金流量表

        Args:
            start_page: 起始页码 (如果已知)

        Returns:
            现金流量表 DataFrame
        """
        if start_page is None:
            pages = self.find_financial_statement_pages("cash_flow")
            if not pages:
                return pd.DataFrame()
            start_page = pages[0]

        if self.has_tesseract:
            result = self.ocr_page_tesseract(start_page)
            return self._parse_text_to_table(result.text)

        return pd.DataFrame()


class ImageOrcParser:
    """
    图像 OCR 解析器

    直接从图像文件进行 OCR 识别，适用于：
    - PDF 转换为图像后的识别
    - 扫描文档识别
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        self.tesseract_cmd = tesseract_cmd

    @property
    def has_tesseract(self) -> bool:
        if not self.tesseract_cmd:
            try:
                import shutil
                self.tesseract_cmd = shutil.which("tesseract")
            except Exception:
                return False
        return os.path.exists(self.tesseract_cmd) if self.tesseract_cmd else False

    def ocr_image(self, image_path: str, lang: str = "chi_sim+eng") -> OCRResult:
        """
        识别图像

        Args:
            image_path: 图像路径
            lang: 语言代码

        Returns:
            OCRResult 对象
        """
        if not self.has_tesseract:
            return OCRResult(text="", confidence=0.0)

        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            image = Image.open(image_path)

            text = pytesseract.image_to_string(image, lang=lang)
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

            confidences = [int(c) for c in data["conf"] if c != "-1"]
            avg_conf = sum(confidences) / len(confidences) / 100 if confidences else 0

            return OCRResult(text=text, confidence=avg_conf)

        except Exception as e:
            return OCRResult(text=f"OCR Error: {str(e)}", confidence=0.0)

    def ocr_image_from_bytes(self, image_bytes: bytes, lang: str = "chi_sim+eng") -> OCRResult:
        """
        从字节数据识别图像

        Args:
            image_bytes: 图像字节数据
            lang: 语言代码

        Returns:
            OCRResult 对象
        """
        if not self.has_tesseract:
            return OCRResult(text="", confidence=0.0)

        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            image = Image.open(io.BytesIO(image_bytes))

            text = pytesseract.image_to_string(image, lang=lang)
            data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

            confidences = [int(c) for c in data["conf"] if c != "-1"]
            avg_conf = sum(confidences) / len(confidences) / 100 if confidences else 0

            return OCRResult(text=text, confidence=avg_conf)

        except Exception as e:
            return OCRResult(text=f"OCR Error: {str(e)}", confidence=0.0)


class OCREngineType(Enum):
    """OCR引擎类型"""
    TESSERACT = "tesseract"
    OCR_SPACE = "ocr_space"
    WINDOWS = "windows"


class OCRSpaceParser:
    """
    OCR.space 云OCR解析器

    使用 OCR.space API 进行中文识别，无需本地安装。
    免费额度：25000次/月

    API文档：https://ocr.space/ocrapi
    """

    API_URL = "https://api.ocr.space/parse/image"

    def __init__(self, api_key: Optional[str] = None, language: str = "chs"):
        """
        初始化 OCR.space 解析器

        Args:
            api_key: OCR.space API密钥（可选，不提供则使用匿名API有频率限制）
            language: 语言代码 (chs=简体中文,cht=繁体中文,eng=英文)
        """
        self.api_key = api_key or ""
        self.language = language
        self._session_headers = {
            "apikey": self.api_key
        } if self.api_key else {}

    def _image_to_base64(self, image: "Image.Image") -> str:
        """将PIL Image转为base64字符串"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def ocr_image(self, image: "Image.Image", timeout: int = 60) -> OCRResult:
        """
        识别单张图像

        Args:
            image: PIL Image对象
            timeout: 超时时间（秒）

        Returns:
            OCRResult对象
        """
        try:
            import base64
            import requests

            img_base64 = self._image_to_base64(image)
            data = {
                "base64Image": f"data:image/png;base64,{img_base64}",
                "language": self.language,
                "isOverlayRequired": "true",
                "detectOrientation": "true",
                "scale": "true",
                "OCREngine": "2"
            }

            response = requests.post(
                self.API_URL,
                data=data,
                headers=self._session_headers,
                timeout=timeout
            )

            if response.status_code == 403:
                return OCRResult(
                    text="OCR.space API需要API密钥。请访问 https://ocr.space/ocrapi 免费注册获取API密钥。",
                    confidence=0.0
                )

            result = response.json()

            if result.get("ParsedResults"):
                parsed_texts = []
                confidences = []

                for pr in result["ParsedResults"]:
                    text = pr.get("ParsedText", "")
                    conf = pr.get("TextOverlay", {}).get("MeanConfidence", 0)
                    parsed_texts.append(text)
                    confidences.append(conf)

                full_text = "\n".join(parsed_texts)
                avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0

                return OCRResult(text=full_text, confidence=avg_confidence)

            error_msg = result.get("ErrorMessage", ["Unknown error"])
            if isinstance(error_msg, list):
                error_msg = error_msg[0] if error_msg else "Unknown error"
            return OCRResult(text=f"OCR Error: {error_msg}", confidence=0.0)

        except Exception as e:
            return OCRResult(text=f"OCR.space Error: {str(e)}", confidence=0.0)

    def ocr_pdf_page(self, pdf_path: str, page_num: int, scale: float = 2.0) -> OCRResult:
        """
        识别PDF指定页面

        Args:
            pdf_path: PDF文件路径
            page_num: 页码（从0开始）
            scale: 缩放比例

        Returns:
            OCRResult对象
        """
        try:
            from PIL import Image

            pdf = pdfium.PdfDocument(pdf_path)
            page = pdf[page_num]
            pil_image = page.render(scale=scale).to_pil()
            pdf.close()

            return self.ocr_image(pil_image)

        except Exception as e:
            return OCRResult(text=f"PDF render error: {str(e)}", confidence=0.0)


class CloudOCRParser:
    """
    云OCR表格解析器

    封装多个云OCR服务，自动切换：
    1. OCR.space (默认，免费额度大)
    """

    def __init__(self, pdf_path: str, api_key: Optional[str] = None):
        """
        初始化云OCR解析器

        Args:
            pdf_path: PDF文件路径
            api_key: OCR API密钥
        """
        self.pdf_path = pdf_path
        self.ocr_space = OCRSpaceParser(api_key=api_key)

    @property
    def page_count(self) -> int:
        """总页数"""
        try:
            pdf = pdfium.PdfDocument(self.pdf_path)
            count = len(pdf)
            pdf.close()
            return count
        except:
            return 0

    def render_page(self, page_num: int, scale: float = 2.0):
        """渲染PDF页面为图像"""
        try:
            pdf = pdfium.PdfDocument(self.pdf_path)
            page = pdf[page_num]
            pil_image = page.render(scale=scale).to_pil()
            pdf.close()
            return pil_image
        except:
            return None

    def ocr_page(self, page_num: int, scale: float = 2.0) -> OCRResult:
        """
        OCR识别指定页面

        Args:
            page_num: 页码
            scale: 缩放比例

        Returns:
            OCRResult对象
        """
        image = self.render_page(page_num, scale)
        if image is None:
            return OCRResult(text="", confidence=0.0)
        return self.ocr_space.ocr_image(image)

    def find_statement_pages(self, statement_type: str, max_pages: int = 50) -> List[int]:
        """
        查找财务报表页面

        Args:
            statement_type: 报表类型 (balance_sheet/income_statement/cash_flow)
            max_pages: 最大搜索页数

        Returns:
            页码列表
        """
        keywords = {
            "balance_sheet": ["资产负债表", "资产", "负债", "股东权益", "所有者权益"],
            "income_statement": ["利润表", "营业收入", "净利润", "营业成本"],
            "cash_flow": ["现金流量表", "经营活动", "投资活动", "筹资活动", "现金"]
        }.get(statement_type, [])

        matching_pages = []
        total_pages = min(self.page_count, max_pages)

        for i in range(total_pages):
            result = self.ocr_page(i)
            if result.confidence > 0:
                for keyword in keywords:
                    if keyword in result.text:
                        matching_pages.append(i)
                        break

        return matching_pages


def create_ocr_parser(pdf_path: str, backend: str = "auto", api_key: Optional[str] = None) -> Union[OCRTableParser, CloudOCRParser]:
    """
    创建 OCR 解析器

    Args:
        pdf_path: PDF 文件路径
        backend: OCR 后端 ("tesseract", "cloud", "auto")
        api_key: 云OCR API密钥

    Returns:
        OCR解析器实例
    """
    if backend == "cloud" or (backend == "auto" and api_key):
        return CloudOCRParser(pdf_path, api_key)

    parser = OCRTableParser(pdf_path)

    if backend == "auto":
        if parser.has_tesseract:
            return parser
        return CloudOCRParser(pdf_path, api_key)

    return parser
