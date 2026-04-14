"""
Tests for engine/adapter.py - build_multidim_model

Verifies that the factory correctly constructs a MultidimensionalModel with
one UnidimensionalModel per concept, and that each sub-model is initialised
with the prior_mu value as its starting theta estimate.
"""
from __future__ import annotations

from adaptivetesting.models import ItemPool


class TestBuildMultidimModel:
    """
    Unit tests for adapter.build_multidim_model.

    Each test builds a model through the public factory function and inspects
    the resulting MultidimensionalModel structure rather than touching internal
    state directly.
    """

    def _build(self, concepts=("math", "reading"), mu=0.0, sigma2=1.0, threshold=1.5):
        """
        Helper: build a MultidimensionalModel for the given concepts using two
        generic items per pool and uniform mastery thresholds.
        """
        from studycat_service.engine.adapter import _make_test_item, build_multidim_model

        items = [_make_test_item(1.0, 0.0, 0.25), _make_test_item(1.2, 0.5, 0.2)]
        pool  = ItemPool(list(items))
        pools = dict.fromkeys(concepts, pool)
        thresholds = dict.fromkeys(concepts, threshold)
        return build_multidim_model(
            concepts=list(concepts),
            pools_by_concept=pools,
            prior_mu=mu,
            prior_sigma2=sigma2,
            mastery_thresholds=thresholds,
        )

    def test_creates_one_model_per_concept(self):
        """
        Passing three concept names should produce a MultidimensionalModel
        whose .models dict contains exactly those three keys — one
        UnidimensionalModel per concept, no more, no fewer.
        """
        model = self._build(concepts=("math", "reading", "science"))
        assert set(model.models.keys()) == {"math", "reading", "science"}

    def test_initial_theta_equals_prior_mu(self):
        """
        Before any responses are recorded, every sub-model's theta estimate
        should equal the prior_mu supplied to the factory. Here prior_mu=0.5
        is used to confirm the parameter is actually wired through rather
        than silently ignored.
        """
        model = self._build(mu=0.5)
        for uni in model.models.values():
            assert abs(uni.get_theta() - 0.5) < 1e-6

    def test_negative_prior_mu(self):
        """
        prior_mu can be negative (representing a student estimated to be
        below average). Confirms the factory accepts and correctly propagates
        negative values rather than clipping or discarding them.
        """
        model = self._build(mu=-1.0)
        for uni in model.models.values():
            assert abs(uni.get_theta() - (-1.0)) < 1e-6

    def test_single_concept(self):
        """
        A quiz covering only one concept should produce a model with a single
        entry. Also verifies that the concept name is preserved exactly as
        supplied (no mangling or sorting side-effects on a one-element list).
        """
        model = self._build(concepts=("only",))
        assert list(model.models.keys()) == ["only"]
