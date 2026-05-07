# -*- coding: utf-8 -*-
"""
PDF到HTML转换器 - 支持多种工具将PDF转换为HTML

当pdfplumber/PyMuPDF遇到自定义字体编码的PDF出现乱码时，
可以使用这些工具转换为HTML后解析。
"""

import os
import subprocess
import tempfile
import shutil
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PdfToHtmlConverter:
    """PDF转HTML转换器"""

    def __init__(self):
        self.temp_dir = None

    def convert(
        self, pdf_path: str, output_dir: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        将PDF转换为HTML

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（可选）

        Returns:
            (成功标志, 输出文件路径或错误信息)
        """
        if not os.path.exists(pdf_path):
            return False, f"PDF文件不存在: {pdf_path}"

        if output_dir is None:
            self.temp_dir = tempfile.mkdtemp()
            output_dir = self.temp_dir
        else:
            os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        html_path = os.path.join(output_dir, f"{base_name}.html")

        if self._try_pdf2htmlEX(pdf_path, html_path):
            return True, html_path

        if self._try_libreoffice(pdf_path, output_dir, base_name):
            found = self._find_html_in_dir(output_dir, base_name)
            if found:
                return True, found

        if self._try_poppler(pdf_path, html_path):
            return True, html_path

        return False, "所有转换方法均失败"

    def _try_pdf2htmlEX(self, pdf_path: str, output_path: str) -> bool:
        """尝试使用pdf2htmlEX转换"""
        try:
            result = subprocess.run(
                ["pdf2htmlEX", "--no-drm", "1", pdf_path, output_path],
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0 and os.path.exists(output_path)
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _try_libreoffice(self, pdf_path: str, output_dir: str, base_name: str) -> bool:
        """尝试使用LibreOffice转换"""
        import pathlib

        def to_windows_abs_path(path: str) -> str:
            abs_path = os.path.abspath(path)
            return str(pathlib.Path(abs_path))

        pdf_path_win = to_windows_abs_path(pdf_path)
        output_dir_win = to_windows_abs_path(output_dir)

        libreoffice_cmds = [
            "soffice",
            "libreoffice",
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
        ]

        for cmd in libreoffice_cmds:
            try:
                result = subprocess.run(
                    [cmd, "--headless", "--convert-to", "html", "--outdir", output_dir_win, pdf_path_win],
                    capture_output=True,
                    timeout=180,
                )
                if result.returncode == 0:
                    return True
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        return False

    def _try_poppler(self, pdf_path: str, output_path: str) -> bool:
        """尝试使用poppler-utils的pdftotext"""
        try:
            result = subprocess.run(
                ["pdftotext", "-htmlmeta", pdf_path, output_path],
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0 and os.path.exists(output_path)
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _find_html_in_dir(self, output_dir: str, base_name: str) -> Optional[str]:
        """在目录中查找生成的HTML文件"""
        for fname in os.listdir(output_dir):
            if fname.endswith(".html") and base_name in fname:
                return os.path.join(output_dir, fname)
        for fname in os.listdir(output_dir):
            if fname.endswith(".html"):
                return os.path.join(output_dir, fname)
        return None

    def cleanup(self):
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None


def convert_pdf_to_html(
    pdf_path: str, output_dir: Optional[str] = None
) -> Tuple[bool, str]:
    """
    便捷函数：将PDF转换为HTML

    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录（可选）

    Returns:
        (成功标志, 输出文件路径或错误信息)
    """
    converter = PdfToHtmlConverter()
    try:
        return converter.convert(pdf_path, output_dir)
    finally:
        converter.cleanup()


def is_garbled_text(text: str) -> bool:
    """
    Detect garbled CID-font text in PDF extracts.

    Detection strategies (any one trigger is sufficient):
    1. Replacement char (U+FFFD) ratio > 30%
    2. Low Chinese ratio + high weird-char ratio (conventional garble)
    3. High Chinese ratio (>30%) but NO financial keywords AND
       high weird-char ratio > 20% (pure CID乱码 without any correct text)
    4. Per-line check: if >50% of non-empty lines have >30% replacement chars,
       the page is mostly garbled even if some headers rendered correctly
    """
    if not text:
        return True

    chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
    total_chars = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

    if total_chars == 0:
        return True

    chinese_ratio = chinese_chars / total_chars

    # Strategy 1: Replacement character ratio
    replacement_char = '�'
    replacement_count = text.count(replacement_char)
    replacement_ratio = replacement_count / total_chars if total_chars > 0 else 0
    if replacement_ratio > 0.3:
        return True

    # Strategy 2: Low Chinese + weird chars (conventional garble)
    if chinese_ratio < 0.1 and total_chars > 50:
        weird_chars = sum(
            1
            for c in text
            if c not in " \n\t中文英文数字0123456789.,()+-/*=：:;{}[]%元万元亿元"
        )
        weird_ratio = weird_chars / total_chars
        if weird_ratio > 0.3:
            return True

    # Strategy 3: High Chinese but no financial keywords + high weird ratio
    non_space = text.replace(" ", "").replace("\n", "").replace("\t", "").replace("\r", "")
    chinese_non_space = sum(1 for c in non_space if "一" <= c <= "鿿")
    chinese_ratio_non_space = chinese_non_space / len(non_space) if non_space else 0

    if chinese_ratio_non_space > 0.3:
        financial_keywords = [
            "资产负债表", "利润表", "现金流量表",
            "资产总计", "负债合计", "所有者权益",
            "营业收入", "营业成本", "净利润",
            "经营活动", "投资活动", "筹资活动",
            "公司名称", "股票代码", "报表日期",
            "合计", "本期", "上期", "期末", "期初",
            "流动资产", "流动负债", "非流动资产",
            "基本每股收益", "稀释每股收益",
        ]
        has_keyword = any(kw in text for kw in financial_keywords)
        if not has_keyword:
            return True
        # Strategy 4: Even if keywords exist, check line-level replacement density
        lines = [l for l in text.split("\n") if l.strip()]
        if lines:
            garbled_lines = sum(
                1 for l in lines
                if l.count(replacement_char) / max(len(l), 1) > 0.3
            )
            if garbled_lines / len(lines) > 0.5:
                return True

    return False
