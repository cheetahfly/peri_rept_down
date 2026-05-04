# -*- coding: utf-8 -*-
"""
表格解析和规范化
"""

import re
from typing import List, Dict, Tuple, Optional
import pandas as pd


class TableParser:
    """表格解析和规范化"""

    COLUMN_PATTERNS = {
        "standard": {
            "balance_sheet": [
                ["项目", "期末余额", "期初余额"],
                ["项目", "期末余额", "年初余额"],
                ["项目", "本期余额", "上期余额"],
            ],
            "income_statement": [
                ["项目", "本期金额", "上期金额"],
                ["项目", "本期发生额", "上期发生额"],
                ["项目", "本期", "上期"],
            ],
            "cash_flow": [
                ["项目", "本期金额", "上期金额"],
                ["项目", "现金流量", "上期现金流量"],
            ],
        },
        "reverse": {
            "balance_sheet": [
                ["项目", "期初余额", "期末余额"],
                ["项目", "年初余额", "期末余额"],
            ],
        },
    }

    CLEAN_PATTERNS = [
        (r"\s+", " "),
        (r"^\s+|\s+$", ""),
        (r"[,，]", ""),
        (r"[\\(（]\s*[\\)）]", ""),
        # 合并跨列拆分的净利润行: "四、净" + "(亏损)" + "/" + "利润" -> "四、净利润"
        (r"四、净\s*\(\s*亏\s*损\s*\)\s*/\s*利\s*润", "净利润"),
        (r"四、净\s*/\s*利\s*润", "净利润"),
        # 同理处理其他跨列拆分的科目（以"X、"开头后面跟单字的）
        (r"([一二三四五六七八九十]+、)([^资产负\d][^益处]?)\s*\(\s*亏\s*损\s*\)\s*/\s*利\s*润", r"\1\2净利润"),
        (r"([一二三四五六七八九十]+、)([^资产负\d][^益处]?)\s*/\s*利\s*润", r"\1\2净利润"),
    ]

    NUMBER_PATTERN = r"[-+]?[\d,，]+(?:\.[\d]+)?(?:[eE][-+]?\d+)?"

    INVALID_ITEM_PATTERNS = [
        r"^第[一二三四五六七八九十]+[章节页]$",
        r"^[①②③④⑤⑥⑦⑧⑨⑩]$",
        r"^见[上中下]?[下中上]?[节页]?$",
        r"^[0-9]+$",
        r"^[A-Za-z]+$",
        r"^的[现金资产负债权益]|^[现金资产负债权益]的$",
        r"^[的了是在]?[现金资产负债权益]*(的|了|是)?$",
    ]

    ITEM_NAME_MIN_LEN = 2
    ITEM_NAME_MAX_LEN = 50

    @classmethod
    def clean_text(cls, text: str) -> str:
        """
        清理文本

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not isinstance(text, str):
            text = str(text)

        for pattern, replacement in cls.CLEAN_PATTERNS:
            text = re.sub(pattern, replacement, text)

        return text.strip()

    @classmethod
    def parse_number(cls, text: str) -> Optional[float]:
        """
        解析数值为浮点数

        Args:
            text: 数值文本

        Returns:
            数值或None
        """
        if not isinstance(text, str):
            text = str(text)

        text = cls.clean_text(text)

        # 处理括号表示负数
        is_negative = "(" in text and ")" in text
        text = (
            text.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
        )

        # 匹配数值
        match = re.search(cls.NUMBER_PATTERN, text.replace(",", "").replace("，", ""))
        if match:
            try:
                value = float(match.group().replace(",", "").replace("，", ""))
                return -value if is_negative else value
            except ValueError:
                return None

        return None

    @classmethod
    def detect_statement_type(cls, header_row: pd.Series) -> Optional[str]:
        """
        检测报表类型

        Args:
            header_row: 表头行

        Returns:
            报表类型或None
        """
        header_text = " ".join([str(v) for v in header_row.values if pd.notna(v)])

        if "资产" in header_text and "负债" in header_text:
            return "balance_sheet"
        elif "利润" in header_text or "损益" in header_text:
            return "income_statement"
        elif "现金" in header_text and "流量" in header_text:
            return "cash_flow"

        return None

    @classmethod
    def normalize_columns(cls, df: pd.DataFrame, statement_type: str) -> pd.DataFrame:
        """
        规范化表格列名

        Args:
            df: 原始DataFrame
            statement_type: 报表类型

        Returns:
            规范化后的DataFrame
        """
        if df.empty:
            return df

        df = df.copy()

        # 第一行作为临时表头
        if df.shape[1] >= 2:
            # 尝试识别列模式
            first_row = df.iloc[0].astype(str)
            col_patterns = cls.COLUMN_PATTERNS["standard"].get(statement_type, [])

            matched_pattern = None
            for pattern in col_patterns:
                if all(p in first_row.values for p in pattern):
                    matched_pattern = pattern
                    break

            if matched_pattern:
                # 使用匹配的模式重命名列
                new_cols = list(df.columns[: len(matched_pattern)]) + list(
                    df.columns[len(matched_pattern) :]
                )
                for i, c in enumerate(new_cols[: len(matched_pattern)]):
                    df.rename(columns={c: matched_pattern[i]}, inplace=True)

        return df

    @classmethod
    def extract_items(cls, df: pd.DataFrame, item_col: str = None) -> Dict[str, float]:
        """
        从表格提取科目数据

        Args:
            df: 表格DataFrame
            item_col: 科目列名（默认为第一列）

        Returns:
            {科目名: 数值} 字典
        """
        if df.empty:
            return {}

        result = {}

        if item_col is None:
            item_col = df.columns[0]

        if item_col not in df.columns:
            item_col = df.columns[0]

        # 转换数据类型避免 StringDtype 迭代问题
        df = df.astype(object)

        for idx, row in df.iterrows():
            # 检测并修复跨列拆分的科目名（如 pdfplumber 把"四、净利润"拆成"四、净 | (亏损) | / | 利润"）
            raw_item = str(row[item_col]) if pd.notna(row[item_col]) else ""
            item_name = cls._fix_split_item_name(row, item_col)
            item_name = cls.clean_text(item_name)

            if not item_name or item_name in ["项目", "项目名称", ""]:
                continue

            if not cls._is_valid_item_name(item_name):
                continue

            value = None
            best_value = None
            value, best_value = cls._extract_best_value(row, df.columns, item_col)

            if value is None and best_value is not None:
                value = best_value

            if value is not None:
                result[item_name] = value

        return result

    @classmethod
    def _fix_split_item_name(cls, row: pd.Series, item_col: str) -> str:
        """
        修复跨列拆分的科目名。

        pdfplumber有时会把一个完整科目名拆成多列，例如：
          "四、净利润" -> col0="四、净", col1="(亏损)", col2="/", col3="利润"

        检测模式：col0 类似 "X、Y" 且 col1, col2, col3 是括号/斜杠等符号片段。
        """
        cols = list(row.index)
        if item_col not in cols:
            return str(row[item_col]) if pd.notna(row[item_col]) else ""

        item_idx = cols.index(item_col)
        # 只检查前面几列（通常是0,1,2,3）
        if item_idx > 3:
            return str(row[item_col]) if pd.notna(row[item_col]) else ""

        # 收集从 item_col 开始的连续非数值片段
        parts = []
        for i in range(item_idx, min(item_idx + 6, len(cols))):
            cell = row[cols[i]]
            if pd.isna(cell):
                break
            cell_str = str(cell).strip()
            if not cell_str:
                break
            # 如果单元格包含数字，认为是数值开始了（停止收集）
            if re.search(r'\d', cell_str):
                break
            parts.append(cell_str)

        # 只有当收集到多个片段时才说明是跨列拆分，否则返回原始值
        if len(parts) >= 2:
            merged = ''.join(parts)
            # 归一化合并后的科目名（如"二、营业(亏损)/利润" -> "营业利润"）
            merged = cls._normalize_item_name(merged)
            return merged

        return str(row[item_col]) if pd.notna(row[item_col]) else ""

    @classmethod
    def _normalize_item_name(cls, name: str) -> str:
        """
        归一化跨列拆分合并后的科目名。

        例如：
          "二、营业(亏损)/利润" -> "营业利润"
          "三、(亏损)/利润总额" -> "利润总额"
          "四、净(亏损)/利润"   -> "净利润"
        """
        # 移除 "X、" 前缀（X可以是任何数字序号）
        name = re.sub(r'^[一二三四五六七八九十]+、', '', name)
        # 移除 (亏损)/ 或 (亏损)  之类的中间标记
        name = re.sub(r'\(?\s*亏\s*损\s*\)?\s*/', '', name)
        # 移除剩余的括号
        name = re.sub(r'[()（）]', '', name)
        return name.strip()

    @classmethod
    def _extract_best_value(cls, row: pd.Series, columns, item_col: str) -> Tuple[Optional[float], Optional[float]]:
        """
        从一行中提取最佳数值。

        Returns:
            (value, best_value) - value是满足阈值条件的值，best_value是绝对值最大的值
        """
        value = None
        best_value = None
        best_abs = 0
        item_idx = list(columns).index(item_col) if item_col in columns else 0

        for col in columns:
            if col == item_col or col is None:
                continue
            cell_value = row[col]
            if pd.notna(cell_value):
                parsed = cls.parse_number(cell_value)
                if parsed is not None:
                    abs_parsed = abs(parsed)
                    if best_value is None or abs_parsed > best_abs:
                        best_value = parsed
                        best_abs = abs_parsed
                    # 阈值条件
                    if abs_parsed > 100:
                        # 特殊处理：当第一数值列是括号负数(如"(亏损)")时，优先用右边的列
                        cell_str = str(cell_value).strip()
                        if cell_str.startswith('(') and ')' in cell_str:
                            # 括号负数出现在第一个数值列（item_col+1附近），
                            # 说明真正的值在更右边的列，继续搜索
                            # 只有当这是最右边的数值列时才使用
                            pass
                        else:
                            value = parsed
                            break

        return value, best_value

    @classmethod
    def _is_valid_item_name(cls, name: str) -> bool:
        """
        验证是否是有效的科目名称

        Args:
            name: 科目名称

        Returns:
            是否有效
        """
        if not name or len(name) < cls.ITEM_NAME_MIN_LEN:
            return False

        if len(name) > cls.ITEM_NAME_MAX_LEN:
            return False

        for pattern in cls.INVALID_ITEM_PATTERNS:
            if re.match(pattern, name):
                return False

        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in name)
        if not has_chinese:
            return False

        if name.isdigit():
            return False

        return True

    @classmethod
    def merge_horizontal_tables(cls, tables: List[pd.DataFrame]) -> pd.DataFrame:
        """
        合并水平排列的表格（如资产负债表的资产和负债部分）

        Args:
            tables: 表格列表

        Returns:
            合并后的DataFrame
        """
        if not tables:
            return pd.DataFrame()

        if len(tables) == 1:
            return tables[0]

        # 简单横向合并
        result = tables[0]
        for df in tables[1:]:
            # 基于第一列匹配
            if result.shape[0] > 0 and df.shape[0] > 0:
                result = pd.concat([result, df.iloc[:, 1:]], axis=1)

        return result

    @classmethod
    def validate_balance_sheet(
        cls, assets: Dict[str, float], liabilities_equity: Dict[str, float]
    ) -> bool:
        """
        验证资产负债表平衡

        Args:
            assets: 资产科目字典
            liabilities_equity: 负债和所有者权益科目字典

        Returns:
            是否平衡
        """
        # 查找合计项
        assets_total = None
        for key in assets:
            if "资产总计" in key or "资产合计" in key:
                assets_total = assets[key]
                break

        liabilities_equity_total = None
        for key in liabilities_equity:
            if "负债和所有者权益总计" in key or "负债及所有者权益合计" in key:
                liabilities_equity_total = liabilities_equity[key]
                break

        if assets_total is not None and liabilities_equity_total is not None:
            # 允许小量误差
            return abs(assets_total - liabilities_equity_total) < abs(
                assets_total * 0.001
            )

        return True  # 无法验证时返回True
