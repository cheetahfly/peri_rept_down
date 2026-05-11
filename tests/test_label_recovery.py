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


class TestLayer1ReferenceMatching:
    """Tests for y-position based reference matching (Layer 1)."""

    def test_reference_matching_assigns_correct_labels(self):
        """When reference data has rows at same y-position, label should match reference."""
        # Reference BS: "货币资金" at y=229.2 with value 1000000.0
        reference_data = {
            "data": {"货币资金": 1000000.0},
            "page_data": {
                "96": {
                    "rows": [
                        {"row": 0, "values": [1000000.0], "y_position": 229.2, "label": "货币资金"}
                    ]
                }
            },
            "pages": [96],
        }
        # Recovered CF: value at y=229.2 (same y), should match reference label
        recovered_data = {
            "data": {"p161_r1_c0": 285449.0},
            "page_data": {
                "161": {
                    "rows": [
                        {"row": 1, "values": [285449.0], "y_position": 229.2}
                    ]
                }
            },
            "pages": [161],
        }
        result = recover_labels(recovered_data, reference_data, "cash_flow")
        # Should have matched by y-position → label = "货币资金"
        assert result["match_method"] == "reference"
        assert "货币资金" in result["flat_data"]
        assert result["flat_data"]["货币资金"] == 285449.0

    def test_no_reference_falls_back_to_template(self):
        """Without reference data, should use template matching."""
        recovered_data = {
            "data": {"p0_r0_c0": 1000.0},
            "page_data": {"0": {"rows": [{"row": 0, "values": [1000.0], "y_position": 100.0}]}},
            "pages": [0],
        }
        result = recover_labels(recovered_data, reference_data=None, statement_type="cash_flow")
        assert result["match_method"] == "template"

    def test_y_tolerance_15pt(self):
        """Rows with y-distance > 15pt should NOT match."""
        # Reference at y=100.0
        reference_data = {
            "data": {"货币资金": 1000000.0},
            "page_data": {
                "0": {
                    "rows": [
                        {"row": 0, "values": [1000000.0], "y_position": 100.0, "label": "货币资金"}
                    ]
                }
            },
            "pages": [0],
        }
        # Recovered at y=130.0 (30pt apart — exceeds 15pt tolerance)
        recovered_data = {
            "data": {"p1_r0_c0": 285449.0},
            "page_data": {
                "1": {
                    "rows": [
                        {"row": 0, "values": [285449.0], "y_position": 130.0}
                    ]
                }
            },
            "pages": [1],
        }
        result = recover_labels(recovered_data, reference_data, "cash_flow")
        # Should fall back to template since y-distance > 15
        assert result["match_method"] in ("template", "none")

    def test_within_tolerance_matches(self):
        """Rows with y-distance <= 15pt should match."""
        reference_data = {
            "data": {"货币资金": 1000000.0},
            "page_data": {
                "0": {
                    "rows": [
                        {"row": 0, "values": [1000000.0], "y_position": 100.0, "label": "货币资金"}
                    ]
                }
            },
            "pages": [0],
        }
        # y=108.0 — within 15pt of 100.0
        recovered_data = {
            "data": {"p1_r0_c0": 285449.0},
            "page_data": {
                "1": {
                    "rows": [
                        {"row": 0, "values": [285449.0], "y_position": 108.0}
                    ]
                }
            },
            "pages": [1],
        }
        result = recover_labels(recovered_data, reference_data, "cash_flow")
        assert result["match_method"] == "reference"
        assert "货币资金" in result["flat_data"]

    def test_reference_matching_sets_confidence_1_0(self):
        """Reference-matched labels should have confidence = 1.0."""
        reference_data = {
            "data": {"净利润": 5000000.0},
            "page_data": {
                "0": {
                    "rows": [
                        {"row": 5, "values": [5000000.0], "y_position": 300.0, "label": "净利润"}
                    ]
                }
            },
            "pages": [0],
        }
        recovered_data = {
            "data": {"p1_r5_c0": 4800000.0},
            "page_data": {
                "1": {
                    "rows": [
                        {"row": 5, "values": [4800000.0], "y_position": 300.0}
                    ]
                }
            },
            "pages": [1],
        }
        result = recover_labels(recovered_data, reference_data, "income_statement")
        ref_items = [e for e in result["label_map"] if e["confidence"] == 1.0]
        assert len(ref_items) > 0
