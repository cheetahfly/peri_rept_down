# -*- coding: utf-8 -*-
"""
二维表格格式化模块

将提取的键值对财务数据转换为标准二维表格格式，
支持多年度对比、多公司对比。
"""

import os
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from . import config


class SchemaMapper:
    """数据映射器 - 处理别名和模糊匹配"""

    def __init__(self):
        self.alias_map = config.ITEM_ALIAS_MAP
        # 构建反向映射（标准名称 -> 所有可能的名称）
        self._reverse_map: Dict[str, List[str]] = {}
        for std_name, aliases in self.alias_map.items():
            self._reverse_map[std_name] = aliases
            # 也把标准名称加入自己的列表
            if std_name not in self._reverse_map[std_name]:
                self._reverse_map[std_name].append(std_name)

    def map(self, raw_name: str) -> Optional[str]:
        """
        将原始科目名称映射到标准科目名称

        Args:
            raw_name: 原始科目名称

        Returns:
            标准科目名称，如果无法映射则返回None
        """
        if not raw_name:
            return None

        raw_name = raw_name.strip()

        # 精确匹配标准名称
        for std_name in config.STATEMENT_TYPE_STANDARD_ITEMS.values():
            if raw_name in std_name:
                # 找到了所属的报表类型，检查是否匹配
                pass

        # 先在别名映射中查找
        for std_name, aliases in self.alias_map.items():
            if raw_name in aliases or raw_name == std_name:
                return std_name

        # 模糊匹配（包含关系）
        for std_name, aliases in self.alias_map.items():
            for alias in aliases:
                if alias in raw_name or raw_name in alias:
                    return std_name

        return None

    def get_standard_items(self, statement_type: str) -> List[str]:
        """获取指定报表类型的标准科目列表"""
        return config.STATEMENT_TYPE_STANDARD_ITEMS.get(statement_type, [])


