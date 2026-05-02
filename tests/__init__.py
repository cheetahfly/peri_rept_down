# -*- coding: utf-8 -*-
"""
测试数据集

结构:
- tests/
  - __init__.py
  - fixtures.py      # 测试用例定义
  - test_runner.py   # 完整测试运行器
  - quick_verify.py  # 快速验证脚本
  - results/         # 测试结果存放

用法:
    # 快速验证
    python tests/quick_verify.py

    # 运行完整测试
    python tests/test_runner.py --report

    # 只测试指定股票
    python tests/test_runner.py --stock 000001

    # 只测试指定用例
    python tests/test_runner.py --fixture 000001_2024_bs
"""

from tests.fixtures import get_all_fixtures, get_fixture_by_id, get_fixtures_by_stock

__all__ = [
    "get_all_fixtures",
    "get_fixture_by_id",
    "get_fixtures_by_stock",
]
