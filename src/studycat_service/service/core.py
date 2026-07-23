"""
Core orchestration that binds DB state <-> engine adapter.
"""
from __future__ import annotations

from dataclasses import dataclass

from adaptivetesting.models import ItemPool, TestItem

from ..config import settings
from ..db import repo
from ..engine.adapter import (
    _make_test_item,
    build_multidim_model,
    choose_next_item,
    determine_all_mastered,
)
from ..models.multidimensional import MultidimensionalModel


@dataclass
class PublicItem:
    item_id: str
    skill: str
    stem: str
    options: list[str]
    figure_url: str | None = None
    reference: str | None = None


def _label_from_index(idx: int) -> str:
    # TODO: Don't restrict to A..D.
    mapping = ["A", "B", "C", "D"]
    return mapping[idx]


def _index_from_label(label: str) -> int:
    # TODO: Don't restrict to A..D.
    return {"A": 0, "B": 1, "C": 2, "D": 3}[label]


def _build_item_pools(
        items
    ) -> tuple[list[str], dict[str, ItemPool], dict[TestItem, str], dict[TestItem, str]]:
    """
    Create ItemPools per concept and maintain reverse maps:
    - testitem_to_itemid: map TestItem -> DB Item.id
    - testitem_to_skill:  map TestItem -> concept/module
    """
    by_concept: dict[str, list[TestItem]] = {}
    testitem_to_itemid: dict[TestItem, str] = {}
    testitem_to_skill: dict[TestItem, str] = {}

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
    """
    Convert a Prisma Item record into a PublicItem dataclass for the API layer.

    Sorts the item's options by label (A→B→C→D) before extracting their
    display text, ensuring the client always receives options in a consistent
    order regardless of how the DB returns them. Handles both string labels
    and enum label values via the isinstance guard.

    Args:
        db_item: A Prisma Item record with its options relation included.

    Returns:
        A PublicItem containing the item ID, skill, question stem, ordered
        option texts, and optional figure URL and reference string.
    """
    # Order options by label A..D
    options = sorted(
        db_item.options,
        key=lambda o: o.label if isinstance(o.label, str) else o.label.name,
    )
    return PublicItem(
        item_id=db_item.id,
        skill=db_item.moduleId,
        stem=db_item.stem,
        options=[opt.text for opt in options],
        figure_url=getattr(db_item, "figureUrl", None),
        reference=getattr(db_item, "reference", None),
    )


def _snapshot_payload(theta: dict[str, float], mastery: dict[str, bool]) -> str:
    """
    Build the JSON string persisted on Response.engineMasterySnapshot.
    Stores the current theta (ability estimate) per skill as floats.
    Returns a JSON string for Prisma compatibility.
    """
    import json
    snapshot = {skill: float(theta[skill]) for skill in mastery.keys()}
    return json.dumps(snapshot)


def _find_test_item_by_irt_params(
        model: MultidimensionalModel,
        a: float,
        b: float,
        c: float,
    ) -> TestItem | None:
    """Find a TestItem in the model's pools that matches the given IRT parameters."""
    for _, uni_model in model.models.items():
        for test_item in uni_model.adaptive_test.item_pool.test_items:
            if (abs(test_item.a - a) < 0.001 and
                abs(test_item.b - b) < 0.001 and
                abs(test_item.c - c) < 0.001):
                return test_item
    return None


async def _filter_repeat_correct_items(attempt, items):
    """
    If quiz does NOT allow repeats, remove items that this student
    has previously answered correctly on this quiz.
    """
    quiz = await repo.get_quiz(attempt.quizId)

    # If repeats allowed, no filtering
    if not quiz or getattr(quiz, "repeatCorrectQuestions", True):
        return items

    # Get all previously correct item IDs for this student + quiz
    correct_item_ids = await repo.get_correct_item_ids_for_enrollment_and_quiz(
        enrollment_id=attempt.enrollmentId,
        quiz_id=attempt.quizId,
    )

    if not correct_item_ids:
        return items

    filtered = [it for it in items if it.id not in correct_item_ids]

    # if no unanswered items remain, no items will be returned
    if not filtered:
        return None

    return filtered


# ---- Orchestration -----------------------------------------------------------

