# -*- coding: utf-8 -*-
"""
多数据源流程编排 - 统一调度RDS、PDF、API三种数据源
"""
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from astock_fundamentals.core.models import (
    StockFinancials, FinancialStatement, FinancialItem,
    STATEMENT_TYPES
)


@dataclass
class DataSourceResult:
    """单个数据源的提取结果"""
    source_name: str
    statements: Dict[str, FinancialStatement]
    success: bool
    error: Optional[str] = None


class ExtractionPipeline:
    """
    多数据源提取管道。

    按优先级依次尝试各数据源，支持结果合并和校验。
    典型流程:
        1. 尝试 RDS 获取高精度数据
        2. 补充 PDF 提取的缺失科目
        3. 如有 API 数据则交叉验证
    """

    def __init__(self):
        self._providers: List[Callable] = []

    def register_provider(self, provider_fn: Callable):
        """注册数据提供者"""
        self._providers.append(provider_fn)

    def extract(self, stock_code: str, year: int,
                report_type: str = "annual") -> StockFinancials:
        """按注册顺序依次提取，后注册的补充/覆盖先注册的"""
        result = StockFinancials(
            stock_code=stock_code,
            year=year,
            report_type=report_type,
        )

        for provider_fn in self._providers:
            try:
                data = provider_fn(stock_code, year, report_type)
                if data:
                    self._merge(result, data)
            except Exception as e:
                import logging
                logging.warning(f"Provider {provider_fn.__name__} failed: {e}")

        return result

    def _merge(self, target: StockFinancials, source: StockFinancials):
        """合并数据：source 补充 target 的缺失项"""
        for st in STATEMENT_TYPES:
            src_stmt = getattr(source, st, None)
            if not src_stmt or not src_stmt.items:
                continue
            tgt_stmt = getattr(target, st, None)
            if tgt_stmt is None:
                setattr(target, st, src_stmt)
                continue
            # 补充缺失科目
            for k, v in src_stmt.items.items():
                if k not in tgt_stmt.items:
                    tgt_stmt.items[k] = v
                    if src_stmt.item_codes:
                        tgt_stmt.item_codes[k] = src_stmt.item_codes.get(k, "")
