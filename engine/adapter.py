"""
Adapter that wraps the existing UnidimensionalModel / MultidimensionalModel.

NOTE: To be checked.

Build item pools per concept, initialize the models, apply the last
response (if provided), and ask the model for the next item.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import uuid

from adaptivetesting.models import TestItem, ItemPool
from adaptivetesting.math.estimators import BayesModal, NormalPrior
from adaptivetesting.math.item_selection import maximum_information_criterion

# Import your wrappers
from models.unidimensional import UnidimensionalModel
from models.multidimensional import MultidimensionalModel


def _make_test_item(a: float, b: float, c: float) -> TestItem:
    """Create a TestItem in the shape expected by adaptivetesting."""
    t = TestItem()
    t.id = uuid.uuid4()     # ephemeral per-request id; we track mapping outside
    t.a = a
    t.b = b
    t.c = c
    return t


def build_multidim_model(
    concepts: List[str],
    pools_by_concept: Dict[str, ItemPool],
    prior_mu: float,
    prior_sigma2: float,
    mastery_thresholds: Dict[str, float],
) -> MultidimensionalModel:
    """
    Build a MultidimensionalModel with one UnidimensionalModel per concept.

    NOTE:
    - We keep the ability estimator as BayesModal with NormalPrior(prior_mu, prior_sigma2).
    - Selection strategy is maximum_information_criterion by default.
    """
    model = MultidimensionalModel(student_id=0, test_id=0)  # IDs not used by library

    for concept in concepts:
        pool = pools_by_concept.get(concept, ItemPool([]))
        thr = mastery_thresholds.get(concept, 1.0)
        model.add_model(
            skill=concept,
            mastery_threshold=thr,
            item_pool=pool,
            initial_theta=prior_mu,
            ability_estimator=BayesModal,
            estimator_args={"prior": NormalPrior(prior_mu, prior_sigma2), "optimization_interval": (-4, 4)},
            item_selector=maximum_information_criterion,
            item_selector_args={}
        )
    return model


def choose_next_item(model: MultidimensionalModel):
    """
    Delegate to your MultidimensionalModel to choose next item.

    Returns:
        (next_item: TestItem | None, chosen_skill: str | None)
    """
    next_item = model.get_next_item()
    if next_item is None:
        return None, None

    # Identify which skill's pool contained the selected item
    chosen_skill = None
    for skill, uni in model.models.items():
        if next_item in uni.adaptive_test.item_pool.test_items:
            chosen_skill = skill
            break
    return next_item, chosen_skill
