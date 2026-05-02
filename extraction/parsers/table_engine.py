# -*- coding: utf-8 -*-
"""
通用表格解析引擎

设计目标:
1. 将表格结构分析与数据提取解耦
2. 支持多种数据源 (PDF, HTML, OCR)
3. 配置驱动而非硬编码
4. 易于扩展新股票和新报表类型

架构:
    TableParserEngine (统一入口)
        ├── SourceAdapter (数据源适配器)
        │   ├── PdfTableSource (pdfplumber)
        │   ├── HtmlTableSource (BeautifulSoup/lxml)
        │   └── OcrTableSource (Tesseract OCR)
        │
        ├── TableStructureAnalyzer (表格结构分析)
        │   ├── RowClassifier (行分类：标题/数据/合计/附注)
        │   ├── ColumnDetector (列检测：年份/附注)
        │   └── TableTypeDetector (表格类型检测)
        │
        └── TableDataNormalizer (数据规范化)
            ├── NumberParser (数值解析)
            ├── ItemNameNormalizer (科目名标准化)
            └── UnitNormalizer (单位规范化)
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable
from enum import Enum
import pandas as pd
import numpy as np


class RowType(Enum):
    """行类型"""
    HEADER = "header"           # 表头行
    DATA = "data"               # 数据行
    SUBTOTAL = "subtotal"       # 小计行
    TOTAL = "total"            # 合计行
    NOTE = "note"               # 附注行
    INDENT = "indent"           # 缩进行（明细项）
    UNKNOWN = "unknown"


class StatementType(Enum):
    """报表类型"""
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow"


class ColumnType(Enum):
    """列类型"""
    ITEM_NAME = "item_name"     # 项目名称列
    VALUE_CURRENT = "value_current"  # 本期数值
    VALUE_PRIOR = "value_prior"      # 上期数值
    NOTE = "note"               # 附注列
    INDEX = "index"             # 索引列


@dataclass
class ParsedRow:
    """解析后的行"""
    row_type: RowType
    item_name: str
    values: Dict[str, float] = field(default_factory=dict)  # {年份: 数值}
    note: str = ""
    level: int = 0  # 层级（用于缩进）
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "type": self.row_type.value,
            "item_name": self.item_name,
            "values": self.values,
            "note": self.note,
            "level": self.level,
        }


@dataclass
class ParsedTable:
    """解析后的表格"""
    statement_type: StatementType
    rows: List[ParsedRow] = field(default_factory=list)
    columns: Dict[str, str] = field(default_factory=dict)  # 列名映射
    unit: str = "元"
    multiplier: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        if not self.rows:
            return pd.DataFrame()
        
        data = []
        for row in self.rows:
            record = {
                "item_name": row.item_name,
                "row_type": row.row_type.value,
                "note": row.note,
                "level": row.level,
            }
            record.update(row.values)
            data.append(record)
        
        return pd.DataFrame(data)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "statement_type": self.statement_type.value,
            "rows": [r.to_dict() for r in self.rows],
            "columns": self.columns,
            "unit": self.unit,
            "multiplier": self.multiplier,
            "metadata": self.metadata,
        }


class NumberParser:
    """数值解析器"""
    
    # 常见格式: (100), -100, 1,234.56, 1.234,56
    NUMBER_PATTERNS = [
        r"[-+]?[\d,]+\.?\d*",  # 标准格式
        r"[\d\s]+\.?\d*",       # 可能带空格
    ]
    
    # 括号表示负数
    NEGATIVE_BRACKETS = [("(", ")"), ("（", "）")]
    
    @classmethod
    def parse(cls, text: str) -> Optional[float]:
        """解析数值为浮点数"""
        if not isinstance(text, str):
            text = str(text)
        
        text = text.strip()
        if not text:
            return None
        
        # 检测括号负数
        is_negative = False
        for open_b, close_b in cls.NEGATIVE_BRACKETS:
            if open_b in text and close_b in text:
                is_negative = True
                text = text.replace(open_b, "").replace(close_b, "")
                break
        
        # 移除非数字字符（保留小数点和负号）
        text = re.sub(r"[^\d.\-+]", "", text)
        
        if not text:
            return None
        
        try:
            value = float(text)
            return -value if is_negative else value
        except ValueError:
            return None
    
    @classmethod
    def format(cls, value: float, decimals: int = 2) -> str:
        """格式化数值"""
        if value is None:
            return ""
        return f"{value:,.{decimals}f}"


class ItemNameNormalizer:
    """科目名称标准化"""
    
    # 同义词映射
    SYNONYMS = {
        # 资产类
        "货币资金": ["现金", "库存现金", "银行存款"],
        "应收账款": ["应收帐款", "应收款"],
        "其他应收款": ["其他应收款项", "应收其他款"],
        "固定资产": ["固定资資産", "固定"],
        "无形资产": ["无型資産", "无开资产"],
        "在建工程": ["在建工程款", "在建"],
        "商誉": ["商誉", "goodwill"],
        
        # 负债类
        "应付账款": ["应付帐款", "应付款"],
        "其他应付款": ["其他应付款式", "应付其他款"],
        "长期借款": ["长期贷款", "长期借欯"],
        "短期借款": ["短期贷款", "短期借欯"],
        
        # 权益类
        "实收资本": ["股本", "注册资金", "实收资本"],
        "未分配利润": ["未分配利润", "未分利润", "未分配利润款"],
        "归属母公司股东权益": ["归属母公司股东权益合计", "母公司股东权益"],
        
        # 利润表
        "营业收入": ["营业收入", "主营收入", "销售总额"],
        "营业成本": ["营业成本", "主营成本", "销售成本"],
        "销售费用": ["销售费用", "营绔费用", "销售欴用"],
        "管理费用": ["管理费用", "管理欴用"],
        "财务费用": ["财务费用", "财务欴用"],
        "净利润": ["净利润", "净利", "利润净额"],
        "归属母公司净利润": ["归属母公司所有者的净利润", "母公司净利润"],
        
        # 现金流量表
        "经营活动产生的现金流量净额": ["经营活动产生的现金流量净额", "经营现金流净额", "经营活动现金流"],
        "经营活动使用的现金流量净额": ["经营活动使用的现金流量净额", "经营现金流净流出"],
        "投资活动产生的现金流量净额": ["投资活动产生的现金流量净额", "投资现金流净额"],
        "筹资活动产生的现金流量净额": ["筹资活动产生的现金流量净额", "筹资现金流净额"],
    }
    
    # 需要过滤的无效名称
    INVALID_PATTERNS = [
        r"^第[一二三四五六七八九十]+[章节页]?$",
        r"^[①②③④⑤⑥⑦⑧⑨⑩]$",
        r"^见[上中下]?[下中上]?[节页]?$",
        r"^[0-9]+$",
        r"^[A-Za-z]+$",
        r"^\s*$",
        r"^的[现金资产负债权益]|^[现金资产负债权益]的$",
    ]
    
    @classmethod
    def normalize(cls, name: str) -> str:
        """标准化科目名称"""
        if not name:
            return ""
        
        name = name.strip()
        
        # 检查无效模式
        for pattern in cls.INVALID_PATTERNS:
            if re.match(pattern, name):
                return ""
        
        # 查表替换
        for standard, synonyms in cls.SYNONYMS.items():
            if name in synonyms or name == standard:
                return standard
        
        return name
    
    @classmethod
    def is_valid(cls, name: str) -> bool:
        """检查是否是有效的科目名称"""
        return bool(cls.normalize(name))


class TableStructureAnalyzer:
    """表格结构分析器"""
    
    # 报表类型关键词
    STATEMENT_KEYWORDS = {
        StatementType.BALANCE_SHEET: ["资产负债表", "资产", "负债", "所有者权益", "股东权益"],
        StatementType.INCOME_STATEMENT: ["利润表", "营业收入", "净利润", "营业利润", "利润总额"],
        StatementType.CASH_FLOW: ["现金流量表", "经营活动", "投资活动", "筹资活动", "现金"],
    }
    
    # 表头行模式
    HEADER_PATTERNS = [
        r"项目",
        r"期[末初]余额",
        r"期[末初]发生额",
        r"本期[金额发生]",
        r"上期[金额发生]",
        r"\d{4}年",
        r"\d{4}[-/]\d{2}",
    ]
    
    # 合计行模式
    TOTAL_PATTERNS = [
        r"资产总计",
        r"负债合计",
        r"负债和所有者权益总计",
        r"负债及所有者权益合计",
        r"股东权益合计",
        r"所有者权益合计",
        r"净利润",
        r"现金及现金等价物净增加",
        r"现金及现金等价物余额",
    ]
    
    # 小计行模式
    SUBTOTAL_PATTERNS = [
        r"小计",
        r"合计",
        r"其中",
        r"其中：",
    ]
    
    # 附注行模式
    NOTE_PATTERNS = [
        r"^\d+[a-z]?$",  # 7f, 49(f)
        r"^[一二三四五六七八九十]+[、.].*",  # 七、1
        r"^注：",
        r"^注释：",
    ]
    
    @classmethod
    def detect_statement_type(cls, text: str) -> Optional[StatementType]:
        """检测报表类型"""
        text = str(text)
        
        scores = {}
        for stmt_type, keywords in cls.STATEMENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[stmt_type] = score
        
        if not scores:
            return None
        
        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] > 0 else None
    
    @classmethod
    def classify_row(cls, row_text: str, prev_row: str = None) -> RowType:
        """分类行类型"""
        row_text = str(row_text).strip()
        
        # 检查表头
        for pattern in cls.HEADER_PATTERNS:
            if re.search(pattern, row_text):
                return RowType.HEADER
        
        # 检查附注
        for pattern in cls.NOTE_PATTERNS:
            if re.match(pattern, row_text):
                return RowType.NOTE
        
        # 检查合计行
        for pattern in cls.TOTAL_PATTERNS:
            if re.search(pattern, row_text):
                return RowType.TOTAL
        
        # 检查小计行
        for pattern in cls.SUBTOTAL_PATTERNS:
            if re.search(pattern, row_text):
                return RowType.SUBTOTAL
        
        return RowType.DATA
    
    @classmethod
    def detect_columns(cls, header_row: pd.Series) -> Dict[str, ColumnType]:
        """检测列类型"""
        columns = {}
        
        for i, col in enumerate(header_row):
            col_str = str(col) if pd.notna(col) else ""
            
            if re.search(r"项目", col_str):
                columns[i] = ColumnType.ITEM_NAME
            elif re.search(r"本期|当期|期末|本期发生", col_str):
                columns[i] = ColumnType.VALUE_CURRENT
            elif re.search(r"上期|期初|年初|上期发生", col_str):
                columns[i] = ColumnType.VALUE_PRIOR
            elif re.search(r"附注|注释|注", col_str):
                columns[i] = ColumnType.NOTE
            else:
                columns[i] = ColumnType.VALUE_CURRENT  # 默认当作数值列
        
        return columns


class UnitNormalizer:
    """单位规范化"""
    
    UNIT_MULTIPLIERS = {
        "元": 1,
        "万元": 10000,
        "亿元": 100000000,
        "千元": 1000,
        "百万元": 1000000,
        "万元": 10000,
    }
    
    @classmethod
    def detect_unit(cls, text: str) -> Tuple[str, float]:
        """从文本中检测单位"""
        for unit, multiplier in cls.UNIT_MULTIPLIERS.items():
            if unit in text:
                return unit, multiplier
        return "元", 1
    
    @classmethod
    def normalize_value(cls, value: float, from_unit: str, to_unit: str = "元") -> float:
        """规范化数值单位"""
        if from_unit not in cls.UNIT_MULTIPLIERS:
            return value
        
        from_mult = cls.UNIT_MULTIPLIERS[from_unit]
        to_mult = cls.UNIT_MULTIPLIERS.get(to_unit, 1)
        
        return value * (from_mult / to_mult)


class TableParserEngine:
    """
    通用表格解析引擎
    
    使用方式:
        engine = TableParserEngine()
        
        # 从PDF解析
        tables = engine.parse_pdf("report.pdf", statement_types=[StatementType.BALANCE_SHEET])
        
        # 从HTML解析
        tables = engine.parse_html("<table>...</table>", statement_types=[StatementType.BALANCE_SHEET])
        
        # 从OCR解析
        tables = engine.parse_ocr(image_path, statement_types=[StatementType.BALANCE_SHEET])
    """
    
    def __init__(self):
        self.analyzer = TableStructureAnalyzer()
        self.number_parser = NumberParser()
        self.item_normalizer = ItemNameNormalizer()
        self.unit_normalizer = UnitNormalizer()
    
    def parse_dataframe(
        self,
        df: pd.DataFrame,
        statement_type: StatementType,
        unit: str = "元",
        multiplier: float = 1.0
    ) -> ParsedTable:
        """
        解析DataFrame为结构化表格
        
        Args:
            df: 原始DataFrame
            statement_type: 报表类型
            unit: 数值单位
            multiplier: 单位乘数
        
        Returns:
            ParsedTable 结构化表格
        """
        if df.empty:
            return ParsedTable(statement_type=statement_type)
        
        result = ParsedTable(
            statement_type=statement_type,
            unit=unit,
            multiplier=multiplier,
            metadata={"original_columns": list(df.columns)}
        )
        
        # 检测列类型
        header_row = df.iloc[0] if len(df) > 0 else pd.Series()
        column_types = self.analyzer.detect_columns(header_row)
        
        # 解析每一行
        for idx, row in df.iterrows():
            row_text = str(row.iloc[0]) if len(row) > 0 else ""
            row_type = self.analyzer.classify_row(row_text)
            
            # 标准化科目名称
            item_name = self.item_normalizer.normalize(row_text)
            
            # 跳过无效行
            if not item_name and row_type == RowType.DATA:
                continue
            
            # 提取数值
            values = {}
            for col_idx, col_type in column_types.items():
                if col_type == ColumnType.ITEM_NAME:
                    continue
                
                if col_idx < len(row):
                    cell_value = row.iloc[col_idx]
                    parsed = self.number_parser.parse(cell_value)
                    if parsed is not None:
                        # 获取列标题作为年份标识
                        col_header = df.columns[col_idx] if col_idx < len(df.columns) else str(col_idx)
                        values[str(col_header)] = parsed * multiplier
            
            parsed_row = ParsedRow(
                row_type=row_type,
                item_name=item_name or row_text,
                values=values,
            )
            result.rows.append(parsed_row)
        
        return result
    
    def parse_pdf(self, pdf_path: str, statement_types: List[StatementType] = None) -> List[ParsedTable]:
        """从PDF解析表格"""
        from extraction.parsers.pdf_parser import PdfParser
        
        tables = []
        statement_types = statement_types or list(StatementType)
        
        with PdfParser(pdf_path) as parser:
            for page_num in range(parser.page_count):
                page_text = parser.extract_text(page_num)
                
                # 检测报表类型
                detected_type = self.analyzer.detect_statement_type(page_text)
                if detected_type and detected_type not in statement_types:
                    continue
                
                # 提取表格
                page_tables = parser.extract_tables(page_num)
                for df in page_tables:
                    if detected_type:
                        parsed = self.parse_dataframe(df, detected_type)
                        tables.append(parsed)
        
        return tables
    
    def merge_continuation(self, tables: List[ParsedTable]) -> List[ParsedTable]:
        """合并跨页表格"""
        if not tables:
            return []
        
        merged = [tables[0]]
        
        for table in tables[1:]:
            last = merged[-1]
            
            # 检查是否应该合并
            if self._should_merge(last, table):
                merged[-1] = self._do_merge(last, table)
            else:
                merged.append(table)
        
        return merged
    
    def _should_merge(self, table1: ParsedTable, table2: ParsedTable) -> bool:
        """判断两个表格是否应该合并"""
        # 同一类型
        if table1.statement_type != table2.statement_type:
            return False
        
        # 检查最后一行是否是不完整的（没有数值）
        if not table1.rows:
            return False
        
        last_row = table1.rows[-1]
        if last_row.values:
            return False  # 最后一行完整，不需要合并
        
        return True
    
    def _do_merge(self, table1: ParsedTable, table2: ParsedTable) -> ParsedTable:
        """合并两个表格"""
        merged = ParsedTable(
            statement_type=table1.statement_type,
            unit=table1.unit,
            multiplier=table1.multiplier,
        )
        
        # 复制第一张表的所有行（除了最后一行空行）
        for row in table1.rows[:-1]:
            merged.rows.append(row)
        
        # 添加第二张表的所有行
        for row in table2.rows:
            merged.rows.append(row)
        
        return merged


# 便捷函数
def extract_tables_from_pdf(pdf_path: str, statement_types: List[StatementType] = None) -> List[ParsedTable]:
    """从PDF提取结构化表格"""
    engine = TableParserEngine()
    return engine.parse_pdf(pdf_path, statement_types)


def extract_tables_from_dataframe(
    df: pd.DataFrame,
    statement_type: StatementType,
    unit: str = "元",
    multiplier: float = 1.0
) -> ParsedTable:
    """从DataFrame提取结构化表格"""
    engine = TableParserEngine()
    return engine.parse_dataframe(df, statement_type, unit, multiplier)


if __name__ == "__main__":
    # 测试
    print("TableParserEngine 模块测试")
    
    # 测试数值解析
    assert NumberParser.parse("(100)") == -100.0
    assert NumberParser.parse("1,234.56") == 1234.56
    print("NumberParser: OK")
    
    # 测试科目名称标准化
    assert ItemNameNormalizer.normalize("现金") == "货币资金"
    assert ItemNameNormalizer.normalize("净利润") == "净利润"
    print("ItemNameNormalizer: OK")
    
    # 测试行分类
    assert TableStructureAnalyzer.classify_row("项目 期末余额 期初余额") == RowType.HEADER
    assert TableStructureAnalyzer.classify_row("资产总计") == RowType.TOTAL
    assert TableStructureAnalyzer.classify_row("货币资金") == RowType.DATA
    print("TableStructureAnalyzer: OK")
    
    print("\n所有测试通过!")
