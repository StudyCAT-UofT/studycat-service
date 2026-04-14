"""
Thin repository wrapper to isolate Prisma queries from the engine logic.
"""
from __future__ import annotations

from typing import Any

from prisma.models import Attempt, Item, Quiz, QuizModule, Response, Theta

from studycat_service.db.client import db

# -------- Attempts / Quiz --------

async def get_attempt(attempt_id: str) -> Attempt | None:
    """
    Fetch an Attempt record by its primary key, including its related Quiz.

    Args:
        attempt_id: Primary key of the Attempt to fetch.

    Returns:
        The Attempt with quiz included, or None if not found.
    """
    return await db.attempt.find_unique(
        where={"id": attempt_id},
        include={"quiz": True, "responses": False}
    )


async def get_quiz(quiz_id: str) -> Quiz | None:
    """
    Fetch a Quiz record by its primary key without any relations included.

    Args:
        quiz_id: Primary key of the Quiz to fetch.

    Returns:
        The Quiz record, or None if not found.
    """
    return await db.quiz.find_unique(
        where={"id": quiz_id}
    )

async def get_quiz_modules(quiz_id: str) -> list[QuizModule]:
    """
    Fetch all QuizModule records associated with a given quiz.

    Each QuizModule links a quiz to a concept/module and carries the mastery
    threshold for that concept within the quiz context.

    Args:
        quiz_id: Primary key of the Quiz whose modules to retrieve.

    Returns:
        A list of QuizModule records, or an empty list if none are configured.
    """
    quiz_modules = await db.quizmodule.find_many(
        where={"quizId": quiz_id}
    )
    return quiz_modules

# -------- Responses --------

async def list_responses(attempt_id: str) -> list[Response]:
    """
    Fetch all Response records for an attempt in chronological order.

    Responses are ordered by answeredAt ascending so callers can replay them
    into the IRT model in the correct sequence to reconstruct historical theta
    estimates. Each response includes its related item and that item's options.

    Args:
        attempt_id: Primary key of the Attempt whose responses to retrieve.

    Returns:
        A list of Response records ordered oldest-first, each with item and
        options included. Returns an empty list if no responses exist yet.
    """
    # We want ordered history to optionally "replay" into the model if you choose.
    return await db.response.find_many(
        where={"attemptId": attempt_id},
        order={"answeredAt": "asc"},
        include={"item": {"include": {"options": True}}}
    )


async def get_response_by_id(response_id: str) -> Response | None:
    """Fetch a specific Response by ID with item and options included."""
    return await db.response.find_unique(
        where={"id": response_id},
        include={"item": {"include": {"options": True}}}
    )


async def attach_engine_snapshot_to_response(response_id: str, snapshot: str) -> None:
    """
    Persist a mastery snapshot onto a Response record.

    Writes the JSON-serialised theta values to the engineMasterySnapshot field
    so that historical ability estimates are preserved alongside each response
    for auditing and analytics.

    Args:
        response_id: Primary key of the Response to update.
        snapshot:    JSON string of skill → float theta values to store. Should be
                     produced by _snapshot_payload in service/core.py to
                     ensure format consistency.
    """
    await db.response.update(
        where={"id": response_id},
        data={"engineMasterySnapshot": snapshot}
    )


# -------- Items (scope) --------

