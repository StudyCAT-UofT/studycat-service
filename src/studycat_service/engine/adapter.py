"""
Adapter that wraps the existing UnidimensionalModel / MultidimensionalModel.

Build item pools per concept, initialize the models, apply the last
response (if provided), and ask the model for the next item.
"""
from __future__ import annotations

import uuid

from adaptivetesting.math.estimators import BayesModal, NormalPrior
from adaptivetesting.math.item_selection import maximum_information_criterion
from adaptivetesting.models import ItemPool, TestItem

from ..models.multidimensional import MultidimensionalModel


def _make_test_item(a: float, b: float, c: float) -> TestItem:
    """Create a TestItem in the shape expected by adaptivetesting."""
    t = TestItem()
    t.id = uuid.uuid4()     # ephemeral per-request id; we track mapping outside
    t.a = a
    t.b = b
    t.c = c
    return t


def build_multidim_model(
    concepts: list[str],
    pools_by_concept: dict[str, ItemPool],
    prior_mu: float,
    prior_sigma2: float,
    mastery_thresholds: dict[str, float],
    existing_thetas: dict[str, float] | None = None,
) -> MultidimensionalModel:
    """
    Build a MultidimensionalModel with one UnidimensionalModel per concept.
    """
    model = MultidimensionalModel(student_id=0, test_id=0)  # IDs not used by library

    if existing_thetas is None:
        existing_thetas = {}

    for concept in concepts:
        pool = pools_by_concept.get(concept, ItemPool([]))
        thr = mastery_thresholds.get(concept, 1.0)

        # Use stored theta as the starting point if it exists, otherwise use global default
        concept_mu = existing_thetas.get(concept, prior_mu)

        model.add_model(
            skill=concept,
            mastery_threshold=thr,
            item_pool=pool,
            initial_theta=concept_mu,
            ability_estimator=BayesModal,
            estimator_args={
                "prior": NormalPrior(concept_mu, prior_sigma2),
                "optimization_interval": (-4, 4),
            },
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

def determine_all_mastered(model: MultidimensionalModel):
    """
    Determines if the user has mastered all the modules included in this model.

    Returns:
        True if all modules have been mastered, False otherwise
    """
    return model.determine_model_mastered()
