"""
Thin repository wrapper to isolate Prisma queries from the engine logic.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from prisma.models import Attempt, Response, Item, ItemOption, Quiz
from prisma.enums import AttemptStatus, OptionLabel, BloomCategory
from prisma.errors import PrismaError
from db.client import db


# -------- Attempts / Quiz --------

async def get_attempt(attempt_id: str) -> Optional[Attempt]:
    return await db.attempt.find_unique(
        where={"id": attempt_id},
        include={"quiz": True, "responses": False}
    )


async def get_quiz(quiz_id: str) -> Optional[Quiz]:
    return await db.quiz.find_unique(
        where={"id": quiz_id},
        include=False
    )


async def mark_attempt_finished(attempt_id: str, engine_mastery_at_finish: Optional[Dict[str, Any]] = None) -> None:
    await db.attempt.update(
        where={"id": attempt_id},
        data={
            "status": AttemptStatus.COMPLETED,
            "engineMasteryAtFinish": engine_mastery_at_finish
        }
    )


# -------- Responses --------

async def list_responses(attempt_id: str) -> List[Response]:
    # We want ordered history to optionally "replay" into the model if you choose.
    return await db.response.find_many(
        where={"attemptId": attempt_id},
        order={"answeredAt": "asc"}
    )


async def get_latest_response_without_snapshot(attempt_id: str) -> Optional[Response]:
    # ASSUMPTION: We consider "without snapshot" as engineMasterySnapshot == None.
    rows = await db.response.find_many(
        where={"attemptId": attempt_id, "engineMasterySnapshot": None},
        order={"answeredAt": "desc"},
        take=1,
        include={"item": {"include": {"options": True}}}
    )
    return rows[0] if rows else None


async def attach_engine_snapshot_to_response(response_id: str, snapshot: Dict[str, Any]) -> None:
    await db.response.update(
        where={"id": response_id},
        data={"engineMasterySnapshot": snapshot}
    )


# -------- Items (scope) --------

async def list_eligible_items_for_quiz(quiz_id: str) -> List[Item]:
    """
    Basic scope: union of explicit QuizItem + filter-based selection (modules/blooms).
    This is a minimal example. You might have more constraints later.

    TODO: If you add scope logic to Core Backend, you can instead pass eligible ids to the engine
    and avoid re-computing here.
    """
    quiz = await db.quiz.find_unique(
        where={"id": quiz_id},
        include={"quizItems": True}
    )
    if not quiz:
        return []

    explicit_ids = [qi.itemId for qi in quiz.quizItems]

    # Filter-based scope
    where_clause: Dict[str, Any] = {"active": True}
    if quiz.includedModules:
        where_clause["module"] = {"in": quiz.includedModules}
    if quiz.includedBlooms:
        where_clause["bloom"] = {"in": quiz.includedBlooms}

    # If explicit list exists, union of both (explicit always included)
    filter_items = await db.item.find_many(
        where=where_clause,
        include={"options": True}
    )
    filter_ids = {it.id for it in filter_items}

    # De-dup union
    if explicit_ids:
        explicit_items = await db.item.find_many(
            where={"id": {"in": explicit_ids}},
            include={"options": True}
        )
        items = explicit_items + [it for it in filter_items if it.id not in {ei.id for ei in explicit_items}]
    else:
        items = filter_items

    return items


async def get_item_by_id(item_id: str) -> Optional[Item]:
    return await db.item.find_unique(
        where={"id": item_id},
        include={"options": True}
    )
