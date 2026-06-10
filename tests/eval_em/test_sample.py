"""Tests for board classifier and sampler."""
import pytest
from scripts.eval_em_lib import classify_board, BOARD_PREFIXES


def test_classify_sh_main():
    assert classify_board("600000") == "sh_main"
    assert classify_board("601000") == "sh_main"
    assert classify_board("603000") == "sh_main"
    assert classify_board("605000") == "sh_main"


def test_classify_sz_main():
    assert classify_board("000001") == "sz_main"
    assert classify_board("001001") == "sz_main"
    assert classify_board("002001") == "sz_main"


def test_classify_chinext():
    assert classify_board("300001") == "chinext"
    assert classify_board("301001") == "chinext"


def test_classify_star():
    assert classify_board("688001") == "star"
    assert classify_board("689001") == "star"


def test_classify_excludes_300_from_sz():
    """创业板 300/301 不应被分到深市主板。"""
    assert classify_board("300750") == "chinext"


def test_classify_unknown():
    """未知前缀归为 unknown。"""
    assert classify_board("999999") == "unknown"
    assert classify_board("830001") == "unknown"  # 北交所


def test_board_prefixes_complete():
    """所有 4 个板块都应在 BOARD_PREFIXES 中。"""
    assert set(BOARD_PREFIXES.keys()) == {"sh_main", "sz_main", "chinext", "star"}