async def init_attempt(
    attempt_id: str,
    modules: list[str] | None,
    prior_mu: float | None,
    prior_sigma2: float | None
) -> tuple[dict[str, float], PublicItem | None]:
    """
    Initialise an attempt and select the first item to present to the student.

    Loads the attempt and its eligible items from the DB, builds per-concept
    ItemPools, seeds theta from any prior history stored against the
    enrollment, constructs the MultidimensionalModel, and selects the first
    item using the maximum information criterion.

    If modules is provided, the model is scoped to only those concepts;
    otherwise all concepts present in the item pool are used. prior_mu and
    prior_sigma2 override the configured defaults when provided, allowing
    callers to customise the Bayesian prior per attempt.

    Args:
        attempt_id:   Primary key of the Attempt record to initialise.
        modules:      Optional list of concept/module IDs to restrict the
                      session to. Pass None to include all concepts available
                      in the quiz's item pool.
        prior_mu:     Optional override for the Normal prior mean. Falls back
                      to settings.prior_mu when None.
        prior_sigma2: Optional override for the Normal prior variance. Falls
                      back to settings.prior_sigma2 when None.

    Returns:
        A tuple of:
          - theta:     Dict mapping each concept to its current ability
                       estimate. Will equal the stored value from a prior
                       session if one exists, otherwise prior_mu.
          - next_item: The first PublicItem to show the student, or None if
                       no eligible items exist for this quiz.

    Raises:
        ValueError: If attempt_id does not correspond to a known Attempt record.
    """
    attempt = await repo.get_attempt(attempt_id)
    if not attempt:
        raise ValueError("Unknown attempt_id")

    items = await repo.list_eligible_items_for_quiz(attempt.quizId)
    items = await _filter_repeat_correct_items(attempt, items)
    if not items:
        # Nothing to ask
        return {}, None

    # Build pools and model
    all_concepts, pools, ti2id, ti2skill = _build_item_pools(items)

    # Scope modules if provided; else use all_concepts from pool
    effective_concepts = modules or all_concepts

    # Load existing theta values from database
    existing_thetas = await repo.get_thetas_for_enrollment(
        attempt.enrollmentId,
        effective_concepts,
    )

    # Mastery thresholds
    quiz_modules = await repo.get_quiz_modules(attempt.quizId)
    module_thresholds = {qm.moduleId: qm.masteryThreshold for qm in quiz_modules}

    thr = {c: module_thresholds[c] for c in effective_concepts}

    model = build_multidim_model(
        concepts=effective_concepts,
        pools_by_concept=pools,
        prior_mu=prior_mu if prior_mu is not None else settings.prior_mu,
        prior_sigma2=prior_sigma2 if prior_sigma2 is not None else settings.prior_sigma2,
        mastery_thresholds=thr,
        existing_thetas=existing_thetas,
    )

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
    item_id: str | None = None,
    answer_index: int | None = None
) -> tuple[dict[str, float], dict[str, bool], PublicItem | None, bool, bool]:
    """
    Process a response and return the next item.

    Args:
        attempt_id: Unique identifier for the attempt
        response_id: ID of the Response record created by Core Backend
        item_id: Fallback item ID if Response lookup fails
        answer_index: Fallback answer index if Response lookup fails

    Returns:
        Tuple of (theta values, mastery values, next item, is_finished, all_mastered)
    """
    attempt = await repo.get_attempt(attempt_id)
    if not attempt:
        raise ValueError("Unknown attempt_id")

    # Pull scope items
    items = await repo.list_eligible_items_for_quiz(attempt.quizId)
    items = await _filter_repeat_correct_items(attempt, items)
    if not items:
        # No items left in scope
        return {}, {}, None, True, False

    # Build pools/model
    concepts, pools, ti2id, ti2skill = _build_item_pools(items)

    # Load existing theta values from database
    existing_thetas = await repo.get_thetas_for_enrollment(
        attempt.enrollmentId,
        concepts,
    )

    quiz_modules = await repo.get_quiz_modules(attempt.quizId)
    module_thresholds = {qm.moduleId: qm.masteryThreshold for qm in quiz_modules}
    thr = {c: module_thresholds[c] for c in concepts}
    model = build_multidim_model(
        concepts=concepts,
        pools_by_concept=pools,
        prior_mu=settings.prior_mu,
        prior_sigma2=settings.prior_sigma2,
        mastery_thresholds=thr,
        existing_thetas=existing_thetas,
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
    used_response_id: str | None = None

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
    mastery = {s: (theta[s] > thr[s]) for s in theta}

    # Persist theta values to database
    for module_id, theta_value in theta.items():
        await repo.upsert_theta(attempt.enrollmentId, module_id, theta_value)

    # Persist snapshot onto the *latest* response if we found one
    if used_response_id:
        await repo.attach_engine_snapshot_to_response(
            used_response_id, snapshot=_snapshot_payload(theta=theta, mastery=mastery)
        )

    next_item = None

    if (len(all_responses) < attempt.fixedLengthN):
        # Pick next item
        next_item, chosen_skill = choose_next_item(model)

    # FINISH if no next item
    is_finished = next_item is None

    all_mastered = determine_all_mastered(model)

    # Build public payload
    next_public: PublicItem | None = None
    if next_item:
        # Find the matching DB item by IRT parameters since TestItem objects may not be identical
        for item in items:
            if (item.irtA is not None and item.irtB is not None and item.irtC is not None and
                abs(float(item.irtA) - next_item.a) < 0.001 and
                abs(float(item.irtB) - next_item.b) < 0.001 and
                abs(float(item.irtC) - next_item.c) < 0.001):
                next_public = _public_item_payload(item)
                break

    return theta, mastery, next_public, is_finished, all_mastered
