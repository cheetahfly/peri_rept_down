# -*- coding: utf-8 -*-
"""Unit tests for financial stock identification in dual_channel_cf_download."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from dual_channel_cf_download import is_financial, FINANCIAL_CODES  # noqa: E402


def test_600036_is_financial():
    assert is_financial("600036") is True  # 招商银行


def test_601318_is_financial():
    assert is_financial("601318") is True  # 中国平安


def test_600030_is_financial():
    assert is_financial("600030") is True  # 中信证券


def test_600519_not_financial():
    assert is_financial("600519") is False  # 贵州茅台


def test_300750_not_financial():
    assert is_financial("300750") is False  # 宁德时代


def test_financial_codes_loaded():
    assert len(FINANCIAL_CODES) >= 20, f"expected ≥20 codes, got {len(FINANCIAL_CODES)}"


def test_financial_codes_contains_major_banks():
    expected_banks = {"600036", "601398", "601288", "601988", "601939"}  # 招商/工/农/中/建
    missing = expected_banks - FINANCIAL_CODES
    assert not missing, f"missing major banks: {missing}"
