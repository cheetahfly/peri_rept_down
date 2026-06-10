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


from scripts.eval_em_lib import stratified_sample


def test_stratified_sample_seed_reproducible():
    """相同 seed 必须产出相同结果。"""
    stock_list = [f"{600000 + i:06d}" for i in range(100)] + \
                 [f"{300000 + i:06d}" for i in range(100)] + \
                 [f"{688000 + i:06d}" for i in range(100)] + \
                 [f"{i:06d}" for i in range(1, 101)]
    s1 = stratified_sample(stock_list, per_board=10, seed=42)
    s2 = stratified_sample(stock_list, per_board=10, seed=42)
    assert s1 == s2


def test_stratified_sample_returns_4_boards():
    """返回 4 个板块各 N 只。"""
    stock_list = [f"{600000 + i:06d}" for i in range(50)] + \
                 [f"{300000 + i:06d}" for i in range(50)] + \
                 [f"{688000 + i:06d}" for i in range(50)] + \
                 [f"{i:06d}" for i in range(1, 51)]
    result = stratified_sample(stock_list, per_board=20, seed=1)
    assert set(result["boards"].keys()) == {"sh_main", "sz_main", "chinext", "star"}
    for board, codes in result["boards"].items():
        assert len(codes) == 20, f"{board} got {len(codes)}, expected 20"


def test_stratified_sample_insufficient_stocks():
    """某板块股票不足时只取该板块全部，但仍返回 4 个 key。"""
    stock_list = ["600000", "600001", "300000"]  # 只有 2 只沪市主板，1 只创业板
    result = stratified_sample(stock_list, per_board=5, seed=1)
    assert len(result["boards"]["sh_main"]) == 2  # 全部取走
    assert len(result["boards"]["chinext"]) == 1
    assert len(result["boards"]["star"]) == 0     # 无股票
    assert len(result["boards"]["sz_main"]) == 0


def test_stratified_sample_includes_all_codes():
    """all_codes 字段汇总 4 个板块的所有股票。"""
    stock_list = [f"{600000 + i:06d}" for i in range(50)] + \
                 [f"{i:06d}" for i in range(1, 51)]
    result = stratified_sample(stock_list, per_board=10, seed=1)
    total = sum(len(v) for v in result["boards"].values())
    assert len(result["all_codes"]) == total