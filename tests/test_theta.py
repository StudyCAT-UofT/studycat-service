"""
Tests for theta growth

Theta growth tests confirm that the Bayesian MAP estimator moves in the
correct direction after correct and incorrect responses.
"""
from __future__ import annotations

from adaptivetesting.models import ItemPool


class TestThetaGrowth:
    """
    Theta (ability estimate) should rise after correct responses and fall
    after incorrect ones.

    All tests use the pool_items fixture to retrieve the exact TestItem
    references held by the pool. This is required because ItemPool.delete_item
    uses list.index() (identity comparison), so passing an externally
    constructed item with identical parameters would raise a ValueError.
    """

    def _fresh_model(self, pool_items, mu=0.0, sigma2=1.0, threshold=2.0):
        """
        Build a single-concept model with three items at b=-1, 0, +1 and
        return it together with the live pool references.
        """
        from studycat_service.engine.adapter import _make_test_item, build_multidim_model

        items = [
            _make_test_item(a=1.0, b=-1.0, c=0.2),
            _make_test_item(a=1.0, b=0.0,  c=0.2),
            _make_test_item(a=1.0, b=1.0,  c=0.2),
        ]
        model = build_multidim_model(
            concepts=["math"],
            pools_by_concept={"math": ItemPool(items)},
            prior_mu=mu,
            prior_sigma2=sigma2,
            mastery_thresholds={"math": threshold},
        )
        # Retrieve references that actually live inside the pool.
        # ItemPool.delete_item uses list.index() (identity check), so we must
        # use these objects, not the originals passed into ItemPool().
        return model, pool_items(model.models["math"])

    def test_correct_response_increases_theta(self, pool_items):
        """
        After a single correct response, theta should be strictly greater than
        its starting value. Uses the easiest item (b=-1) against a student
        starting at mu=0 so the likelihood update clearly favours a higher
        ability. Asserts theta_after > theta_before with a descriptive failure
        message showing the actual values.
        """
        model, items = self._fresh_model(pool_items)
        theta_before = model.models["math"].get_theta()
        model.models["math"].record_response(1, items[0])
        theta_after = model.models["math"].get_theta()
        assert theta_after > theta_before, (
            f"Expected theta to increase after correct response, "
            f"got {theta_before} -> {theta_after}"
        )

    def test_incorrect_response_decreases_or_stays_theta(self, pool_items):
        """
        After a single incorrect response on a hard item (b=+1), theta should
        be less than or equal to its starting value. Starts with mu=1.0 so
        there is enough room above the prior mean to observe a meaningful
        downward movement. The test accepts 'stays equal' because the prior
        can dampen the update when the starting theta is already high.
        """
        model, items = self._fresh_model(pool_items, mu=1.0)
        theta_before = model.models["math"].get_theta()
        model.models["math"].record_response(0, items[2])  # hard item, wrong
        theta_after = model.models["math"].get_theta()
        assert theta_after <= theta_before, (
            f"Expected theta to decrease or stay after incorrect response, "
            f"got {theta_before} -> {theta_after}"
        )

    def test_multiple_correct_responses_converge_upward(self, pool_items):
        """
        Answering all three items correctly in sequence should move theta
        strictly above its initial value. Tests the cumulative update path
        — each call to record_response removes the item from the pool and
        re-estimates theta from the growing response history.
        """
        model, items = self._fresh_model(pool_items)
        theta_start = model.models["math"].get_theta()
        for item in items:
            model.models["math"].record_response(1, item)
        assert model.models["math"].get_theta() > theta_start

    def test_multiple_incorrect_responses_converge_downward(self, pool_items):
        """
        Answering all three items incorrectly in sequence should move theta
        strictly below its initial value.
        """
        model, items = self._fresh_model(pool_items, mu=0.5)
        theta_start = model.models["math"].get_theta()
        for item in items:
            model.models["math"].record_response(0, item)
        assert model.models["math"].get_theta() < theta_start
