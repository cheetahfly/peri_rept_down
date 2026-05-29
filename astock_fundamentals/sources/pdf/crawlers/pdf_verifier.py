# -*- coding: utf-8 -*-
"""
PDF文件验证模块

验证下载的PDF是否为真正的财务报表（非公告、摘要等）
"""

import os
import logging

logger = logging.getLogger(__name__)


class PdfVerifier:
    """PDF财务报表验证器"""

    # 按报告类型的最小文件大小（字节）
    MIN_FILE_SIZES = {
        "annual": 500 * 1024,       # 500KB
        "half_year": 300 * 1024,    # 300KB
        "quarter_q1": 100 * 1024,   # 100KB
        "quarter_q3": 150 * 1024,   # 150KB
        "quarter": 100 * 1024,      # 100KB（通用季报）
    }

    # 按报告类型的最小页数
    MIN_PAGE_COUNTS = {
        "annual": 50,
        "half_year": 20,
        "quarter_q1": 10,
        "quarter_q3": 10,
        "quarter": 10,
    }

    # 财务报表正面关键词（至少命中1个）
    REPORT_KEYWORDS = [
        "资产负债表", "利润表", "现金流量表",
        "合并资产负债表", "合并利润表", "合并现金流量表",
        "报告期内", "本报告期", "公司概况",
        "财务报表", "会计数据", "经营成果",
    ]

    # 非报表文档关键词（命中多个则拒绝）
    NON_REPORT_KEYWORDS = [
        "召开股东大会", "征集投票权", "增持", "减持",
        "停复牌", "退市", "风险提示", "澄清",
        "停牌", "复牌", "回购", "质押",
    ]

    def verify(self, pdf_path: str, report_type: str = "annual") -> dict:
        """
        验证PDF是否为有效的财务报表

        Args:
            pdf_path: PDF文件路径
            report_type: 报告类型 (annual/half_year/quarter_q1/quarter_q3)

        Returns:
            {"valid": bool, "reason": str, "confidence": float}
        """
        result = {"valid": True, "reason": "", "confidence": 1.0}

        # 1. 文件存在性
        if not os.path.exists(pdf_path):
            return {"valid": False, "reason": "文件不存在", "confidence": 0.0}

        # 2. 文件大小检查
        file_size = os.path.getsize(pdf_path)
        min_size = self.MIN_FILE_SIZES.get(report_type, 100 * 1024)
        if file_size < min_size:
            return {
                "valid": False,
                "reason": f"文件太小 ({file_size / 1024:.0f}KB < {min_size / 1024:.0f}KB)",
                "confidence": 0.9,
            }

        # 3. 页数和文本关键词检查
        try:
            from astock_fundamentals.sources.pdf.parsers.pdf_parser import PdfParser

            with PdfParser(pdf_path) as parser:
                page_count = parser.page_count
                min_pages = self.MIN_PAGE_COUNTS.get(report_type, 10)

                if page_count < min_pages:
                    return {
                        "valid": False,
                        "reason": f"页数太少 ({page_count} < {min_pages})",
                        "confidence": 0.85,
                    }

                # 采样前3页文本
                sample_text = ""
                for p in range(min(3, page_count)):
                    text = parser.extract_text(p) or ""
                    sample_text += text

                # 检查正面关键词
                positive_hits = sum(1 for kw in self.REPORT_KEYWORDS if kw in sample_text)
                # 检查负面关键词
                negative_hits = sum(1 for kw in self.NON_REPORT_KEYWORDS if kw in sample_text)

                if positive_hits == 0 and negative_hits >= 2:
                    return {
                        "valid": False,
                        "reason": f"非报表文档 (正面关键词: {positive_hits}, 负面关键词: {negative_hits})",
                        "confidence": 0.8,
                    }

                # 乱码检测
                from astock_fundamentals.sources.pdf.parsers.html_converter import is_garbled_text
                if is_garbled_text(sample_text) and positive_hits == 0:
                    return {
                        "valid": False,
                        "reason": "文本乱码且无报表关键词",
                        "confidence": 0.6,
                    }

                # 置信度计算
                result["confidence"] = min(1.0, 0.5 + positive_hits * 0.1 - negative_hits * 0.05)

        except Exception as e:
            logger.warning("PDF验证异常 (%s): %s", pdf_path, e)
            result["confidence"] = 0.5

        return result
