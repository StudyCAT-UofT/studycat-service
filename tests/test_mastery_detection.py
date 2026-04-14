"""
Tests for mastery detection (engine/adapter.py)

Mastery tests confirm that determine_all_mastered correctly reflects whether
every skill's theta has crossed its configured threshold.
"""
from __future__ import annotations

from adaptivetesting.models import ItemPool


class TestMasteryDetection:
    """
    determine_all_mastered wraps MultidimensionalModel.determine_model_mastered,
    which returns True only when every sub-model reports mastery_reached.
    A sub-model reaches mastery when its current theta >= its mastery_threshold.
    """

    def test_not_mastered_below_threshold(self):
        """
        A freshly built model with a very high threshold (3.0) and no responses
        recorded should not report mastery. The starting theta equals prior_mu=0,
        which is well below 3.0. Confirms the base case: mastery is not granted
        by default, only after sufficient correct responses.
        """
        from studycat_service.engine.adapter import (
            _make_test_item,
            build_multidim_model,
            determine_all_mastered,
        )

        item = _make_test_item(1.0, 0.0, 0.25)
        model = build_multidim_model(
            concepts=["math"],
            pools_by_concept={"math": ItemPool([item])},
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 3.0},
        )
        assert not determine_all_mastered(model)

    def test_mastery_reached_when_theta_exceeds_threshold(self, pool_items):
        """
        After answering four high-discrimination (a=2) items correctly, theta
        should rise above the low threshold of 0.5, causing mastery to be
        flagged. Uses pool_items to retrieve the live references required by
        ItemPool.delete_item (identity-based lookup). Includes the final theta
        value in the failure message to make debugging straightforward if the
        threshold arithmetic changes.
        """
        from studycat_service.engine.adapter import (
            _make_test_item,
            build_multidim_model,
            determine_all_mastered,
        )

        items = [_make_test_item(2.0, float(b), 0.0) for b in range(-3, 1)]
        model = build_multidim_model(
            concepts=["math"],
            pools_by_concept={"math": ItemPool(list(items))},
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 0.5},
        )
        for pooled_item in pool_items(model.models["math"]):
            model.models["math"].record_response(1, pooled_item)

        assert determine_all_mastered(model), (
            f"Expected mastery after all correct, theta={model.models['math'].get_theta()}"
        )

    def test_all_mastered_requires_every_skill(self, pool_items):
        """
        determine_all_mastered must return False when even one skill has not
        reached its threshold. Sets up math and reading both with threshold=0.5,
        masters only math by answering its items correctly, and leaves reading
        untouched. Asserts the result is still False, confirming the AND
        semantics (all skills must be mastered, not just any one).
        """
        from studycat_service.engine.adapter import (
            _make_test_item,
            build_multidim_model,
            determine_all_mastered,
        )

        items = [_make_test_item(2.0, float(b), 0.0) for b in range(-3, 1)]
        model = build_multidim_model(
            concepts=["math", "reading"],
            pools_by_concept={
                "math":    ItemPool(list(items)),
                "reading": ItemPool(list(items)),
            },
            prior_mu=0.0,
            prior_sigma2=1.0,
            mastery_thresholds={"math": 0.5, "reading": 0.5},
        )
        for pooled_item in pool_items(model.models["math"]):
            model.models["math"].record_response(1, pooled_item)

        assert not determine_all_mastered(model), (
            "Should not be all-mastered when reading is still below threshold"
        )
