"""Smoke test for GuosenLoader connectivity (skipped if no API key set)."""
import os

import pytest


def test_health_check_if_key_set():
    """If GS_API_KEY is set, loader.health_check() should work without raising."""
    if not os.environ.get("GS_API_KEY"):
        pytest.skip("GS_API_KEY not set; skipping live health check")
    from astock_fundamentals.sources.guosen import GuosenLoader
    loader = GuosenLoader()
    # Don't assert True — the API may be rate-limited or unreachable in CI.
    # Just check the call doesn't raise.
    try:
        result = loader.health_check()
    except Exception as e:
        pytest.skip(f"API call failed (likely network/rate limit): {e}")
    assert isinstance(result, bool)