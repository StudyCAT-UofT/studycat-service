"""
Unit tests for service/core.py
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from service.core import _index_from_label, _label_from_index, init_attempt

# ============================================================================
# Helper Function Tests
# ============================================================================


def test_label_from_index_valid():
    """Test valid index to label conversions."""
    assert _label_from_index(0) == "A"
    assert _label_from_index(1) == "B"
    assert _label_from_index(2) == "C"
    assert _label_from_index(3) == "D"


def test_label_from_index_out_of_range():
    """Test that out-of-range indices raise IndexError."""
    with pytest.raises(IndexError):
        _label_from_index(4)


def test_index_from_label_valid():
    """Test valid label to index conversions."""
    assert _index_from_label("A") == 0
    assert _index_from_label("B") == 1
    assert _index_from_label("C") == 2
    assert _index_from_label("D") == 3


# ============================================================================
# Async Function Tests
# ============================================================================


@pytest.mark.asyncio
async def test_init_attempt_unknown_attempt_id():
    """Test that unknown attempt_id raises ValueError."""
    with patch("service.core.repo.get_attempt", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        with pytest.raises(ValueError, match="Unknown attempt_id"):
            await init_attempt("unknown_id", None, None, None)


@pytest.mark.asyncio
async def test_init_attempt_no_items():
    """Test init_attempt when there are no eligible items."""
    attempt = MagicMock()
    attempt.quizId = "quiz1"
    attempt.enrollmentId = "enrollment1"

    with patch("service.core.repo.get_attempt", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = attempt

        with patch(
            "service.core.repo.list_eligible_items_for_quiz", new_callable=AsyncMock
        ) as mock_items:
            mock_items.return_value = []

            theta, public = await init_attempt("attempt1", None, None, None)
            assert theta == {}
            assert public is None
