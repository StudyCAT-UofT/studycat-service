"""
Seeding functions for creating test data in the database.

These functions can be used to seed the database with test data for development
and testing purposes.
"""
from __future__ import annotations

import asyncio
from typing import Any

from prisma.enums import AttemptStatus, BloomCategory, OptionLabel
from prisma.models import Attempt, Item, Quiz, Response

from db.client import db
from db.repo import get_item_by_id


async def create_quiz(quiz_data: dict[str, Any]) -> Quiz:
    """Create a new quiz for testing."""
    return await db.quiz.create(
        data={
            "id": quiz_data["id"],
            "offeringId": quiz_data["offeringId"],
            "title": quiz_data["title"],
            "fixedLength": quiz_data["fixedLength"],
            "includedModuleIds": quiz_data.get("includedModuleIds", []),
            "includedBlooms": [BloomCategory(b) for b in quiz_data.get("includedBlooms", [])],
            "active": True
        }
    )


async def create_item(item_data: dict[str, Any]) -> Item:
    """Create a new item for testing."""
    # Create the item first
    item = await db.item.create(
        data={
            "id": item_data["id"],
            "courseId": item_data["courseId"],
            "externalQuestionId": item_data["externalQuestionId"],
            "stem": item_data["stem"],
            "moduleId": item_data["moduleId"],
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


async def create_attempt(attempt_data: dict[str, Any]) -> Attempt:
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


async def create_response(response_data: dict[str, Any]) -> Response:
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


async def main():
    """Main function to run seeding operations."""
    try:
        await db.connect()
        print("✓ Connected to database")

        # Example usage - users can customize this section
        print("\nSeeding functions are available. Use them in your own scripts:")
        print("  - create_quiz(quiz_data)")
        print("  - create_item(item_data)")
        print("  - create_attempt(attempt_data)")
        print("  - create_response(response_data)")
        print("\nExample:")
        print("  from db.seed import create_quiz, create_item")
        print("  await create_quiz({...})")

    except Exception as e:
        print(f"✗ Error: {e}")
        raise
    finally:
        await db.disconnect()
        print("✓ Disconnected from database")


if __name__ == "__main__":
    asyncio.run(main())

