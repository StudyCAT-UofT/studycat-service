"""
conftest.py - shared fixtures for the adaptive-testing test suite.

All factory helpers are defined as plain underscore-prefixed functions so
they can also be imported directly when needed. Each is then exposed as a
pytest fixture that returns the callable, allowing tests to call them with
arbitrary arguments via normal function-call syntax.
"""

from unittest.mock import MagicMock

import pytest

# --- raw utility functions (still importable directly if needed) ---

def _pool_items(uni_model) -> list:
    """
    Return the live TestItem references stored inside a UnidimensionalModel's
    item pool.

    Why this exists: ItemPool.delete_item locates items using list.index(),
    which compares by object identity (not value equality). If a test builds
    a TestItem externally and passes it to record_response, the lookup fails
    with a ValueError because the pool holds a different object in memory even
    if the IRT parameters are identical. This helper surfaces the exact
    references the pool owns so tests can safely hand them back.
    """
    return list(uni_model.adaptive_test.item_pool.test_items)


def _make_db_item(module_id="math", a=1.0, b=0.0, c=0.25, active=True, item_id=None):
    """
    Build a MagicMock that mimics a Prisma DB Item record.

    Parameters mirror the fields that service/core.py reads:
      - moduleId  : concept/skill the item belongs to
      - irtA/B/C  : IRT discrimination, difficulty, and guessing parameters
      - active    : whether the item should be included in pools
      - id        : primary key; defaults to '<module_id>-item'

    A single answer option labelled 'A' (correct) is attached so that
    _public_item_payload and answer-checking logic have something to work with.
    """
    item = MagicMock()
    item.id        = item_id or f"{module_id}-item"
    item.moduleId  = module_id
    item.active    = active
    item.irtA      = a
    item.irtB      = b
    item.irtC      = c
    item.stem      = "A question"
    item.figureUrl = None
    item.reference = None
    opt = MagicMock()
    opt.label     = "A"
    opt.text      = "Answer"
    opt.isCorrect = True
    item.options  = [opt]
    return item


def _make_quiz_module(module_id="math", threshold=1.5):
    """
    Build a MagicMock that mimics a Prisma QuizModule record.

    masteryThreshold is the theta value a student must reach for the skill to
    be considered mastered. Tests that want mastery to trigger easily should
    pass a low threshold (e.g. 0.5); tests that want it unreachable should
    pass a high one (e.g. 3.0).
    """
    qm = MagicMock()
    qm.moduleId         = module_id
    qm.masteryThreshold = threshold
    return qm


def _make_attempt(quiz_id="quiz1", enrollment_id="enr1", fixed_length=5):
    """
    Build a MagicMock that mimics a Prisma Attempt record.

    fixed_length controls how many responses are allowed before step_attempt
    stops issuing new items. Set it to 1 in tests that want to verify the
    finished=True path, or to a large number to keep the test running.
    """
    a = MagicMock()
    a.quizId       = quiz_id
    a.enrollmentId = enrollment_id
    a.fixedLengthN = fixed_length
    return a


def _make_response(response_id, db_item, is_correct=True):
    """
    Build a MagicMock that mimics a Prisma Response record.

    Associates the response with a specific DB item so that step_attempt can
    look up the item's IRT parameters and moduleId when replaying history.
    is_correct drives which direction theta moves after the response is
    processed.
    """
    r = MagicMock()
    r.id        = response_id
    r.isCorrect = is_correct
    r.item      = db_item
    return r


# --- fixtures ---

@pytest.fixture
def pool_items():
    return _pool_items


@pytest.fixture
def make_db_item():
    return _make_db_item


@pytest.fixture
def make_quiz_module():
    return _make_quiz_module


@pytest.fixture
def make_attempt():
    return _make_attempt


@pytest.fixture
def make_response():
    return _make_response
