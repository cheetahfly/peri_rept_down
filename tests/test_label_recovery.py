# -*- coding: utf-8 -*-
"""Tests for label recovery module."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.label_recovery import recover_labels


class TestRecoverLabelsBasic:
    """Basic signature and behavior tests."""

    def test_recover_labels_returns_dict(self):
        """recover_labels returns a dict with flat_data, label_map, confidence, match_method."""
        recovered_data = {
            "data": {
                "p0_r0_c0": 1000000.0,
                "p0_r1_c0": 2000000.0,
                "p0_r2_c0": 3000000.0,
            },
            "page_data": {
                "0": {
                    "rows": [
                        {"row": 0, "values": [1000000.0]},
                        {"row": 1, "values": [2000000.0]},
                        {"row": 2, "values": [3000000.0]},
                    ]
                }
            },
            "pages": [0],
        }
        result = recover_labels(recovered_data, reference_data=None, statement_type="cash_flow")
        assert isinstance(result, dict)
        assert "flat_data" in result
        assert "label_map" in result
        assert "confidence" in result
        assert "match_method" in result

    def test_confidence_is_float_between_0_and_1(self):
        recovered_data = {
            "data": {"p0_r0_c0": 100.0},
            "page_data": {"0": {"rows": [{"row": 0, "values": [100.0]}]}},
            "pages": [0],
        }
        result = recover_labels(recovered_data, None, "cash_flow")
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["match_method"] in ("reference", "template", "none")

    def test_no_reference_uses_template(self):
        """Without reference data, template matching should be used."""
        recovered_data = {
            "data": {"p0_r0_c0": 100.0, "p0_r1_c0": 200.0},
            "page_data": {"0": {"rows": [{"row": 0, "values": [100.0]}, {"row": 1, "values": [200.0]}]}},
            "pages": [0],
        }
        result = recover_labels(recovered_data, reference_data=None, statement_type="cash_flow")
        assert result["match_method"] == "template"
        assert len(result["flat_data"]) == 2

    def test_primary_value_threshold(self):
        """Items with |value| < 1000 should be marked is_primary=False."""
        recovered_data = {
            "data": {"p0_r0_c0": 500.0, "p0_r1_c0": 50000.0},
            "page_data": {"0": {"rows": [{"row": 0, "values": [500.0]}, {"row": 1, "values": [50000.0]}]}},
            "pages": [0],
        }
        result = recover_labels(recovered_data, None, "cash_flow")
        primary_items = [e for e in result["label_map"] if e.get("is_primary")]
        assert len(primary_items) == 1  # only the 50000 one
