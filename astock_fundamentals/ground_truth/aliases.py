# -*- coding: utf-8 -*-
"""
Alias loading and management for financial item name mappings.

Provides access to the hierarchical alias system loaded from aliases.yaml
via astock_fundamentals.core.extraction_config.
"""
from astock_fundamentals.core.extraction_config import get_aliases

__all__ = ["get_aliases"]