class TableFormatter:
    """二维表格格式化器"""

    def __init__(self, schema_mapper: Optional[SchemaMapper] = None):
        self.schema_mapper = schema_mapper or SchemaMapper()

    def to_dataframe(
        self,
        kv_data: Dict[str, float],
        year: int,
        statement_type: str,
    ) -> pd.DataFrame:
        """
        将键值数据转换为标准顺序的DataFrame

        Args:
            kv_data: 键值对数据，如 {"资产总计": 5769270.0, ...}
            year: 报表年份
            statement_type: 报表类型 (balance_sheet/income_statement/cash_flow/indicators)

        Returns:
            DataFrame，列为 [指标名称, {year}年]
        """
        standard_items = self.schema_mapper.get_standard_items(statement_type)

        # 创建标准顺序的数据
        rows = []
        for item in standard_items:
            value = kv_data.get(item)
            rows.append({"指标名称": item, f"{year}年": value})

        df = pd.DataFrame(rows)
        return df

    def map_dataframe(
        self,
        df: pd.DataFrame,
        statement_type: str,
    ) -> pd.DataFrame:
        """
        将提取的DataFrame映射到标准格式

        Args:
            df: 提取的DataFrame，包含 指标名称 和值列
            statement_type: 报表类型

        Returns:
            映射后的标准格式DataFrame
        """
        if df.empty:
            standard_items = self.schema_mapper.get_standard_items(statement_type)
            return pd.DataFrame({"指标名称": standard_items})

        # 确保有指标名称列
        if "指标名称" not in df.columns and "item" in df.columns:
            df = df.rename(columns={"item": "指标名称"})

        # 获取标准科目
        standard_items = self.schema_mapper.get_standard_items(statement_type)

        # 创建标准顺序的DataFrame
        result_df = pd.DataFrame({"指标名称": standard_items})

        # 将原始数据的指标名称映射到标准名称
        if "指标名称" in df.columns:
            df["指标名称_标准"] = df["指标名称"].apply(self.schema_mapper.map)

            # 合并，保留标准名称
            for col in df.columns:
                if col not in ["指标名称", "指标名称_标准"]:
                    # 将数据映射到标准科目
                    mapped = df.groupby("指标名称_标准")[col].first()
                    result_df = result_df.merge(
                        mapped.reset_index().rename(
                            columns={"指标名称_标准": "指标名称"}
                        ),
                        on="指标名称",
                        how="left",
                    )

        return result_df

    def add_yoy_change(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算同比变化

        Args:
            df: 多年度DataFrame，列名为 "{year}年"

        Returns:
            添加了同比变化列的DataFrame
        """
        years = sorted([c.replace("年", "") for c in df.columns if c.endswith("年")])

        if len(years) < 2:
            return df

        # 计算同比变化
        for i in range(1, len(years)):
            prev_year = years[i - 1]
            curr_year = years[i]
            col_prev = f"{prev_year}年"
            col_curr = f"{curr_year}年"
            col_change = f"{curr_year}年同比变化%"

            if col_prev in df.columns and col_curr in df.columns:
                df[col_change] = ((df[col_curr] - df[col_prev]) / df[col_prev] * 100).round(2)

        return df


class MultiPeriodTableBuilder:
    """多期间表格构建器"""

    def __init__(self, schema_mapper: Optional[SchemaMapper] = None):
        self.schema_mapper = schema_mapper or SchemaMapper()
        self.formatter = TableFormatter(self.schema_mapper)

    def build_single_stock(
        self,
        kv_data_by_year: Dict[int, Dict[str, float]],
        statement_type: str,
        include_yoy: bool = True,
    ) -> pd.DataFrame:
        """
        构建单股票多年对比表

        Args:
            kv_data_by_year: {年份: {科目名: 值}}，如 {2024: {"资产总计": 5769270}, 2023: {...}}
            statement_type: 报表类型
            include_yoy: 是否计算同比变化

        Returns:
            DataFrame，行=科目，列=年份+同比变化
        """
        dfs = []
        for year, kv_data in sorted(kv_data_by_year.items()):
            year_df = self.formatter.to_dataframe(kv_data, year, statement_type)
            dfs.append(year_df)

        if not dfs:
            return pd.DataFrame()

        # 合并所有年份（按指标名称）
        result_df = dfs[0]
        for df in dfs[1:]:
            # 获取年份列名
            year_cols = [c for c in df.columns if c.endswith("年") and c != "指标名称"]
            if year_cols:
                year_col = year_cols[0]
                # 按指标名称合并
                result_df = result_df.merge(
                    df[["指标名称", year_col]],
                    on="指标名称",
                    how="outer",
                )

        # 按标准顺序排序
        standard_items = self.schema_mapper.get_standard_items(statement_type)
        result_df["_sort_key"] = result_df["指标名称"].apply(
            lambda x: standard_items.index(x) if x in standard_items else len(standard_items)
        )
        result_df = result_df.sort_values("_sort_key").drop(columns=["_sort_key"])
        result_df = result_df.reset_index(drop=True)

        # 计算同比变化
        if include_yoy:
            result_df = self.formatter.add_yoy_change(result_df)

        return result_df

    def build_multi_stock(
        self,
        stock_data: Dict[Tuple[str, str], Dict[str, float]],
        # {(stock_code, stock_name): {科目名: 值}}
        year: int,
        statement_type: str,
    ) -> pd.DataFrame:
        """
        构建多股票同年对比表

        Args:
            stock_data: {(股票代码, 股票名称): {科目名: 值}}
            year: 报表年份
            statement_type: 报表类型

        Returns:
            DataFrame，行=股票，列=股票代码、股票名称、科目1、科目2、...
        """
        standard_items = self.schema_mapper.get_standard_items(statement_type)

        # 创建结果表
        rows = []
        for (stock_code, stock_name), kv_data in stock_data.items():
            row = {"股票代码": stock_code, "股票名称": stock_name}
            for item in standard_items:
                row[item] = kv_data.get(item)
            rows.append(row)

        result_df = pd.DataFrame(rows)

        # 调整列顺序：股票代码、股票名称在前，然后是标准科目
        cols = ["股票代码", "股票名称"] + standard_items
        cols = [c for c in cols if c in result_df.columns]
        result_df = result_df[cols]

        return result_df


def export_to_csv(df: pd.DataFrame, file_path: str, encoding: str = 'utf-8-sig') -> bool:
    """
    导出DataFrame为CSV文件

    Args:
        df: 要导出的DataFrame
        file_path: 文件路径
        encoding: 编码格式

    Returns:
        是否成功
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else ".", exist_ok=True)
    df.to_csv(file_path, index=False, encoding=encoding, errors='replace')
    return True
