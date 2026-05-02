# -*- coding: utf-8 -*-
"""
JSON存储模块
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd

from extraction.config import EXTRACTED_BY_CODE_DIR


class JsonStore:
    """JSON格式存储"""

    def __init__(self, base_dir: str = None):
        """
        初始化存储

        Args:
            base_dir: 存储根目录
        """
        self.base_dir = base_dir or EXTRACTED_BY_CODE_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    def save(self, stock_code: str, year: int, statement_type: str,
             data: Dict, file_path: str = None) -> str:
        """
        保存提取结果

        Args:
            stock_code: 股票代码
            year: 报告年份
            statement_type: 报表类型
            data: 提取的数据
            file_path: 指定路径（可选）

        Returns:
            保存的文件路径
        """
        if file_path is None:
            file_path = self._generate_path(stock_code, year, statement_type)

        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 构建保存数据
        save_data = {
            "stock_code": stock_code,
            "report_year": year,
            "statement_type": statement_type,
            "data": data,
            "saved_at": datetime.now().isoformat(),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        return file_path

    def save_all(self, stock_code: str, year: int, extracted_data: Dict) -> List[str]:
        """
        保存所有报表类型

        Args:
            stock_code: 股票代码
            year: 报告年份
            extracted_data: {报表类型: 数据}

        Returns:
            保存的文件路径列表
        """
        saved_paths = []

        for statement_type, data in extracted_data.items():
            if data and data.get("found"):
                file_path = self.save(stock_code, year, statement_type, data)
                saved_paths.append(file_path)

        return saved_paths

    def load(self, file_path: str) -> Optional[Dict]:
        """
        加载JSON数据

        Args:
            file_path: 文件路径

        Returns:
            数据字典或None
        """
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all(self, stock_code: str, year: int) -> Dict[str, Dict]:
        """
        加载某股票某年的所有报表

        Args:
            stock_code: 股票代码
            year: 报告年份

        Returns:
            {报表类型: 数据} 字典
        """
        result = {}

        for statement_type in ["balance_sheet", "income_statement", "cash_flow"]:
            file_path = self._generate_path(stock_code, year, statement_type)
            data = self.load(file_path)
            if data:
                result[statement_type] = data.get("data", {})

        return result

    def _generate_path(self, stock_code: str, year: int, statement_type: str) -> str:
        """生成文件路径"""
        stock_dir = os.path.join(self.base_dir, stock_code)
        file_name = f"{stock_code}_{year}_{statement_type}.json"
        return os.path.join(stock_dir, file_name)

    def list_files(self, stock_code: str = None) -> List[str]:
        """
        列出JSON文件

        Args:
            stock_code: 股票代码（可选）

        Returns:
            文件路径列表
        """
        if stock_code:
            search_dir = os.path.join(self.base_dir, stock_code)
        else:
            search_dir = self.base_dir

        if not os.path.exists(search_dir):
            return []

        files = []
        for root, _, filenames in os.walk(search_dir):
            for filename in filenames:
                if filename.endswith(".json"):
                    files.append(os.path.join(root, filename))

        return sorted(files)

    @staticmethod
    def parse_stock_code_from_filename(filename: str) -> Optional[str]:
        """从文件名解析股票代码"""
        match = re.match(r'^(\d{6})', filename)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def parse_year_from_filename(filename: str) -> Optional[int]:
        """从文件名解析年份"""
        match = re.search(r'(\d{4})', filename)
        if match:
            return int(match.group(1))
        return None

    def load_for_table(
        self,
        stock_code: str,
        years: List[int],
        statement_type: str,
    ) -> Dict[int, Dict[str, float]]:
        """
        加载多年数据用于表格导出

        Args:
            stock_code: 股票代码
            years: 年份列表
            statement_type: 报表类型

        Returns:
            {年份: {科目名: 值}}
        """
        result = {}
        for year in years:
            file_path = self._generate_path(stock_code, year, statement_type)
            data = self.load(file_path)
            if data:
                # data的结构是 {"stock_code": ..., "report_year": ..., "data": {"statement_type": ..., "found": true, "data": {...}}}
                inner_data = data.get("data", {})
                if inner_data.get("found"):
                    # 取最内层的data键
                    result[year] = inner_data.get("data", {})
        return result

    def load_multi_stock_for_table(
        self,
        stock_codes: List[str],
        year: int,
        statement_type: str,
    ) -> Dict[Tuple[str, str], Dict[str, float]]:
        """
        加载多股票同年数据用于表格导出

        Args:
            stock_codes: 股票代码列表
            year: 报告年份
            statement_type: 报表类型

        Returns:
            {(股票代码, 股票代码): {科目名: 值}}
        """
        result = {}
        for stock_code in stock_codes:
            file_path = self._generate_path(stock_code, year, statement_type)
            data = self.load(file_path)
            if data:
                inner_data = data.get("data", {})
                if inner_data.get("found"):
                    result[(stock_code, stock_code)] = inner_data.get("data", {})
        return result
