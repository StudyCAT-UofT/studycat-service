"""
Core orchestration that binds DB state <-> engine adapter.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from prisma.enums import OptionLabel
from db import repo
from config import settings
from engine.adapter import _make_test_item, build_multidim_model, choose_next_item
from adaptivetesting.models import ItemPool, TestItem
from models.multidimensional import MultidimensionalModel


@dataclass
class PublicItem:
    item_id: str
    skill: str
    stem: str
    options: List[str]


def _label_from_index(idx: int) -> OptionLabel:
    # TODO: Don't restrict to A..D.
    mapping = [OptionLabel.A, OptionLabel.B, OptionLabel.C, OptionLabel.D]
    return mapping[idx]


def _index_from_label(label: OptionLabel) -> int:
    # TODO: Don't restrict to A..D.
    return {"A": 0, "B": 1, "C": 2, "D": 3}[label.name]


def _build_item_pools(items) -> Tuple[List[str], Dict[str, ItemPool], Dict[TestItem, str], Dict[TestItem, str]]:
    """
    Create ItemPools per concept and maintain reverse maps:
    - testitem_to_itemid: map TestItem -> DB Item.id
    - testitem_to_skill:  map TestItem -> concept/module
    """
    by_concept: Dict[str, List[TestItem]] = {}
    testitem_to_itemid: Dict[TestItem, str] = {}
    testitem_to_skill: Dict[TestItem, str] = {}

    for it in items:
        module_id = it.moduleId
        # Skip inactive or untagged items
        if not it.active or not module_id:
            continue
        # Guard: ensure we have IRT params (ASSUMPTION: non-null a/b/c)
        if it.irtA is None or it.irtB is None or it.irtC is None:
            continue

        ti = _make_test_item(a=float(it.irtA), b=float(it.irtB), c=float(it.irtC))
        by_concept.setdefault(module_id, []).append(ti)
        testitem_to_itemid[ti] = it.id
        testitem_to_skill[ti] = module_id

    concepts = sorted(by_concept.keys())
    pools = {c: ItemPool(lst) for c, lst in by_concept.items()}
    return concepts, pools, testitem_to_itemid, testitem_to_skill


def _public_item_payload(db_item) -> PublicItem:
    # Order options by label A..D
    options = sorted(db_item.options, key=lambda o: o.label if isinstance(o.label, str) else o.label.name)
    return PublicItem(
        item_id=db_item.id,
        skill=db_item.moduleId,
        stem=db_item.stem,
        options=[opt.text for opt in options],
    )


def _snapshot_payload(theta: Dict[str, float], mastery: Dict[str, bool]) -> str:
    """
    Persisted on Response.engineMasterySnapshot (JSON).
    Store mastery values as float (0.0-1.0) to match existing data format.
    Returns JSON string for Prisma compatibility.
    """
    import json
    # Convert boolean mastery to float values to match existing data format
    snapshot = {skill: float(theta[skill]) for skill in mastery.keys()}
    return json.dumps(snapshot)


def _find_test_item_by_irt_params(model: 'MultidimensionalModel', a: float, b: float, c: float) -> Optional['TestItem']:
    """Find a TestItem in the model's pools that matches the given IRT parameters."""
    for skill, uni_model in model.models.items():
        for test_item in uni_model.adaptive_test.item_pool.test_items:
            if (abs(test_item.a - a) < 0.001 and 
                abs(test_item.b - b) < 0.001 and 
                abs(test_item.c - c) < 0.001):
                return test_item
    return None


# ---- Orchestration -----------------------------------------------------------

async def init_attempt(attempt_id: str, modules: Optional[List[str]], prior_mu: Optional[float], prior_sigma2: Optional[float]) -> Tuple[Dict[str, float], Optional[PublicItem]]:
    attempt = await repo.get_attempt(attempt_id)
    if not attempt:
        raise ValueError("Unknown attempt_id")

    items = await repo.list_eligible_items_for_quiz(attempt.quizId)
    if not items:
        # Nothing to ask
        return {}, None

    # Build pools and model
    all_concepts, pools, ti2id, ti2skill = _build_item_pools(items)

    # Scope modules if provided; else use all_concepts from pool
    effective_concepts = modules or all_concepts

    # Load existing theta values from database
    existing_thetas = await repo.get_thetas_for_enrollment(attempt.enrollmentId, effective_concepts)

    # Mastery thresholds (uniform default unless provided)
    thr = {c: settings.mastery_thresholds.get(c, settings.default_mastery_threshold) for c in effective_concepts}

    model = build_multidim_model(
        concepts=effective_concepts,
        pools_by_concept=pools,
        prior_mu=prior_mu if prior_mu is not None else settings.prior_mu,
        prior_sigma2=prior_sigma2 if prior_sigma2 is not None else settings.prior_sigma2,
        mastery_thresholds=thr,
    )

    # Initialize model with existing theta values if available
    for concept in effective_concepts:
        if concept in existing_thetas:
            # Set the theta value in the model
            model.models[concept].set_theta(existing_thetas[concept])

    # Choose first item
    next_item, chosen_skill = choose_next_item(model)
    if not next_item:
        return {}, None

    # Initial thetas (no responses yet)
    theta = {skill: uni.get_theta() for skill, uni in model.models.items()}

    # Return a public payload based on DB item object
    # Find DB item by matching IRT parameters since TestItem objects may not be identical
    public = None
    if next_item:
        # Find the matching DB item by IRT parameters
        for item in items:
            if (item.irtA is not None and item.irtB is not None and item.irtC is not None and
                abs(float(item.irtA) - next_item.a) < 0.001 and
                abs(float(item.irtB) - next_item.b) < 0.001 and
                abs(float(item.irtC) - next_item.c) < 0.001):
                public = _public_item_payload(item)
                break

    return theta, public


