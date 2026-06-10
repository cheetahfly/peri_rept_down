# -*- coding: utf-8 -*-
"""
Shared library for EM channel evaluation.
"""

import json
import os
import random
import re
import time
import warnings
from typing import Dict, List, Optional, Tuple

import pandas as pd

warnings.filterwarnings("ignore")

# ----- 板块代码前缀映射 -----
BOARD_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "sh_main": ("600", "601", "603", "605"),  # 沪市主板
    "sz_main": ("000", "001", "002"),          # 深市主板（排除 003/300/301）
    "chinext": ("300", "301"),                 # 创业板
    "star":    ("688", "689"),                 # 科创板
}


def classify_board(stock_code: str) -> str:
    """Classify a stock code to one of 4 boards.

    Returns one of: sh_main, sz_main, chinext, star, unknown.
    """
    code = str(stock_code).zfill(6)
    for board, prefixes in BOARD_PREFIXES.items():
        for prefix in prefixes:
            if code.startswith(prefix):
                return board
    return "unknown"