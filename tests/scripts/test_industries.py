"""Tests for --industries CLI parameter in clean_sina_pipeline and learn_sina_aliases."""
import os
import sys

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _norm(s):
    """Normalize stock code to 6-digit zero-padded string (YAML may load as int)."""
    return str(s).zfill(6)


def _load_industry_stocks_via_pipeline():
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
    from clean_sina_pipeline import _load_industry_stocks
    return _load_industry_stocks


def test_industry_aliases_yaml_loads():
    with open(os.path.join(PROJECT_ROOT, "rules", "industry_aliases.yaml"), "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert "industries" in doc
    assert "banking" in doc["industries"]
    banking = [_norm(s) for s in doc["industries"]["banking"]["stocks"]]
    assert "000001" in banking


def test_resolve_banking_industry():
    helper = _load_industry_stocks_via_pipeline()
    stocks = [_norm(s) for s in helper(["banking"])]
    for code in ["000001", "600000", "600036", "601398"]:
        assert code in stocks
    assert "600519" not in stocks  # 茅台 not in banking


def test_resolve_multiple_industries_dedup():
    helper = _load_industry_stocks_via_pipeline()
    stocks = [_norm(s) for s in helper(["banking", "insurance"])]
    # 601318 in both, should dedup
    assert stocks.count("601318") == 1


def test_resolve_all_token():
    helper = _load_industry_stocks_via_pipeline()
    stocks = [_norm(s) for s in helper(["all"])]
    assert "000001" in stocks


def test_resolve_unknown_industry_returns_partial():
    helper = _load_industry_stocks_via_pipeline()
    stocks = [_norm(s) for s in helper(["banking", "nonexistent_industry"])]
    assert "000001" in stocks
    assert len(stocks) >= 4


def test_resolve_none_token_returns_empty():
    helper = _load_industry_stocks_via_pipeline()
    stocks = helper(["none"])
    assert stocks == []


def test_pipeline_cli_help_works():
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "clean_sina_pipeline.py"),
         "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--industries" in result.stdout