async def step_attempt(
    attempt_id: str,
    response_id: str,
    item_id: Optional[str] = None,
    answer_index: Optional[int] = None
) -> Tuple[Dict[str, float], Dict[str, bool], Optional[PublicItem], bool]:
    """
    Process a response and return the next item.
    
    Args:
        attempt_id: Unique identifier for the attempt
        response_id: ID of the Response record created by Core Backend
        item_id: Fallback item ID if Response lookup fails
        answer_index: Fallback answer index if Response lookup fails
    
    Returns:
        Tuple of (theta values, mastery values, next item, is_finished)
    """
    attempt = await repo.get_attempt(attempt_id)
    if not attempt:
        raise ValueError("Unknown attempt_id")

    # Pull scope items
    items = await repo.list_eligible_items_for_quiz(attempt.quizId)
    if not items:
        # No items left in scope
        return {}, {}, None, True

    # Build pools/model
    concepts, pools, ti2id, ti2skill = _build_item_pools(items)
    thr = {c: settings.mastery_thresholds.get(c, settings.default_mastery_threshold) for c in concepts}
    model = build_multidim_model(
        concepts=concepts,
        pools_by_concept=pools,
        prior_mu=settings.prior_mu,
        prior_sigma2=settings.prior_sigma2,
        mastery_thresholds=thr,
    )

    # Load all previous responses for this attempt and replay them
    all_responses = await repo.list_responses(attempt_id)
    for prev_response in all_responses:
        # Skip the current response (we'll process it separately)
        if prev_response.id == response_id:
            continue
            
        # Replay previous response
        is_correct = bool(prev_response.isCorrect)
        skill = prev_response.item.moduleId
        prev_ti = _find_test_item_by_irt_params(
            model, 
            float(prev_response.item.irtA), 
            float(prev_response.item.irtB), 
            float(prev_response.item.irtC)
        )
        if prev_ti:
            model.models[skill].record_response(1 if is_correct else 0, prev_ti)

    # Fetch the Response record by response_id
    response = await repo.get_response_by_id(response_id)
    used_response_id: Optional[str] = None
    
    if response:
        used_response_id = response.id
        # DB has truth for correctness
        is_correct = bool(response.isCorrect)
        # Identify skill by the item's moduleId
        skill = response.item.moduleId
        # Find the TestItem in the model that matches this response
        prev_ti = _find_test_item_by_irt_params(
            model, 
            float(response.item.irtA), 
            float(response.item.irtB), 
            float(response.item.irtC)
        )
        if prev_ti:
            # Record the response into the correct skill model
            model.models[skill].record_response(1 if is_correct else 0, prev_ti)
    elif item_id is not None and answer_index is not None:
        # Fallback: compute correctness without DB response
        db_item = await repo.get_item_by_id(item_id)
        if not db_item:
            raise ValueError("Unknown item_id")
        # Determine correct label from options
        correct_opt = next((o for o in db_item.options if o.isCorrect), None)
        if not correct_opt:
            raise ValueError("Item has no correct option in DB")
        is_correct = (_label_from_index(answer_index) == correct_opt.label)
        skill = db_item.moduleId
        # Find the TestItem in the model that matches this item
        prev_ti = _find_test_item_by_irt_params(
            model, 
            float(db_item.irtA), 
            float(db_item.irtB), 
            float(db_item.irtC)
        )
        if prev_ti:
            model.models[skill].record_response(1 if is_correct else 0, prev_ti)
    else:
        # No response to apply (first step after init)
        pass

    # Compute current theta and naive mastery
    theta = {s: m.get_theta() for s, m in model.models.items()}
    mastery = {s: (theta[s] >= thr[s]) for s in theta}

    # Persist theta values to database
    for module_id, theta_value in theta.items():
        await repo.upsert_theta(attempt.enrollmentId, module_id, theta_value)

    # Pick next item
    next_item, chosen_skill = choose_next_item(model)

    # FINISH if no next item
    is_finished = next_item is None

    # Persist snapshot onto the *latest* response if we found one
    if used_response_id:
        await repo.attach_engine_snapshot_to_response(
            used_response_id,
            snapshot=_snapshot_payload(theta=theta, mastery=mastery)
        )

    # Build public payload
    next_public: Optional[PublicItem] = None
    if next_item:
        # Find the matching DB item by IRT parameters since TestItem objects may not be identical
        for item in items:
            if (item.irtA is not None and item.irtB is not None and item.irtC is not None and
                abs(float(item.irtA) - next_item.a) < 0.001 and
                abs(float(item.irtB) - next_item.b) < 0.001 and
                abs(float(item.irtC) - next_item.c) < 0.001):
                next_public = _public_item_payload(item)
                break

    return theta, mastery, next_public, is_finished
