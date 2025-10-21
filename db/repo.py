"""
Thin repository wrapper to isolate Prisma queries from the engine logic.

NOTE: Placeholder -- to be checked and implemented.
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


async def get_response_by_id(response_id: str) -> Optional[Response]:
    """Fetch a specific Response by ID with item and options included."""
    return await db.response.find_unique(
        where={"id": response_id},
        include={"item": {"include": {"options": True}}}
    )


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


# -------- Create Functions for Testing --------

async def create_quiz(quiz_data: Dict[str, Any]) -> Quiz:
    """Create a new quiz for testing."""
    return await db.quiz.create(
        data={
            "id": quiz_data["id"],
            "offeringId": quiz_data["offeringId"],
            "title": quiz_data["title"],
            "fixedLength": quiz_data["fixedLength"],
            "includedModules": quiz_data.get("includedModules", []),
            "includedBlooms": [BloomCategory(b) for b in quiz_data.get("includedBlooms", [])],
            "active": True
        }
    )


async def create_item(item_data: Dict[str, Any]) -> Item:
    """Create a new item for testing."""
    # Create the item first
    item = await db.item.create(
        data={
            "id": item_data["id"],
            "courseId": item_data["courseId"],
            "externalQuestionId": item_data["externalQuestionId"],
            "stem": item_data["stem"],
            "module": item_data["concept"],
            "bloom": BloomCategory(item_data["bloom"]),
            "irtA": item_data["irtA"],
            "irtB": item_data["irtB"],
            "irtC": item_data["irtC"],
            "active": True
        }
    )
    
    # Create options
    for option_data in item_data["options"]:
        await db.itemoption.create(
            data={
                "itemId": item.id,
                "label": OptionLabel(option_data["label"]),
                "text": option_data["text"],
                "isCorrect": option_data["isCorrect"]
            }
        )
    
    # Return item with options
    return await get_item_by_id(item.id)


async def create_attempt(attempt_data: Dict[str, Any]) -> Attempt:
    """Create a new attempt for testing."""
    return await db.attempt.create(
        data={
            "id": attempt_data["id"],
            "quizId": attempt_data["quizId"],
            "userId": attempt_data["userId"],
            "status": AttemptStatus(attempt_data["status"]),
            "startedAt": attempt_data["startedAt"],
            "fixedLengthN": attempt_data.get("fixedLengthN", 10)
        }
    )


async def create_response(response_data: Dict[str, Any]) -> Response:
    """Create a new response for testing."""
    # Convert answerIndex to OptionLabel
    answer_index = response_data["answerIndex"]
    option_labels = ["A", "B", "C", "D"]
    selected_label = option_labels[answer_index] if 0 <= answer_index < len(option_labels) else "A"
    
    return await db.response.create(
        data={
            "id": response_data["id"],
            "attemptId": response_data["attemptId"],
            "itemId": response_data["itemId"],
            "selectedLabel": OptionLabel(selected_label),
            "isCorrect": response_data["isCorrect"],
            "responseTimeMs": response_data.get("responseTimeMs", 0),
            "answeredAt": response_data.get("submittedAt", "2024-01-01T00:00:00Z"),
            "askedAt": response_data.get("askedAt", "2024-01-01T00:00:00Z")
        }
    )


# -------- Additional Helper Functions --------

async def get_quiz_by_id(quiz_id: str) -> Optional[Quiz]:
    """Get quiz by ID with all related data."""
    return await db.quiz.find_unique(
        where={"id": quiz_id},
        include={"quizItems": True}
    )


async def get_attempt_by_id(attempt_id: str) -> Optional[Attempt]:
    """Get attempt by ID with all related data."""
    return await db.attempt.find_unique(
        where={"id": attempt_id},
        include={"quiz": True, "responses": True}
    )
