"""
Thin repository wrapper to isolate Prisma queries from the engine logic.

NOTE: Placeholder -- to be checked and implemented.
"""
from __future__ import annotations

from typing import Any

from prisma.models import Attempt, Item, Quiz, Response, Theta, QuizModule

from db.client import db

# -------- Attempts / Quiz --------

async def get_attempt(attempt_id: str) -> Attempt | None:
    return await db.attempt.find_unique(
        where={"id": attempt_id},
        include={"quiz": True, "responses": False}
    )


async def get_quiz(quiz_id: str) -> Quiz | None:
    return await db.quiz.find_unique(
        where={"id": quiz_id},
        include=False
    )

async def get_quiz_modules(quiz_id: str) -> list[QuizModule] | None:
    quiz_modules = await db.quizmodule.find_many(
        where={"quizId": quiz_id}
    )
    
    return quiz_modules


async def mark_attempt_finished(
        attempt_id: str,
        engine_mastery_at_finish: dict[str, Any] | None = None,
    ) -> None:
    await db.attempt.update(
        where={"id": attempt_id},
        data={
            "status": "COMPLETED",
            "engineMasteryAtFinish": engine_mastery_at_finish
        }
    )


# -------- Responses --------

async def list_responses(attempt_id: str) -> list[Response]:
    # We want ordered history to optionally "replay" into the model if you choose.
    return await db.response.find_many(
        where={"attemptId": attempt_id},
        order={"answeredAt": "asc"},
        include={"item": {"include": {"options": True}}}
    )


async def get_latest_response_without_snapshot(attempt_id: str) -> Response | None:
    # ASSUMPTION: We consider "without snapshot" as engineMasterySnapshot == None.
    rows = await db.response.find_many(
        where={"attemptId": attempt_id, "engineMasterySnapshot": None},
        order={"answeredAt": "desc"},
        take=1,
        include={"item": {"include": {"options": True}}}
    )
    return rows[0] if rows else None


async def get_response_by_id(response_id: str) -> Response | None:
    """Fetch a specific Response by ID with item and options included."""
    return await db.response.find_unique(
        where={"id": response_id},
        include={"item": {"include": {"options": True}}}
    )


async def attach_engine_snapshot_to_response(response_id: str, snapshot: dict[str, Any]) -> None:
    await db.response.update(
        where={"id": response_id},
        data={"engineMasterySnapshot": snapshot}
    )


# -------- Items (scope) --------

async def list_eligible_items_for_quiz(quiz_id: str) -> list[Item]:
    """
    Basic scope: union of explicit QuizItem + filter-based selection (modules/blooms).
    This is a minimal example. You might have more constraints later.

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
    return await db.item.find_unique(
        where={"id": item_id},
        include={"options": True}
    )


# -------- Additional Helper Functions --------

async def get_quiz_by_id(quiz_id: str) -> Quiz | None:
    """Get quiz by ID with all related data."""
    return await db.quiz.find_unique(
        where={"id": quiz_id},
        include={"quizItems": True}
    )


async def get_attempt_by_id(attempt_id: str) -> Attempt | None:
    """Get attempt by ID with all related data."""
    return await db.attempt.find_unique(
        where={"id": attempt_id},
        include={"quiz": True, "responses": True}
    )


# -------- Theta Management --------

async def get_theta(enrollment_id: str, module_id: str) -> Theta | None:
    """Get existing theta value for a specific enrollment and module."""
    return await db.theta.find_unique(
        where={
            "enrollmentId_moduleId": {
                "enrollmentId": enrollment_id,
                "moduleId": module_id
            }
        }
    )


async def upsert_theta(enrollment_id: str, module_id: str, value: float) -> Theta:
    """Create or update theta value for a specific enrollment and module."""
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
    """Get theta values for multiple modules for a specific enrollment."""
    thetas = await db.theta.find_many(
        where={
            "enrollmentId": enrollment_id,
            "moduleId": {"in": module_ids}
        }
    )
    return {theta.moduleId: theta.value for theta in thetas}
