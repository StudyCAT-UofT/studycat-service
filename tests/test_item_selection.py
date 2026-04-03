"""
Tests for IRT item selection in engine/adapter.py

Item selection tests confirm that the maximum information criterion
picks the item that provides the most information given the student's
current theta estimate.
"""

from __future__ import annotations

import pytest
from adaptivetesting.models import ItemPool


class TestItemSelection:
    """
    choose_next_item delegates to MultidimensionalModel.get_next_item, which
    uses the maximum information criterion (MIC) to select the item that
    provides the most Fisher information at the student's current theta.

    For the 3PL model, information peaks when item difficulty b ≈ theta, and
    is higher for items with greater discrimination a. These tests verify both
    properties directly using controlled item sets.
    """

    def test_selects_item_near_current_theta(self):
        """
        Given three items at b=-2, 0, +2 and a student starting at theta=0,
        the MIC should select the item at b=0 because its information function
        peaks exactly at the student's current ability estimate. Asserts the
        chosen item's b-parameter is within 0.01 of 0.0 and that the correct
        skill label is returned alongside it.
        """
        from engine.adapter import _make_test_item, build_multidim_model, choose_next_item

        items = [
            _make_test_item(a=1.0, b=-2.0, c=0.0),
            _make_test_item(a=1.0, b=0.0,  c=0.0),
            _make_test_item(a=1.0, b=2.0,  c=0.0),
        ]
        model = build_multidim_model(
            concepts=["math"],
            pools_by_concept={"math": ItemPool(list(items))},
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 2.0},
        )
        next_item, skill = choose_next_item(model)
        assert skill == "math"
        assert next_item is not None
        assert abs(next_item.b - 0.0) < 0.01, (
            f"Expected item with b≈0 to be selected, got b={next_item.b}"
        )

    def test_high_discrimination_preferred_over_low(self):
        """
        Two items at the same difficulty (b=0) but discrimination a=0.5 vs
        a=2.0. The item with a=2.0 carries four times more information at any
        given theta, so the MIC must select it first. Asserts the returned
        item's a-parameter equals 2.0 using pytest.approx to handle
        floating-point comparison safely.
        """
        from engine.adapter import _make_test_item, build_multidim_model, choose_next_item

        low_a  = _make_test_item(a=0.5, b=0.0, c=0.0)
        high_a = _make_test_item(a=2.0, b=0.0, c=0.0)
        model = build_multidim_model(
            concepts=["math"],
            pools_by_concept={"math": ItemPool([low_a, high_a])},
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 2.0},
        )
        next_item, _ = choose_next_item(model)
        assert next_item is not None
        assert next_item.a == pytest.approx(2.0), (
            f"Expected high-discrimination item to be selected, got a={next_item.a}"
        )

    def test_returns_none_when_pool_exhausted(self, pool_items):
        """
        Once every item in the pool has been answered, choose_next_item should
        return (None, None) rather than raising an exception. Builds a
        single-item pool, consumes it via record_response (using the
        pool-internal reference to satisfy identity checks), then asserts both
        return values are None.
        """
        from engine.adapter import _make_test_item, build_multidim_model, choose_next_item

        item = _make_test_item(1.0, 0.0, 0.25)
        model = build_multidim_model(
            concepts=["math"],
            pools_by_concept={"math": ItemPool([item])},
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 2.0},
        )
        [pooled_item] = pool_items(model.models["math"])
        model.models["math"].record_response(1, pooled_item)
        next_item, skill = choose_next_item(model)
        assert next_item is None
        assert skill is None

    def test_multidim_routes_to_weakest_skill(self, pool_items):
        """
        The MultidimensionalModel sorts sub-models by theta and selects from
        the one with the lowest current estimate (weakest-first strategy).

        Sets up math and reading each with one item, then records a correct
        response for reading to boost its theta above math's. The next call
        to choose_next_item should therefore select from math. Verifies the
        returned skill label is 'math'.
        """
        from engine.adapter import _make_test_item, build_multidim_model, choose_next_item

        item_math    = _make_test_item(1.0, 0.0, 0.2)
        item_reading = _make_test_item(1.0, 0.0, 0.2)
        model = build_multidim_model(
            concepts=["math", "reading"],
            pools_by_concept={
                "math":    ItemPool([item_math]),
                "reading": ItemPool([item_reading]),
            },
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 2.0, "reading": 2.0},
        )
        [pooled_reading] = pool_items(model.models["reading"])
        model.models["reading"].record_response(1, pooled_reading)

        _, chosen_skill = choose_next_item(model)
        assert chosen_skill == "math"
