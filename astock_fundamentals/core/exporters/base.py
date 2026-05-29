# -*- coding: utf-8 -*-
"""
导出器基类
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseExporter(ABC):
    """导出器基类"""

    @abstractmethod
    def export(self, df: pd.DataFrame, file_path: str, **kwargs) -> bool:
        """
        导出DataFrame到文件

        Args:
            df: 要导出的DataFrame
            file_path: 文件路径
            **kwargs: 其他参数

        Returns:
            bool: 导出是否成功
        """
        pass

    @property
    @abstractmethod
    def extension(self) -> str:
        """文件扩展名"""
        pass
