# -*- coding: utf-8 -*-
"""
财务报表明取器基类
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
from datetime import datetime

import pandas as pd

from extraction.parsers.pdf_parser import PdfParser
from extraction.parsers.table_parser import TableParser
from extraction.config import SECTION_KEYWORDS, EXPECTED_ITEMS_PER_TYPE

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """财报提取器基类"""

    # 子类需要定义的属性
    STATEMENT_TYPE = None  # 报表类型标识
    SECTION_KEYWORDS = []  # 关键词列表

    def __init__(self, pdf_parser: PdfParser):
        """
        初始化提取器

        Args:
            pdf_parser: PDF解析器实例
        """
        self.parser = pdf_parser
        self.table_parser = TableParser()

    def extract(self, pdf_path: str = None, discovered_pages: List[int] = None) -> Dict:
        """
        提取财务数据

        Args:
            pdf_path: PDF文件路径（如果使用新的PDF）
            discovered_pages: 预发现的页面列表（用于去重后注入）

        Returns:
            提取的数据字典
        """
        if pdf_path:
            with PdfParser(pdf_path) as parser:
                return self._do_extract(parser, discovered_pages)
        else:
            return self._do_extract(self.parser, discovered_pages)

    def _do_extract(self, parser: PdfParser, discovered_pages: List[int] = None) -> Dict:
        """
        执行提取逻辑

        Args:
            parser: PDF解析器
            discovered_pages: 预发现的页面列表（用于去重后注入）

        Returns:
            提取的数据
        """
        # 查找报表页面（如果外部已发现则直接使用）
        if discovered_pages is not None:
            section_pages = discovered_pages
        else:
            section_pages = self._find_section_pages(parser)

        if not section_pages:
            return {
                "statement_type": self.STATEMENT_TYPE,
                "found": False,
                "data": {},
                "error": "未找到报表页面",
            }

        # 提取报表数据（利润表优先使用文本解析以避免表格结构误判）
        prefer_text = self.STATEMENT_TYPE == "income_statement"
        tables_data = self._extract_tables_from_pages(parser, section_pages, prefer_text_parse=prefer_text)

        # 合并跨页表格
        merged_data = self._merge_tables(tables_data)

        # 单位规范化
        normalized_data = self._normalize_units(merged_data, section_pages)

        result = {
            "statement_type": self.STATEMENT_TYPE,
            "found": True,
            "pages": section_pages,
            "data": normalized_data,
            "extracted_at": datetime.now().isoformat(),
        }

        # NEW: Quality gate — if found but very few items, try auto-recovery
        found_items = len(normalized_data)
        min_items = EXPECTED_ITEMS_PER_TYPE.get(self.STATEMENT_TYPE, 30) // 3

        if found_items < min_items:
            from extraction.semantic_recovery import SemanticRecovery
            import os as _os

            pdf_path = getattr(parser, "pdf_path", None) or getattr(parser, "_pdf_path", None)
            if pdf_path and _os.path.exists(pdf_path):
                import pdfplumber
                total_pages = 0
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        total_pages = len(pdf.pages)
                except Exception:
                    pass

                scan_range = []  # 兜底值，当 total_pages == 0 时使用
                if total_pages > 0:
                    # Build targeted scan range: neighborhood around discovered pages
                    # This avoids being flooded by unrelated high-density pages (e.g. TOC)
                    NEIGHBORHOOD = 15  # pages on each side of discovered page
                    if section_pages:
                        min_p = max(0, min(section_pages) - NEIGHBORHOOD)
                        max_p = min(total_pages - 1, max(section_pages) + NEIGHBORHOOD)
                        scan_range = list(range(min_p, max_p + 1))
                    else:
                        scan_range = list(range(total_pages))

                    # Use new semantic recovery
                    recovery = SemanticRecovery()
                    recovered = recovery.recover_from_html(
                        pdf_path, scan_range, self.STATEMENT_TYPE
                    )
                    if recovered:
                        result["data"] = recovered
                        result["recovered"] = True
                        result["recovery_method"] = "semantic"
                        result["pages"] = scan_range

                # Fallback: word-level recovery (pdfplumber-based, no external deps)
                if len(result["data"]) < min_items:
                    from extraction.word_recovery import recover_statement_auto
                    word_data = recover_statement_auto(
                        pdf_path, self.STATEMENT_TYPE, scan_range, top_n=10
                    )
                    if word_data.get("found"):
                        existing = result["data"]
                        recovered_flat = word_data.get("data", {})
                        merged = dict(existing)
                        for k, v in recovered_flat.items():
                            if k not in merged and isinstance(v, (int, float)) and abs(v) >= 1000:
                                merged[k] = v
                        if len(merged) > len(existing):
                            result["data"] = merged
                            result["recovered"] = True
                            result["recovery_method"] = "word_recovery"
                            result["word_recovery_stats"] = word_data.get("stats", {})

        return result

    def _find_section_pages(self, parser: PdfParser) -> List[int]:
        """
        查找报表所在页面（智能定位，排除目录等）

        Args:
            parser: PDF解析器

        Returns:
            页面列表
        """
        keywords = self.SECTION_KEYWORDS or SECTION_KEYWORDS.get(
            self.STATEMENT_TYPE, []
        )
        candidate_pages = parser.find_pages(keywords)

        if not candidate_pages:
            return []

        # 页面距离约束：仅包含第一个候选页附近有限范围的页面
        # 排除距首候选页过远的页面（通常是附注页被误匹配）
        first_page = candidate_pages[0]
        MAX_SPREAD = 8

        # 对于CID字体PDF，find_pages可能在早期页面误匹配关键词（如管理层分析表格含"利润表"）
        # 优先用含有严格section header（独立标题行，而非嵌入在段落中）的候选页作为锚点
        # 注意：不能使用_text_has_section_header（含宽松fallback），需用纯行首匹配
        # layout=True会在文本前后填充空格，因此需\s*处理行首行尾空白
        section_prefix = r'(?:\d+[\.、]?\s*)?'
        anchor_kws = SECTION_KEYWORDS.get(self.STATEMENT_TYPE, [])
        for p in candidate_pages:
            text = parser.extract_text(p)
            if not text:
                continue
            if any(re.search(rf'^\s*{section_prefix}{re.escape(kw)}\s*$', text, re.MULTILINE)
                   for kw in anchor_kws):
                first_page = p
                break

        filtered_pages = [p for p in candidate_pages if abs(p - first_page) <= MAX_SPREAD]
        if filtered_pages:
            candidate_pages = filtered_pages

        real_pages = []
        for page_num in candidate_pages:
            # 提取页面文本进行附注页检测
            page_text = parser.extract_text(page_num)

            # 排除附注页：页面包含"财务报表附注"等字幕
            if self._is_appendix_page(page_text):
                continue

            # 优先检查页面是否包含明确的section header（如"合并利润表"）
            # 某些CID字体PDF无法提取表格，但文本中包含表头关键词
            if self._text_has_section_header(page_text):
                real_pages.append(page_num)
                continue

            # 预检查：页面是否包含报表科目关键词——跳过明显不相关的页面
            # （如find_pages误匹配到"利润表"的附注页、TOC页等）
            # 这避免了在这些无关页面上调用极慢的pdfplumber extract_tables()（单页可达100s+）
            has_stmt_keywords = (
                self.STATEMENT_ITEMS
                and any(kw in page_text for kw in self.STATEMENT_ITEMS[:5])
            )
            if not has_stmt_keywords:
                # CID字体PDF回退：关键词可能因乱码而无法匹配，
                # 此时用中文比例+最长连续串长度判断是否为乱码数据页
                if self._is_text_cid_garbled(page_text):
                    # 乱码页面仍有可能是报表页（关键词被替换），允许继续
                    pass
                else:
                    # 既无关键词、又非CID乱码 → 不相关页，跳过
                    continue

            tables = parser.extract_tables(page_num, min_rows=5, min_cols=2)

            if not tables:
                text_tables = parser.extract_text_tables(page_num)
                if text_tables:
                    for table in text_tables:
                        if self._is_valid_table(table):
                            real_pages.append(page_num)
                            break
                # 如果本节表未能提取到表格，也检查是否包含报表科目关键词
                # （CID字体PDF的表格可能完全无法被pdfplumber解析）
                if page_num not in real_pages:
                    if self._text_has_section_header(page_text):
                        real_pages.append(page_num)
                    elif self.STATEMENT_ITEMS:
                        # 最后兜底：检查页面是否包含报表科目关键词
                        has_stmt_keywords = any(kw in page_text for kw in self.STATEMENT_ITEMS[:5])
                        if has_stmt_keywords and len(page_text) > 500:
                            real_pages.append(page_num)
            else:
                for table in tables:
                    if self._is_valid_table(table):
                        real_pages.append(page_num)
                        break

        # 第二轮：对现金流量表和资产负债表，额外扫描未在candidate_pages中的页面
        # 这些页可能是延续页（如BS负债页、CF筹资活动跨页）但未被find_pages找到
        if self.STATEMENT_TYPE == "cash_flow":
            extra_pages = self._find_cf_continuation_pages(parser)
            for p in extra_pages:
                if p not in real_pages and abs(p - first_page) <= MAX_SPREAD:
                    # 对延续页也要做附注页检查，避免IS页（含有BS关键词的）被加入BS
                    text = parser.extract_text(p)
                    if text and not self._is_appendix_page(text):
                        real_pages.append(p)
            real_pages.sort()
        elif self.STATEMENT_TYPE == "balance_sheet":
            extra_pages = self._find_bs_continuation_pages(parser)
            for p in extra_pages:
                if p not in real_pages and abs(p - first_page) <= MAX_SPREAD:
                    # 对延续页也要做附注页检查
                    text = parser.extract_text(p)
                    if text and not self._is_appendix_page(text):
                        real_pages.append(p)
            real_pages.sort()
        elif self.STATEMENT_TYPE == "income_statement":
            extra_pages = self._find_is_continuation_pages(parser)
            for p in extra_pages:
                if p not in real_pages and abs(p - first_page) <= MAX_SPREAD:
                    text = parser.extract_text(p)
                    if text and not self._is_appendix_page(text):
                        real_pages.append(p)
            real_pages.sort()

        # 补充填写：对已确认的连续页面之间的空隙进行填充
        # CID字体PDF中部分页面无法通过关键词匹配或表格验证，但实际报表页面是连续的
        # 例如pages=[55, 57, 58, 59] -> gap_fill 56
        filled_pages = set(real_pages)
        for i in range(len(real_pages) - 1):
            start = real_pages[i]
            end = real_pages[i + 1]
            if end - start > 1:
                for p in range(start + 1, end):
                    if p not in filled_pages:
                        text = parser.extract_text(p)
                        if text and not self._is_appendix_page(text):
                            filled_pages.add(p)
        real_pages = sorted(filled_pages)

        # 去重：当同一个报表类型匹配到多个章节（如BS的"一、合并资产负债表"和"二、母公司资产负债表"，
        # 或IS的"三、合并利润表"和"四、母公司利润表"），只保留第一个章节（通常是合并报表）
        # 基于section header页面是否连续来判断：同章节的header页连续，不同章节间有间隔
        if len(real_pages) > 1:
            header_pages = []
            for p in real_pages:
                text = parser.extract_text(p)
                if text and self._text_has_section_header(text):
                    header_pages.append(p)
            if len(header_pages) > 1:
                # 文本层面检测到多个section header（适用于非CID字体PDF）
                non_consecutive = False
                for i in range(len(header_pages) - 1):
                    if header_pages[i + 1] - header_pages[i] > 1:
                        non_consecutive = True
                        first_section_end = header_pages[i + 1] - 1
                        real_pages = [p for p in real_pages if p <= first_section_end]
                        logger.info("Multiple sections for %s, keeping first section: pages %s",
                                    self.STATEMENT_TYPE, real_pages)
                        break
                if not non_consecutive:
                    logger.debug("All header pages consecutive for %s, treating as single section: %s",
                                 self.STATEMENT_TYPE, real_pages)
            elif len(header_pages) == 0:
                # CID字体PDF兜底：文字乱码导致_text_has_section_header无法匹配，
                # 此时如果页面不连续，说明有多个报表章节，只保留第一个连续块
                first_block = [real_pages[0]]
                for p in real_pages[1:]:
                    if p == first_block[-1] + 1:
                        first_block.append(p)
                    else:
                        break
                if len(first_block) < len(real_pages):
                    logger.info("CID fallback: multiple sections via gap, keeping first block: %s", first_block)
                    real_pages = first_block

        return real_pages

    # 子类需要定义的科目关键词（用于过滤）
    STATEMENT_ITEMS = []

    def _find_cf_continuation_pages(self, parser: 'PdfParser') -> List[int]:
        """
        扫描可能包含现金流量表章节但未被find_pages找到的页面

        Args:
            parser: PDF解析器

        Returns:
            额外发现的页码列表
        """
        extra = []

        # 方法1：关键词搜索（适用于非CID字体PDF）
        section_pattern = re.compile(
            r'[一二三四五六七八]、.{0,15}(经营|投资|筹资)活动.{0,30}(现金|流量|净额)'
        )

        for page_num in range(parser.page_count):
            text = parser.extract_text(page_num)
            if section_pattern.search(text):
                # 进一步验证：页面应该包含数字（财务数据）
                if re.search(r'\d{3,}', text):
                    extra.append(page_num)

        # 方法2：CID字体PDF回退——关键词搜索找到的页面太少时，
        # 使用数值密度法：查找包含大量"中文+6位以上数字"数据行的页面
        # 财务数据行特征：一行中同时出现中文字符和大数字
        if len(extra) < 3:
            cid_extra = []
            for page_num in range(parser.page_count):
                text = parser.extract_text(page_num)
                if not text:
                    continue
                lines = text.split('\n')
                data_lines = sum(
                    1 for l in lines
                    if any('一' <= c <= '鿿' for c in l)
                    and re.search(r'[\d,]{6,}', l)
                )
                if data_lines >= 15:
                    cid_extra.append(page_num)
            # 去重合并
            for p in cid_extra:
                if p not in extra:
                    extra.append(p)

        return extra

    def _find_bs_continuation_pages(self, parser: 'PdfParser') -> List[int]:
        """
        扫描可能包含资产负债表负债/权益章节但未被find_pages找到的页面

        Args:
            parser: PDF解析器

        Returns:
            额外发现的页码列表
        """
        extra = []

        # 逐行处理避免 layout=True 空格的 catastrophic backtracking
        kw_pattern = re.compile(
            r'(负债合计|非流动负债合计|流动负债合计|'
            r'所有者权益.*?合计|股东权益.*?合计|'
            r'归属于母公司.*?权益.*?合计|'
            r'负债和所有者权益.*?总计|'
            r'负债和股东权益.*?总计)'
        )

        for page_num in range(parser.page_count):
            text = parser.extract_text(page_num)
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if re.search(r'[\d,]{6,}', line) and kw_pattern.search(line):
                    extra.append(page_num)
                    break

        return extra

    def _find_is_continuation_pages(self, parser: 'PdfParser') -> List[int]:
        """
        扫描可能包含利润表延续行但未被find_pages找到的页面

        Args:
            parser: PDF解析器

        Returns:
            额外发现的页码列表
        """
        extra = []

        # 逐行处理避免 layout=True 空格的 catastrophic backtracking
        kw_pattern = re.compile(
            r'(?:减|加|其(?:中|他))?\s*'
            r'(营业收入|营业成本|营业利润|利润总额|净利润|'
            r'综合收益总额|所得税费用|利息净收入|已赚保费|'
            r'保险业务收入|投资收益|公允价值变动)'
        )

        for page_num in range(parser.page_count):
            text = parser.extract_text(page_num)
            if not text:
                continue
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if re.search(r'\d{4,}', line) and kw_pattern.search(line):
                    extra.append(page_num)
                    break

        return extra

    def _text_has_section_header(self, text: str) -> bool:
        """
        检查页面文本是否包含报表类型的section header

        Args:
            text: 页面文本

        Returns:
            是否包含section header
        """
        if not text:
            return False

        # 针对不同报表类型使用严格的header模式匹配
        if self.STATEMENT_TYPE == "income_statement":
            # 利润表必须是"合并利润表"或"银行利润表"作为独立标题行（后面跟年度/金额/附注等）
            # 排除：目录页"XX利润表 11-12"、章节标题"XX利润表项目分析"等
            # 使用行首匹配+后缀验证，避免误判

            # 匹配"三、合并利润表"、"3、合并利润表" 或 "合并利润表" 位于行首（含母公司变体）
            # layout=True会在文本前添加空格，因此用\s*处理行首空白
            section_prefix = r'(?:\d+[\.、]?\s*)?'
            valid_headers = [
                rf'^\s*{section_prefix}(合并利润表|母公司利润表|银行利润表|利润表)\s*$',
            ]
            for p in valid_headers:
                if re.search(p, text, re.MULTILINE):
                    return True

            # 匹配"合并利润表"后跟内容但不是纯页码
            if re.search(r'^\s*(合并利润表|银行利润表)\s+(?![\d\-]+\s*$)', text, re.MULTILINE):
                return True

            # 如果"利润表"出现在行首但匹配失败，说明可能是"XX利润表 11-12"这样的目录项
            if re.search(r'^\s*.*合并利润表|^\s*.*银行利润表', text, re.MULTILINE):
                # 检查是否是"XX利润表 11-12"或"XX利润表 13"这样的页码引用
                if re.search(r'(合并|银行)利润表\s+[\d\-]+\s*$', text, re.MULTILINE):
                    return False  # 目录项，不算
                # 可能是"XX利润表"后跟其他内容（如"XX利润表补充"）
                if re.search(r'(合并|银行)利润表\s+[^\d]', text, re.MULTILINE):
                    return True

            # 排除"XX利润表项目"、"XX利润表中"等干扰（中间无空格的短语）
            if re.search(r'(合并|银行)利润表项目|(合并|银行)利润表中|利润表项目分析', text):
                return False

            # 检查"利润表"关键词后是否有列标题特征
            if '利润表' in text:
                # CID字体PDF中，"利润表"可能出现在附注引用中（如"详见合并利润表附注"）或
                # "财务报表"乱码产生的"利润表"字符（如公司治理段落中的引用）而非表头
                # 真正的利润表表头始终在页面前部出现（前1/3行数以内），
                # 而附注引用在页面中后部
                lines = text.split('\n')
                header_zone = max(5, len(lines) // 3)
                # 额外检查："利润表"必须位于行首附近（前20个非空白字符内）
                # 段落中间的"利润表"（如"相关财务报表附注"中的乱码匹配）不是标题
                has_line_start_header = False
                for l in lines[:header_zone]:
                    if '利润表' in l:
                        stripped = l.lstrip()
                        if stripped.find('利润表') <= 20:
                            has_line_start_header = True
                            break
                if has_line_start_header:
                    # 验证页面确实包含财务数据行（中文+5位以上数字），
                    # 排除仅有"利润表"关键词但无实际数据的页（如公司治理段中的乱码匹配）
                    data_lines = sum(
                        1 for l in lines
                        if any('一' <= c <= '鿿' for c in l)
                        and re.search(r'[\d,]{5,}', l)
                    )
                    if data_lines >= 5:
                        # 真正的标题应该有"金额"或"本期"或"上期"等列标题
                        if re.search(r'本期|上期|金额|年度|发生额', text):
                            return True

        elif self.STATEMENT_TYPE == "balance_sheet":
            # 资产负债表（可选章节编号前缀），含合并/母公司/银行变体
            # layout=True会在文本前添加空格，因此用\s*处理行首空白
            section_prefix = r'(?:\d+[\.、]?\s*)?'
            for kw in ['合并资产负债表', '母公司资产负债表', '银行资产负债表', '资产负债表']:
                if re.search(rf'^\s*{section_prefix}{re.escape(kw)}\s*$', text, re.MULTILINE):
                    return True
            # 如果"资产负债表"在行首后跟数字（非延续页的简单表格），也算
            if re.search(r'^\s*资产负债表\s+[\d,]', text, re.MULTILINE):
                return True

        elif self.STATEMENT_TYPE == "cash_flow":
            # 现金流量表（可选章节编号前缀），含(续)后缀
            section_prefix = r'(?:\d+[\.、]?\s*)?'
            for kw in ['合并现金流量表', '母公司现金流量表', '银行现金流量表', '现金流量表']:
                if re.search(rf'^\s*{section_prefix}{re.escape(kw)}(?:\(续\))?\s*$', text, re.MULTILINE):
                    return True
            # 同时检查 CF 章节：数字+顿号开头，后面跟经营活动/投资活动/筹资活动
            section_pattern = r'[一二三四五六七八九十]、.{0,15}(经营|投资|筹资)活动.{0,30}(现金|流量|净额)'
            if re.search(section_pattern, text):
                return True

        else:
            # 默认逻辑：关键词在行首或紧随公司名后
            section_keywords = self.SECTION_KEYWORDS or SECTION_KEYWORDS.get(
                self.STATEMENT_TYPE, []
            )
            for kw in section_keywords:
                if re.search(rf'^\s*{re.escape(kw)}\s*$', text, re.MULTILINE):
                    return True
                # 检查关键词+数字上下文
                idx = text.find(kw)
                if idx >= 0:
                    start = max(0, idx - 20)
                    end = min(len(text), idx + len(kw) + 20)
                    context = text[start:end]
                    if re.search(r'[\d,.%（）()]', context):
                        return True

        return False

    def _is_appendix_page(self, text: str) -> bool:
        """
        检测页面是否为附注页（附录页）

        附注页的特征：
        - 页面任意位置包含"财务报表附注"（完整标题）
        - 页面包含"附注"章节标题 + 科目编号（如"五、附注"或"四、财务报表附注"）
        - 包含会计政策说明语句（如"于资产负债表日"、"以公允价值计量"等）

        注意：不能仅因为表格中包含"附注"列标题就判定为附注页

        Args:
            text: 页面文本

        Returns:
            是否为附注页
        """
        if not text:
            return False

        # 如果页面包含明确的报表标题（如"合并资产负债表"等），不是附注页
        # 银行PDF的BS表有"附注"列，底部也有"财务报表附注"抬头，需优先排除
        if self._text_has_section_header(text):
            return False

        # 同时检查延续页标题（如"合并资产负债表(续)"），同样不是附注页
        section_prefix = r'(?:\d+[\.、]?\s*)?'
        cont_kws = SECTION_KEYWORDS.get(self.STATEMENT_TYPE, [])
        if any(re.search(rf'^\s*{section_prefix}{re.escape(kw)}\(续\)\s*$', text, re.MULTILINE)
               for kw in cont_kws):
            return False

        # 整页扫描是否存在"财务报表附注"（notes页面的明确标志）
        if '财务报表附注' in text:
            # 排除"后附财务报表附注为财务报表的组成部分"（报表页标准脚注，非附注页）
            # 真正的附注页至少会有2处"财务报表附注"（如标题+章节号或正文引用）
            if '后附财务报表附注为财务报表的组成部分' in text:
                if text.count('财务报表附注') <= 1:
                    return False
            return True

        # 检查页面开头区域（前2000字符）是否包含附注特征
        header_area = text[:2000]

        # 包含章节编号+附注关键词（如"四、财务报表附注"、"五、附注"）
        lines = header_area.split('\n')
        for i, line in enumerate(lines[:25]):
            line = line.strip()
            if not line:
                continue
            # 匹配形如 "四、财务报表附注" 或 "五、附注" 的中文章节标题
            if re.match(r'[一二三四五六七八九十]+、', line) and '附注' in line:
                return True
            # 匹配形如 "1. 公司基本情况"、"2. 财务报表编制基础" 等编号科目
            # 这些是附注页开头部分的典型特征
            if re.match(r'\d+\.\s+', line) and i < 8:
                # 包含常见的附注章节名
                if any(kw in line for kw in ['公司基本情况', '财务报表编制', '重要会计政策',
                                               '会计估计', '税项', '合并范围', '分部报告']):
                    return True

        # 检查全文是否包含"会计政策"说明或附注编号（如"附注三"、"附注四"）
        # 这是notes页面的辅助判断（避免误判主表页面上因表格包含"附注"列而被排除）
        note_section_refs = ['附注三', '附注四', '附注五', '附注六', '附注七',
                              '附注八', '附注九', '附注十', '附注十一', '附注十二']
        if any(ref in header_area for ref in note_section_refs):
            return True

        # 会计政策说明语句（notes页的典型内容特征）
        # 这些短语在BS/IS/CF主表页面上几乎不会出现
        # 但如果页面已经包含明确的报表标题（如"合并利润表"），则不应判定为附注页
        if not self._text_has_section_header(text):
            accounting_policy_indicators = [
                '于资产负债表日', '以公允价值计量', '采用公允价值',
                '外币业务', '外币报表折算', '股份支付', '企业合并',
                '会计政策', '会计估计', '前期差错',
            ]
            # 移除易误判的短语（如"职工薪酬"会匹配科目"应付职工薪酬"、"所得税"会匹配"递延所得税负债"）
            # 同时要求短语出现在句子语境中（周围30字符内有中文字，无大数字），而非表格行内
            policy_hits = 0
            for phrase in accounting_policy_indicators:
                if phrase not in text:
                    continue
                idx = text.find(phrase)
                start = max(0, idx - 30)
                end = min(len(text), idx + len(phrase) + 30)
                context = text[start:end]
                # 表格行特征：短语附近有大数字（4位以上），判断为科目名而非政策说明
                if re.search(r'\d{4,}', context):
                    continue
                # 进一步确认：短语附近有中文字（排除页眉/页脚等孤立匹配）
                if re.search(r'[一-鿿]', context[max(0, idx-start-5):idx-start+5]):
                    policy_hits += 1
            if policy_hits >= 2:
                return True

        return False

    @staticmethod
    def _is_text_cid_garbled(text: str) -> bool:
        """
        检测文本是否因CID字体导致乱码

        CID字体PDF中，pdfplumber提取的文本因字体编码映射错误导致中文字符被替换为
        其他Unicode字符。判断依据：
        1. 中文比例偏低（<30%，正常中文文本>40%）
        2. 最长连续中文字符串长度<4（正常页面有"营业收入"等4+字科目名，CID乱码
           则中文字符被孤立成1-2个字符，如"营^%X收p"）

        Args:
            text: 页面文本

        Returns:
            是否疑似CID字体乱码
        """
        if not text or len(text) < 200:
            return False

        chinese_chars = 0
        max_run = 0
        current_run = 0

        for c in text:
            if '一' <= c <= '鿿':
                chinese_chars += 1
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0

        if chinese_chars == 0:
            return True

        ratio = chinese_chars / len(text)
        # CID乱码：低中文比例 + 无长中文连续串（正常页面必有4+字科目名）
        return ratio < 0.3 and max_run < 4

    def _extract_tables_from_pages(
        self, parser: PdfParser, pages: List[int], prefer_text_parse: bool = False
    ) -> List[Tuple[int, pd.DataFrame]]:
        """
        从页面提取表格（支持跨页表格合并）

        Args:
            parser: PDF解析器
            pages: 页面列表
            prefer_text_parse: 是否优先使用文本解析

        Returns:
            [(页码, 表格DataFrame)] 列表
        """
        result = []
        prev_table = None
        prev_columns = None

        for page_num in pages:
            tables, continuation_table, continuation_columns = (
                parser.extract_tables_with_continuation(
                    page_num, prev_table, prev_columns, prefer_text_parse=prefer_text_parse
                )
            )

            if not tables:
                tables = parser.extract_text_tables(page_num)
                for table in tables:
                    if table is not None and not table.empty:
                        table = table.dropna(how="all")
                        if not table.empty:
                            if self._is_valid_table(table):
                                result.append((page_num, table))
                                prev_table = table
                                prev_columns = (
                                    list(table.columns)
                                    if table.columns is not None
                                    else None
                                )
                continue

            for table in tables:
                if table is not None and not table.empty:
                    table = table.dropna(how="all")
                    if not table.empty:
                        if self._is_valid_table(table):
                            result.append((page_num, table))

            if continuation_table is not None and not continuation_table.empty:
                prev_table = continuation_table
                prev_columns = continuation_columns
            else:
                prev_table = tables[-1] if tables else None
                prev_columns = (
                    list(tables[-1].columns)
                    if tables and tables[-1].columns is not None
                    else None
                )

        # 如果表格提取失败（0个有效表格），尝试从页面文本直接提取（CID字体PDF回退）
        if not result and pages:
            text_items = self._extract_items_from_text(parser, pages)
            if text_items:
                # 将文本提取的科目构建为DataFrame，复用下游合并逻辑
                text_df = pd.DataFrame([
                    {'item': k, 'value': str(v)} for k, v in text_items.items()
                ])
                if not text_df.empty:
                    result.append((pages[0], text_df))

        return result

    def _extract_items_from_text(self, parser: PdfParser, pages: List[int]) -> Dict[str, float]:
        """
        从页面文本直接提取科目数据（文本回退方案，用于CID字体PDF）

        pdfplumber对CID字体PDF的表格提取可能丢失列结构（如缺少科目名称列），
        但文本提取（layout=True）通常能正确保留科目名和数值。
        此方法在表格提取失败时作为回退使用。

        Args:
            parser: PDF解析器
            pages: 页面列表

        Returns:
            {科目名: 数值} 字典
        """
        items = {}
        seen = set()

        # 过滤：值太小的（可能是年份/页码，不是财务数据）
        VALUE_MIN = 50000
        # 无效科目名（表头行、说明文字等）
        INVALID_NAMES = [
            '单位', '项目', '附注', '期末', '期初', '年初', '年末',
            '报表日期', '货币单位', '人民币',
            '公允反映', '按照规定', '会计报表',
        ]

        for p in pages:
            text = parser.extract_text(p)
            if not text:
                continue

            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue

                # 检查行中是否包含中文文本
                if not any('一' <= c <= '鿿' for c in line):
                    continue

                # 检查行中是否包含大数值（至少4位连续数字）
                nums = re.findall(r'[\d,]+\.?\d*', line)

                # 过滤有效的财务数值（去逗号后 >= 1千且 <= 1000万亿）
                valid_nums = []
                for n_str in nums:
                    try:
                        v = float(n_str.replace(',', ''))
                        if abs(v) >= 1000 and abs(v) <= 1e15:
                            valid_nums.append(v)
                    except ValueError:
                        continue

                if not valid_nums:
                    continue

                # 取行中第一个有效数值
                first_val = valid_nums[0]

                # 找到对应数值在行中的位置
                first_num_str = None
                for n_str in nums:
                    try:
                        v = float(n_str.replace(',', ''))
                        if v == first_val:
                            first_num_str = n_str
                            break
                    except ValueError:
                        continue

                if not first_num_str:
                    continue

                # 数值前的文本作为科目名称
                idx = line.find(first_num_str)
                if idx < 0:
                    continue

                item_name = line[:idx].strip()
                # 去掉章节编号（如"十八、"）
                item_name = re.sub(r'^[一二三四五六七八九十]+、', '', item_name).strip()
                # 去掉多余空格
                item_name = re.sub(r'\s+', ' ', item_name).strip()

                if not item_name or len(item_name) < 2 or len(item_name) > 50:
                    continue

                if not any('一' <= c <= '鿿' for c in item_name):
                    continue

                if item_name in seen:
                    continue

                items[item_name] = first_val
                seen.add(item_name)

        return items

    def _is_valid_table(self, table: pd.DataFrame) -> bool:
        """
        验证表格是否是目标报表的有效表格

        Args:
            table: 表格DataFrame

        Returns:
            是否有效
        """
        if table.empty:
            return False

        if table.shape[0] < 5 or table.shape[1] < 2:
            return False

        first_col_values = [str(v) for v in table.iloc[:, 0].values if pd.notna(v)]
        if not first_col_values:
            return False

        first_col_text = " ".join(first_col_values)
        if len(first_col_text) < 10:
            return False

        check_rows = max(3, table.shape[0] // 2)
        invalid_count = 0
        invalid_starts = ["章节", "第", "节", "页", "目", "录", "注", "释", "附"]

        for val in first_col_values[:check_rows]:
            for invalid in invalid_starts:
                if val.startswith(invalid):
                    invalid_count += 1
                    break

        if invalid_count >= check_rows * 0.5:
            return False

        table_text = " ".join([str(v) for v in table.values.flatten() if pd.notna(v)])

        if self.STATEMENT_ITEMS:
            has_relevant_item = any(kw in table_text for kw in self.STATEMENT_ITEMS)
            if not has_relevant_item:
                return False

        # 检测是否是分析页/百分比页（包含"占比"列的是分析表格，排除）
        table_text = " ".join([str(v) for v in table.values.flatten() if pd.notna(v)])
        has_percentage_col = "占比" in table_text and table.shape[1] >= 4
        if has_percentage_col:
            return False

        if self.STATEMENT_TYPE == "balance_sheet":
            if "资产" not in table_text and "负债" not in table_text:
                return False
            if "%" in table_text and len(table.columns) <= 4:
                return False

        elif self.STATEMENT_TYPE == "income_statement":
            # 排除分析页（含百分比列的"收入构成"等分析表格）
            if "占比" in table_text and table.shape[1] >= 4:
                return False
            if "收入" not in table_text and "利润" not in table_text:
                return False

        elif self.STATEMENT_TYPE == "cash_flow":
            keywords = ["现金", "流量", "经营", "投资", "筹资"]
            if not any(kw in table_text for kw in keywords):
                return False

        has_numeric = False
        for col in table.columns[1:]:
            for val in table[col].values:
                try:
                    if pd.notna(val).any() if hasattr(val, "any") else pd.notna(val):
                        val_str = str(val)
                        if re.match(
                            r"^-?[\d,，.]+$", val_str.replace(",", "").replace("，", "")
                        ):
                            has_numeric = True
                            break
                except (ValueError, TypeError):
                    continue
            if has_numeric:
                break

        if not has_numeric:
            return False

        return True

    def _merge_tables(self, tables: List[Tuple[int, pd.DataFrame]]) -> Dict[str, float]:
        """
        合并表格数据

        Args:
            tables: [(页码, 表格)] 列表

        Returns:
            {科目: 数值} 字典
        """
        all_items = {}
        seen_keys = set()

        for page_num, table in tables:
            try:
                items = TableParser.extract_items(table)
                for key, value in items.items():
                    clean_key = TableParser.clean_text(key)

                    if clean_key in seen_keys:
                        continue

                    if not TableParser._is_valid_item_name(clean_key):
                        continue

                    all_items[clean_key] = value
                    seen_keys.add(clean_key)
            except Exception as e:
                logger.debug(f"合并表格时跳过页{page_num}: {e}")
                continue

        return all_items

    def _normalize_units(self, data: Dict[str, float], section_pages: List[int] = None) -> Dict[str, float]:
        """
        单位规范化（转换为元）

        Args:
            data: 原始数据字典
            section_pages: 报表页面列表（用于单位检测）

        Returns:
            规范化后的数据
        """
        # 检测单位
        unit, multiplier = self._detect_unit(section_pages)

        if multiplier == 1:
            return data

        # 转换数值
        normalized = {}
        for key, value in data.items():
            normalized[key] = round(value * multiplier, 2)

        return normalized

    def _detect_unit(self, section_pages: List[int] = None) -> Tuple[str, float]:
        """
        检测PDF中的单位（结合文档声明和数值特征）

        Args:
            section_pages: 报表页面列表（优先使用这些页面检测单位）

        Returns:
            (单位名称, 乘数)
        """
        unit, multiplier = self.parser.detect_unit()

        if multiplier != 1:
            return unit, multiplier

        # 使用报表页面检测单位（更准确）
        pages_to_scan = section_pages if section_pages else []
        if not pages_to_scan:
            # 如果没有指定页面，扫描整个文档
            pages_to_scan = range(self.parser.page_count)

        for page_num in pages_to_scan:
            tables = self.parser.extract_tables(page_num, min_rows=5)

            for table in tables:
                values = []
                for col in table.columns[1:]:
                    for val in table[col]:
                        if pd.notna(val):
                            parsed = TableParser.parse_number(str(val))
                            if parsed is not None and abs(parsed) > 1000:
                                values.append(abs(parsed))

                if len(values) >= 5:
                    median_val = sorted(values)[len(values) // 2]

                    if median_val < 10000 and median_val > 1:
                        return ("万元", 10000)
                    elif median_val < 100 and median_val > 0.1:
                        return ("亿元", 100000000)

        return unit, multiplier

    def _clean_item_name(self, name: str) -> str:
        """
        清理科目名称

        Args:
            name: 原始名称

        Returns:
            清理后的名称
        """
        if not isinstance(name, str):
            name = str(name)

        # 移除多余空格
        name = re.sub(r"\s+", "", name)

        # 移除括号内容（附注等）
        name = re.sub(r"[（(].*?[)）]", "", name)

        return name.strip()

    @abstractmethod
    def validate(self, data: Dict) -> Tuple[bool, str]:
        """
        验证提取数据的正确性

        Args:
            data: 提取的数据

        Returns:
            (是否有效, 错误信息)
        """
        pass

    def get_summary(self, data: Dict) -> Dict:
        """
        获取数据摘要

        Args:
            data: 提取的数据

        Returns:
            摘要信息
        """
        if not data or not data.get("found"):
            return {"status": "not_found"}

        items = data.get("data", {})
        return {
            "statement_type": self.STATEMENT_TYPE,
            "item_count": len(items),
            "has_total": any("合计" in k or "总计" in k for k in items.keys()),
            "pages": data.get("pages", []),
        }

    def calculate_confidence(self, data: Dict) -> Dict[str, float]:
        """
        计算提取结果的置信度评分

        Args:
            data: 提取的数据

        Returns:
            置信度评分字典
        """
        if not data or not data.get("found"):
            return {
                "overall": 0.0,
                "completeness": 0.0,
                "consistency": 0.0,
                "balance_check": 0.0,
            }

        items = data.get("data", {})

        completeness = self._calculate_completeness(items)

        is_valid, error_msg = self.validate(data)
        consistency = 1.0 if is_valid else 0.0

        balance_check = self._check_data_balance(items)

        overall = (completeness * 0.4) + (consistency * 0.3) + (balance_check * 0.3)

        return {
            "overall": round(overall, 3),
            "completeness": round(completeness, 3),
            "consistency": round(consistency, 3),
            "balance_check": round(balance_check, 3),
        }

    def _check_data_balance(self, items: Dict[str, float]) -> float:
        """
        检查数据平衡性

        Args:
            items: 科目数据

        Returns:
            平衡性评分 (0-1)
        """
        if self.STATEMENT_TYPE == "balance_sheet":
            assets = self._find_total_by_pattern(items, "assets_total")
            liabilities = self._find_total_by_pattern(items, "liabilities_total")
            equity = self._find_total_by_pattern(items, "equity_total")

            if assets and liabilities and equity:
                total = liabilities + equity
                diff = abs(assets - total)
                tolerance = abs(assets * 0.01)
                if diff <= tolerance:
                    return 1.0
                elif diff <= abs(assets * 0.05):
                    return 0.5
                else:
                    return 0.0

        elif self.STATEMENT_TYPE == "cash_flow":
            operating = self._find_cash_flow_total(items, "operating")
            investing = self._find_cash_flow_total(items, "investing")
            financing = self._find_cash_flow_total(items, "financing")
            net_increase = self._find_cash_flow_total(items, "net_increase")

            if (
                operating is not None
                and investing is not None
                and financing is not None
            ):
                calculated_net = operating + investing + financing
                if net_increase is not None:
                    diff = abs(calculated_net - net_increase)
                    tolerance = (
                        abs(net_increase * 0.1)
                        if net_increase != 0
                        else abs(calculated_net * 0.1)
                    )
                    if diff <= tolerance:
                        return 1.0
                    elif diff <= abs(calculated_net * 0.2):
                        return 0.5
                    else:
                        return 0.0
            return 0.5

        elif self.STATEMENT_TYPE == "income_statement":
            return self._check_income_statement_balance(items)

        return 0.5

    def _check_income_statement_balance(self, items: Dict[str, float]) -> float:
        """检查利润表平衡性"""
        net_profit = None
        total_profit = None
        income_tax = None
        operating_profit = None
        revenue = None
        expenses = None

        for key, value in items.items():
            if net_profit is None and "净利润" in key:
                net_profit = value
            if total_profit is None and "利润总额" in key:
                total_profit = value
            if income_tax is None and "所得税" in key and "费用" in key:
                income_tax = value
            if operating_profit is None and "营业利润" in key:
                operating_profit = value
            if revenue is None and "营业收入" in key:
                revenue = value
            if expenses is None and ("营业支出" in key or "业务及管理费" in key):
                expenses = value

        if (
            net_profit is not None
            and total_profit is not None
            and income_tax is not None
        ):
            # 所得税费用在财报中通常为负数（费用），所以用加法
            expected_net = total_profit + income_tax
            if abs(expected_net) > 0:
                ratio = abs(net_profit) / abs(expected_net)
                if 0.8 <= ratio <= 1.2:
                    return 1.0
                elif 0.5 <= ratio <= 2.0:
                    return 0.5

        if (
            operating_profit is not None
            and revenue is not None
            and expenses is not None
        ):
            # 费用（如业务及管理费）通常为负数，所以用减法
            expected = revenue - abs(expenses) if expenses < 0 else revenue + expenses
            if abs(expected) > 0:
                ratio = abs(operating_profit) / abs(expected)
                if 0.8 <= ratio <= 1.2:
                    return 1.0
                elif 0.5 <= ratio <= 2.0:
                    return 0.5

        if net_profit is not None and revenue is not None and revenue > 0:
            profit_margin = abs(net_profit) / revenue
            if 0 <= profit_margin <= 1:
                return 1.0

        # 当"净利润"因表格解析问题未提取到时，用营业利润作为替代
        if operating_profit is not None and revenue is not None and revenue > 0:
            profit_margin = abs(operating_profit) / revenue
            if 0 <= profit_margin <= 1:
                return 0.8

        # 用利润总额作为进一步替代
        if total_profit is not None and revenue is not None and revenue > 0:
            profit_margin = abs(total_profit) / revenue
            if 0 <= profit_margin <= 1:
                return 0.8

        return 0.5

    def _find_cash_flow_total(self, items: Dict[str, float], flow_type: str) -> float:
        """查找现金流量表各类合计"""
        patterns = {
            "operating": [
                r"经营活动产生",
                r"经营活动.*净额",
                r"经营活动(产生)/使用.*净额",
                r"经营.*现金流净额",
                r"经营活动现金流量净额",
                r"^经营活动$",
                r"^经营活动\s",
            ],
            "investing": [
                r"投资活动产生的净现金流",
                r"投资活动.*净额",
                r"投资活动(产生)/使用.*净额",
                r"投资.*现金流净额",
                r"投资活动现金流量净额",
                r"^投资活动$",
                r"^投资活动\s",
                r"投资活动.*小计",
            ],
            "financing": [
                r"筹资活动产生的现金流量净额",
                r"筹资活动使用的现金流量净额",
                r"筹资活动(产生)/使用.*净额",
                r"筹资活动\(使用\)/产生.*净额",
                r"筹资.*现金流净额",
                r"筹资活动现金流量净额",
                r"^筹资活动产生$",
                r"^筹资活动$",
                r"^筹资活动\s",
                r"筹资活动.*小计",
            ],
            "net_increase": [
                r"现金及现金等价物净增加额",
                r"现金及现金等价物净减少额",
                r"现金及现金等价物.*净[增加减少]",
                r"现金及现金等价物净(增加|减少)",
                r"现金及现金等价物净(增加)/减少",
                r"现金及现金等价物净(减少)/增加",
                r"^[五六]、.*净[增加减少]",
                r"^[五六]、.*现金及现金等价物",
                r"现金净增加|现金净减少",
                r"[五六]、.*净\(.*\)/[增加减少]",
            ],
        }

        search_patterns = patterns.get(flow_type, [])
        for key in items.keys():
            for pattern in search_patterns:
                if re.search(pattern, key):
                    return items[key]
        return None

    def _find_total_by_pattern(
        self, items: Dict[str, float], pattern_key: str
    ) -> float:
        """根据模式查找合计项"""
        if not hasattr(self, "KEY_ITEM_PATTERNS"):
            return None
        patterns = self.KEY_ITEM_PATTERNS.get(pattern_key, [])
        for key in items.keys():
            for pattern in patterns:
                if re.search(pattern, key):
                    return items[key]
        return None

    def _calculate_completeness(self, items: Dict[str, float]) -> float:
        """
        计算数据完整性

        Args:
            items: 提取的科目数据

        Returns:
            完整性评分 (0-1)
        """
        if not items:
            return 0.0

        key_items_found = 0
        key_items_to_find = getattr(self, "KEY_ITEMS", [])
        if isinstance(key_items_to_find, list):
            for key in items.keys():
                for pattern in key_items_to_find:
                    if isinstance(pattern, str) and (pattern in key or key in pattern):
                        key_items_found += 1
                        break

        total_items = len(items)

        expected = EXPECTED_ITEMS_PER_TYPE.get(self.STATEMENT_TYPE, 30)
        item_count_score = min(total_items / expected, 1.0)

        expected_key_items = min(len(key_items_to_find), 5) if key_items_to_find else 5
        key_item_score = min(key_items_found / expected_key_items, 1.0)

        return (item_count_score * 0.3) + (key_item_score * 0.7)
