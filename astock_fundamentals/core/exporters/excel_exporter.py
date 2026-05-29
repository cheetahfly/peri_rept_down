# -*- coding: utf-8 -*-
"""
Excel导出器
"""
import pandas as pd
from .base import BaseExporter


class ExcelExporter(BaseExporter):
    """Excel格式导出器 (.xlsx)"""

    def export(self, df: pd.DataFrame, file_path: str, **kwargs) -> bool:
        """
        导出DataFrame为Excel文件

        Args:
            df: 要导出的DataFrame
            file_path: 文件路径
            **kwargs: sheet_name等参数

        Returns:
            bool: 导出是否成功
        """
        sheet_name = kwargs.get("sheet_name", "Sheet1")
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            self._auto_width(writer, sheet_name, df)
        return True

    @property
    def extension(self) -> str:
        return ".xlsx"

    @staticmethod
    def _auto_width(writer, sheet_name: str, df: pd.DataFrame):
        """Auto-adjust column widths based on content."""
        from openpyxl.utils import get_column_letter
        ws = writer.sheets[sheet_name]
        for i, col in enumerate(df.columns, 1):
            max_len = max(
                df[col].astype(str).map(len).max() if len(df) else 0,
                len(str(col)),
            )
            ws.column_dimensions[get_column_letter(i)].width = min(max_len + 3, 60)
