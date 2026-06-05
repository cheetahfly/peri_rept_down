# -*- coding: utf-8 -*-
"""
Guosen (国信证券) financial data source.

Adapter for the gs-stock-financial-query skill. Provides a SinaLoader-compatible
interface (read_statement, get_annual) for use in clean_sina_pipeline.py
and baseline_2019_2022.py.

Requires GS_API_KEY env var or api_key parameter at construction.
"""
from astock_fundamentals.sources.guosen.guosen_loader import (
    GuosenLoader,
    GuosenAuthError,
    GuosenEmptyDataError,
)

__all__ = ["GuosenLoader", "GuosenAuthError", "GuosenEmptyDataError"]