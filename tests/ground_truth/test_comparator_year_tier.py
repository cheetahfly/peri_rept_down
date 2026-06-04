import pytest
from astock_fundamentals.ground_truth.comparator import year_tier_tolerance


def test_year_tier_returns_dict_with_three_keys():
    tiers = year_tier_tolerance()
    assert set(tiers.keys()) == {"early", "mid", "recent"}


def test_year_tier_values_increase_toward_recent():
    tiers = year_tier_tolerance()
    assert tiers["early"] > tiers["mid"] >= tiers["recent"]


def test_year_tier_classify_2019_is_mid():
    assert year_tier_tolerance().classify(2019) == "mid"


def test_year_tier_classify_2022_is_recent():
    assert year_tier_tolerance().classify(2022) == "recent"


def test_year_tier_classify_2003_is_early():
    assert year_tier_tolerance().classify(2003) == "early"


def test_get_tolerance_for_year_returns_float():
    from astock_fundamentals.ground_truth.comparator import get_tolerance_for_year
    assert isinstance(get_tolerance_for_year(2019), float)
    assert 0 < get_tolerance_for_year(2019) < 1
