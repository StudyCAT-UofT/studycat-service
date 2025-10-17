"""
Core orchestration that binds DB state <-> engine adapter.

Design choices (explicit):
- Stateless service: we rebuild model state on each call.
- We PERSIST theta/mastery snapshots on each response via Response.engineMasterySnapshot.
- We treat Item.module as "concept" (configurable).

If you later add a dedicated table for ability estimates, update the persistence in one place
(see `_snapshot_payload` and the call in `step_attempt`).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from prisma.enums import OptionLabel
from db import repo
from config import settings
from engine.adapter import _make_test_item, build_multidim_model, choose_next_item
from adaptivetesting.models import ItemPool, TestItem


@dataclass
class PublicItem:
    item_id: str
    skill: str
    stem: str
    options: List[str]


def _label_from_index(idx: int) -> OptionLabel:
    # ASSUMPTION: 0..3 => A..D
    mapping = [OptionLabel.A, OptionLabel.B, OptionLabel.C, OptionLabel.D]
    return mapping[idx]


def _index_from_label(label: OptionLabel) -> int:
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
        concept = getattr(it, settings.concept_field)
        # Skip inactive or untagged items
        if not it.active or not concept:
            continue
        # Guard: ensure we have IRT params (ASSUMPTION: non-null a/b/c)
        if it.irtA is None or it.irtB is None or it.irtC is None:
            continue

        ti = _make_test_item(a=float(it.irtA), b=float(it.irtB), c=float(it.irtC))
        by_concept.setdefault(concept, []).append(ti)
        testitem_to_itemid[ti] = it.id
        testitem_to_skill[ti] = concept

    concepts = sorted(by_concept.keys())
    pools = {c: ItemPool(lst) for c, lst in by_concept.items()}
    return concepts, pools, testitem_to_itemid, testitem_to_skill


def _public_item_payload(db_item) -> PublicItem:
    # Order options by label A..D
    options = sorted(db_item.options, key=lambda o: o.label.name)
    return PublicItem(
        item_id=db_item.id,
        skill=getattr(db_item, settings.concept_field),
        stem=db_item.stem,
        options=[opt.text for opt in options],
    )


def _snapshot_payload(theta: Dict[str, float], mastery: Dict[str, bool]) -> Dict[str, Any]:
    """
    Persisted on Response.engineMasterySnapshot (JSON).
    NOTE: Schema calls it 'mastery snapshot', but we store both theta & mastery to keep it useful.
    If you later add a dedicated ability table, write there instead and keep this as a lightweight copy.
    """
    return {"theta": theta, "mastery": mastery}


# ---- Orchestration -----------------------------------------------------------

async def init_attempt(attempt_id: str, concepts: Optional[List[str]], prior_mu: Optional[float], prior_sigma2: Optional[float]) -> Tuple[Dict[str, float], Optional[PublicItem]]:
    attempt = await repo.get_attempt(attempt_id)
    if not attempt:
        raise ValueError("Unknown attempt_id")

    items = await repo.list_eligible_items_for_quiz(attempt.quizId)
    if not items:
        # Nothing to ask
        return {}, None

    # Build pools and model
    all_concepts, pools, _, _ = _build_item_pools(items)

    # Scope concepts if provided; else use all_concepts from pool
    effective_concepts = concepts or all_concepts

    # Mastery thresholds (uniform default unless provided)
    thr = {c: settings.mastery_thresholds.get(c, settings.default_mastery_threshold) for c in effective_concepts}

    model = build_multidim_model(
        concepts=effective_concepts,
        pools_by_concept=pools,
        prior_mu=prior_mu if prior_mu is not None else settings.prior_mu,
        prior_sigma2=prior_sigma2 if prior_sigma2 is not None else settings.prior_sigma2,
        mastery_thresholds=thr,
    )

    # Choose first item
    next_item, chosen_skill = choose_next_item(model)
    if not next_item:
        return {}, None

    # Initial thetas (no responses yet)
    theta = {skill: uni.get_theta() for skill, uni in model.models.items()}

    # Return a public payload based on DB item object
    # Find DB item by reverse mapping (rebuild mapping for a single item)
    # Simpler: compute public payload directly from DB by id
    # Find the DB id for next_item by scanning testitem_to_itemid built earlier—rebuild minimal map for this one
    # For clarity (and no hidden state), do a direct lookup by best-effort:
    public = None
    # Rebuild mapping by scanning the pool again; small overhead OK for MVP
    _, _, ti2id, _ = _build_item_pools(items)
    db_id = ti2id.get(next_item)
    if db_id:
        db_item = await repo.get_item_by_id(db_id)
        if db_item:
            public = _public_item_payload(db_item)

    return theta, public


async def step_attempt(
    attempt_id: str,
    item_id: Optional[str],
    answer_index: Optional[int]
) -> Tuple[Dict[str, float], Dict[str, bool], Optional[PublicItem], bool]:
    """
    Stateless step:
    - Option A (preferred by you): Core Backend writes Response, we pick up the *latest* response
      without an engine snapshot and augment it.
    - Option B: If item_id + answer_index are provided, compute correctness directly (engine-only).

    We implement both. If both are present, we trust the DB (Option A) but validate.
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

    # Reconstruct minimal state:
    # MVP approach: warm-start from prior and only apply the *latest* response (keeps engine stateless & fast).
    # TODO (optional): If you want exact replay, iterate all historical responses and call record_response for each.
    latest = await repo.get_latest_response_without_snapshot(attempt_id)
    used_response_id: Optional[str] = None
    if latest:
        used_response_id = latest.id
        # DB has truth for correctness
        is_correct = bool(latest.isCorrect)
        # Identify skill by the item's module
        skill = getattr(latest.item, settings.concept_field)
        # Build a minimal TestItem for the latest item
        # ASSUMPTION: latest.item has non-null irtA/B/C
        prev_ti = _make_test_item(float(latest.item.irtA), float(latest.item.irtB), float(latest.item.irtC))
        # Record the response into the correct skill model
        model.models[skill].record_response(1 if is_correct else 0, prev_ti)

    elif item_id is not None and answer_index is not None:
        # Compute correctness without DB response (Option B)
        db_item = await repo.get_item_by_id(item_id)
        if not db_item:
            raise ValueError("Unknown item_id")
        # Determine correct label from options
        correct_opt = next((o for o in db_item.options if o.isCorrect), None)
        if not correct_opt:
            raise ValueError("Item has no correct option in DB")
        is_correct = (_label_from_index(answer_index) == correct_opt.label)
        skill = getattr(db_item, settings.concept_field)
        prev_ti = _make_test_item(float(db_item.irtA), float(db_item.irtB), float(db_item.irtC))
        model.models[skill].record_response(1 if is_correct else 0, prev_ti)
    else:
        # No response to apply (first step after init)
        pass

    # Compute current theta and naive mastery
    theta = {s: m.get_theta() for s, m in model.models.items()}
    mastery = {s: (theta[s] >= thr[s]) for s in theta}

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
        # Map next_item -> DB id via reverse map
        db_id = ti2id.get(next_item)
        if db_id:
            db_item = await repo.get_item_by_id(db_id)
            if db_item:
                next_public = _public_item_payload(db_item)

    return theta, mastery, next_public, is_finished
