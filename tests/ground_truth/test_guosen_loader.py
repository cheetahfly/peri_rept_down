import os
import sys
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from astock_fundamentals.sources.guosen import (
    GuosenLoader,
    GuosenAuthError,
    GuosenEmptyDataError,
)


def test_guosen_auth_error_is_exception():
    assert issubclass(GuosenAuthError, Exception)


def test_guosen_empty_data_error_is_exception():
    assert issubclass(GuosenEmptyDataError, Exception)


def test_guosen_load_raises_auth_error_when_no_key(monkeypatch):
    monkeypatch.delenv("GS_API_KEY", raising=False)
    with pytest.raises(GuosenAuthError):
        GuosenLoader()


def test_guosen_load_uses_explicit_api_key():
    loader = GuosenLoader(api_key="explicit-test-key")
    assert loader.api_key == "explicit-test-key"


def test_guosen_load_uses_env_var(monkeypatch):
    monkeypatch.setenv("GS_API_KEY", "env-test-key")
    loader = GuosenLoader()
    assert loader.api_key == "env-test-key"


def test_guosen_load_reads_memory_md(monkeypatch, tmp_path):
    monkeypatch.delenv("GS_API_KEY", raising=False)
    memory_path = tmp_path / "memory.md"
    memory_path.write_text("# Project memory\nGS_API_KEY=memory-test-key\n")
    loader = GuosenLoader(memory_path=str(memory_path))
    assert loader.api_key == "memory-test-key"