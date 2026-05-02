# -*- coding: utf-8 -*-
"""
CSV导出器
"""
import pandas as pd
from .base import BaseExporter


class CsvExporter(BaseExporter):
    """CSV格式导出器"""

    def export(self, df: pd.DataFrame, file_path: str, **kwargs) -> bool:
        """
        导出DataFrame为CSV文件

        Args:
            df: 要导出的DataFrame
            file_path: 文件路径
            **kwargs: encoding等参数

        Returns:
            bool: 导出是否成功
        """
        encoding = kwargs.get('encoding', 'utf-8-sig')
        df.to_csv(file_path, index=False, encoding=encoding)
        return True

    @property
    def extension(self) -> str:
        return '.csv'
