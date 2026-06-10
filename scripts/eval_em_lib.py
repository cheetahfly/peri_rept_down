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


def stratified_sample(
    stock_list: List[str],
    per_board: int = 50,
    seed: int = 42,
) -> Dict:
    """Stratified random sample: per_board stocks from each of 4 boards.

    Args:
        stock_list: full A-share stock codes.
        per_board: how many to sample from each board (default 50).
        seed: random seed for reproducibility.

    Returns:
        {
            "seed": 42,
            "per_board": 50,
            "boards": {"sh_main": [...], "sz_main": [...], "chinext": [...], "star": [...]},
            "all_codes": [所有抽到的代码]
        }
    """
    by_board: Dict[str, List[str]] = {b: [] for b in BOARD_PREFIXES}
    for code in stock_list:
        board = classify_board(code)
        if board in by_board:
            by_board[board].append(code)

    rng = random.Random(seed)
    sampled: Dict[str, List[str]] = {}
    for board, codes in by_board.items():
        rng.shuffle(codes)
        sampled[board] = codes[:per_board]

    all_codes = []
    for codes in sampled.values():
        all_codes.extend(codes)

    return {
        "seed": seed,
        "per_board": per_board,
        "boards": sampled,
        "all_codes": all_codes,
    }