async def list_eligible_items_for_quiz(quiz_id: str) -> list[Item]:
    """
    Resolve the full set of items eligible for a given quiz by unioning
    explicitly assigned items with filter-based selection.

    Explicit items are those listed in the quiz's quizItems relation and are
    always included regardless of filter criteria. Filter-based items are
    drawn from the active item catalogue and narrowed by the quiz's configured
    module scope (quizModules) and Bloom's taxonomy levels (includedBlooms)
    when those fields are set.

    The two sets are merged with deduplication so an item appearing in both
    the explicit list and the filter results is only returned once.

    Args:
        quiz_id: Primary key of the Quiz to resolve items for.

    Returns:
        A deduplicated list of Item records with options included, or an
        empty list if the quiz does not exist or no items match the criteria.

    TODO: If you add scope logic to Core Backend, you can instead pass eligible ids to the engine
    and avoid re-computing here.
    """
    quiz = await db.quiz.find_unique(
        where={"id": quiz_id},
        include={
            "quizItems": True,
            "quizModules": {"include": {"module": True}},
            }
    )
    if not quiz:
        return []

    explicit_ids = [qi.itemId for qi in quiz.quizItems]

    included_module_ids = [qm.module.id for qm in quiz.quizModules]

    # Filter-based scope
    where_clause: dict[str, Any] = {"active": True}
    if included_module_ids:
        where_clause["moduleId"] = {"in": included_module_ids}

    if quiz.includedBlooms:
        bloom_list = [b.strip() for b in quiz.includedBlooms.split(",")]
        where_clause["bloom"] = {"in": bloom_list}

    # If explicit list exists, union of both (explicit always included)
    filter_items = await db.item.find_many(
        where=where_clause,
        include={"options": True}
    )

    # De-dup union
    if explicit_ids:
        explicit_items = await db.item.find_many(
            where={"id": {"in": explicit_ids}},
            include={"options": True}
        )
        explicit_item_ids = {ei.id for ei in explicit_items}
        items = explicit_items + [
            it for it in filter_items if it.id not in explicit_item_ids
        ]
    else:
        items = filter_items

    return items


async def get_item_by_id(item_id: str) -> Item | None:
    """
    Fetch a single Item record by its primary key, including its options.

    Args:
        item_id: Primary key of the Item to fetch.

    Returns:
        The Item with options included, or None if not found.
    """
    return await db.item.find_unique(
        where={"id": item_id},
        include={"options": True}
    )


async def get_correct_item_ids_for_enrollment_and_quiz(
    enrollment_id: str,
    quiz_id: str
) -> set[str]:
    """
    Returns item IDs that this student has EVER answered correctly
    for this quiz (across all attempts).
    """
    responses = await db.response.find_many(
        where={
            "isCorrect": True,
            "attempt": {
                "quizId": quiz_id,
                "enrollmentId": enrollment_id,
            },
        },
        include={"item": False},  # optional, just get response fields
    )

    # Collect unique item IDs
    return {r.itemId for r in responses}

# -------- Theta Management --------

async def upsert_theta(enrollment_id: str, module_id: str, value: float) -> Theta:
    """
    Create or update the theta value for a specific enrollment and module.

    Performs a manual find-then-update/create rather than a Prisma upsert to
    remain compatible with the current client configuration. Idempotent: calling
    this multiple times with the same arguments will converge on the last value.

    Args:
        enrollment_id: Primary key of the Enrollment to update.
        module_id:     Primary key of the Module (concept) being updated.
        value:         New theta (ability estimate) to store.

    Returns:
        The updated or newly created Theta record.
    """
    # First try to find existing theta
    existing_theta = await db.theta.find_unique(
        where={
            "enrollmentId_moduleId": {
                "enrollmentId": enrollment_id,
                "moduleId": module_id
            }
        }
    )

    if existing_theta:
        # Update existing theta
        return await db.theta.update(
            where={
                "enrollmentId_moduleId": {
                    "enrollmentId": enrollment_id,
                    "moduleId": module_id
                }
            },
            data={"value": value}
        )
    else:
        # Create new theta
        return await db.theta.create(
            data={
                "enrollmentId": enrollment_id,
                "moduleId": module_id,
                "value": value
            }
        )


async def get_thetas_for_enrollment(enrollment_id: str, module_ids: list[str]) -> dict[str, float]:
    """
    Fetch theta values for a batch of modules for a single enrollment.

    Used by init_attempt to seed the IRT model with historical ability
    estimates before selecting the first item. Modules with no stored theta
    are simply absent from the returned dict, and the model falls back to
    prior_mu for those concepts.

    Args:
        enrollment_id: Primary key of the Enrollment to query.
        module_ids:    List of module IDs to retrieve thetas for.

    Returns:
        A dict mapping module_id → float theta value for each module that
        has a stored record. Modules with no record are excluded.
    """
    thetas = await db.theta.find_many(
        where={
            "enrollmentId": enrollment_id,
            "moduleId": {"in": module_ids}
        }
    )
    return {theta.moduleId: theta.value for theta in thetas}
