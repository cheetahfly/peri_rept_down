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
from extraction.config import SECTION_KEYWORDS

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
        normalized_data = self._normalize_units(merged_data)

        result = {
            "statement_type": self.STATEMENT_TYPE,
            "found": True,
            "pages": section_pages,
            "data": normalized_data,
            "extracted_at": datetime.now().isoformat(),
        }

        # NEW: Quality gate — if found but very few items, try auto-recovery
        found_items = len(normalized_data)
        min_items_for_quality = {"balance_sheet": 10, "income_statement": 5, "cash_flow": 5}
        min_items = min_items_for_quality.get(self.STATEMENT_TYPE, 5)

        if found_items < min_items:
            from extraction.word_recovery import recover_statement_auto
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

                if total_pages > 0:
                    scan_range = list(range(total_pages))
                    recovered = recover_statement_auto(
                        pdf_path, self.STATEMENT_TYPE, scan_range, top_n=10
                    )
                    if recovered.get("found"):
                        result["data"] = recovered.get("data", {})
                        result["recovered"] = True
                        result["recovery_method"] = recovered.get("recovery_method", "auto")
                        result["pages"] = recovered.get("pages", section_pages)

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

        real_pages = []
        for page_num in candidate_pages:
            # 提取页面文本进行附注页检测
            page_text = parser.extract_text(page_num)

            # 排除附注页：页面开头包含"附注"字样的页面不参与报表正文
            if self._is_appendix_page(page_text):
                continue

            tables = parser.extract_tables(page_num, min_rows=5, min_cols=2)

            if not tables:
                text_tables = parser.extract_text_tables(page_num)
                if text_tables:
                    for table in text_tables:
                        if self._is_valid_table(table):
                            real_pages.append(page_num)
                            break
                # 即使没有表格，也检查页面文本是否包含section header
                # （某些PDF的表格无法被pdfplumber提取，但关键词已在页眉）
                if page_num not in real_pages:
                    if self._text_has_section_header(page_text):
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
                if p not in real_pages:
                    real_pages.append(p)
            real_pages.sort()
        elif self.STATEMENT_TYPE == "balance_sheet":
            extra_pages = self._find_bs_continuation_pages(parser)
            for p in extra_pages:
                if p not in real_pages:
                    real_pages.append(p)
            real_pages.sort()

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

        # 扫描所有页面，查找CF章节header
        section_pattern = re.compile(
            r'[一二三四五六七八]、.{0,15}(经营|投资|筹资)活动.{0,30}(现金|流量|净额)'
        )

        for page_num in range(len(parser.doc.pages)):
            text = parser.extract_text(page_num)
            if section_pattern.search(text):
                # 进一步验证：页面应该包含数字（财务数据）
                if re.search(r'\d{3,}', text):
                    extra.append(page_num)

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

        # 扫描所有页面，查找BS汇总行（必须是"关键词 + 数字"的组合，排除干扰页）
        # 匹配: 关键词 换行/空格 亿元级数字（6位以上）
        section_pattern = re.compile(
            r'(?:^|\n)\s*(负债合计|非流动负债合计|流动负债合计|'
            r'所有者权益.*?合计|股东权益.*?合计|'
            r'归属于母公司.*?权益.*?合计|'
            r'负债和所有者权益.*?总计|'
            r'负债和股东权益.*?总计)'
            r'\s*[\d,]+(?:\.\d+)?(?:\s|$|\n)'
        )

        for page_num in range(len(parser.doc.pages)):
            text = parser.extract_text(page_num)
            if section_pattern.search(text):
                extra.append(page_num)

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
            
            # 匹配行首的"合并利润表"或"银行利润表"
            valid_header_pattern = r'^(合并利润表|银行利润表|利润表)$'
            valid_header_with_content = r'^(合并利润表|银行利润表)\s+(?![\d\-]+\s*$)'  # 后面跟内容但不是纯页码
            
            for p in [valid_header_pattern, valid_header_with_content]:
                if re.search(p, text, re.MULTILINE):
                    return True
            
            # 如果"利润表"出现在行首但匹配失败，说明可能是"XX利润表 11-12"这样的目录项
            if re.search(r'^合并利润表|^银行利润表', text, re.MULTILINE):
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
                # 真正的标题应该有"金额"或"本期"或"上期"等列标题
                if re.search(r'本期|上期|金额|年度|发生额', text):
                    return True

        elif self.STATEMENT_TYPE == "balance_sheet":
            # 资产负债表必须是"合并资产负债表"或"银行资产负债表"
            patterns = [
                r'^合并资产负债表',
                r'^银行资产负债表',
                r'^\s*合并资产负债表\s',
                r'^\s*银行资产负债表\s',
            ]
            for p in patterns:
                if re.search(p, text, re.MULTILINE):
                    return True

        elif self.STATEMENT_TYPE == "cash_flow":
            # 现金流量表必须是"合并现金流量表"或"银行现金流量表"
            patterns = [
                r'^合并现金流量表',
                r'^银行现金流量表',
                r'^\s*合并现金流量表\s',
                r'^\s*银行现金流量表\s',
            ]
            for p in patterns:
                if re.search(p, text, re.MULTILINE):
                    return True
            # 同时检查 CF 章节：数字+顿号开头，后面跟经营活动/投资活动/筹资活动
            section_pattern = r'[一二三四五六七八]、.{0,15}(经营|投资|筹资)活动.{0,30}(现金|流量|净额)'
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
        - 页面标题区域包含"财务报表附注"（如"四、财务报表附注"）
        - 包含章节编号+科目附注（如"47. 其他综合收益"）

        注意：不能仅因为表格中包含"附注"列标题就判定为附注页

        Args:
            text: 页面文本

        Returns:
            是否为附注页
        """
        if not text:
            return False

        # 获取页面开头区域（前1500字符，覆盖页面标题区域）
        header_area = text[:1500]

        # 附注页的明确标志：页面标题包含"财务报表附注"
        if '财务报表附注' in header_area:
            return True

        # 检查是否包含"附注"作为独立章节（章节编号 + 附注 + 科目名称）
        # 例如："47. 其他综合收益" 出现在页面开头部分
        # 这种格式是附注页的典型特征
        lines = header_area.split('\n')
        for i, line in enumerate(lines[:20]):  # 检查前20行
            line = line.strip()
            # 匹配 "47. 其他综合收益" 格式（章节编号 + 科目名称）
            if re.match(r'\d+\.\s*.+', line):
                # 检查这一行是否在页面开头部分（而不是表格中间）
                # 附注页的章节标题通常在页面开头几行
                if i < 10 and ('其他综合收益' in line or '外币报表' in line or '无形资产' in line or '应收账款' in line):
                    return True
            # 匹配 "四、" 格式（中文章节编号）
            if re.match(r'[一二三四五六七八九十]+、', line):
                if '附注' in line and i < 10:
                    return True

        return False

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

        return result

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

    def _normalize_units(self, data: Dict[str, float]) -> Dict[str, float]:
        """
        单位规范化（转换为元）

        Args:
            data: 原始数据字典

        Returns:
            规范化后的数据
        """
        # 检测单位
        unit, multiplier = self._detect_unit()

        if multiplier == 1:
            return data

        # 转换数值
        normalized = {}
        for key, value in data.items():
            normalized[key] = round(value * multiplier, 2)

        return normalized

    def _detect_unit(self) -> Tuple[str, float]:
        """
        检测PDF中的单位（结合文档声明和数值特征）

        Returns:
            (单位名称, 乘数)
        """
        unit, multiplier = self.parser.detect_unit()

        if multiplier != 1:
            return unit, multiplier

        for page_num in range(min(50, self.parser.page_count)):
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

        item_count_score = min(total_items / 40, 1.0)

        expected_key_items = min(len(key_items_to_find), 5) if key_items_to_find else 5
        key_item_score = min(key_items_found / expected_key_items, 1.0)

        return (item_count_score * 0.3) + (key_item_score * 0.7)
