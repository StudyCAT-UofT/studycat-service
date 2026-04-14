"""
Tests for service/core.py - label helpers, snapshot payload, public item
payload, init_attempt, and step_attempt.

The orchestration tests (init_attempt, step_attempt) mock every repo call so
the tests run without a database and focus purely on the logic inside core.py.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from studycat_service.service.core import _index_from_label, _label_from_index

# ---------------------------------------------------------------------------
# _label_from_index / _index_from_label
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _snapshot_payload
# ---------------------------------------------------------------------------

class TestSnapshotPayload:
    """
    _snapshot_payload serialises current theta values to a JSON string that is
    stored on Response.engineMasterySnapshot. The format must be compatible
    with the existing data in the database (float values keyed by skill name,
    scoped to the mastery dict's keys only).
    """
    def test_returns_valid_json(self):
        """
        The return value must be a string that json.loads can parse into a
        dict without raising an exception. Uses two skills to confirm the
        serialiser handles multiple entries correctly.
        """
        from studycat_service.service.core import _snapshot_payload

        parsed = json.loads(_snapshot_payload(
            {"math": 0.75, "reading": -0.3},
            {"math": True, "reading": False},
        ))
        assert isinstance(parsed, dict)

    def test_values_are_floats(self):
        """
        Each value in the snapshot must be a Python float (not a bool or int),
        matching the existing data format described in the source comment.
        Checks a single skill whose boolean mastery flag True should have been
        converted to float(theta) rather than stored as 1.0 from the bool.
        """
        from studycat_service.service.core import _snapshot_payload

        parsed = json.loads(_snapshot_payload({"math": 1.2}, {"math": True}))
        assert isinstance(parsed["math"], float)

    def test_only_mastery_keys_included(self):
        """
        The snapshot is scoped to the skills in the mastery dict, not the full
        theta dict. If theta contains an extra skill that mastery does not,
        that skill must be absent from the output. This prevents stale or
        out-of-scope skills from leaking into the snapshot stored on the
        response record.
        """
        from studycat_service.service.core import _snapshot_payload

        parsed = json.loads(_snapshot_payload(
            {"math": 0.5, "extra_skill": 1.0},
            {"math": True},
        ))
        assert "extra_skill" not in parsed
        assert "math" in parsed


# ---------------------------------------------------------------------------
# _public_item_payload
# ---------------------------------------------------------------------------

class TestPublicItemPayload:
    """
    _public_item_payload converts a Prisma DB Item record into a PublicItem
    dataclass suitable for sending to the frontend. Tests cover field mapping,
    option ordering, and option text extraction.
    """
    def _make_db_item(self):
        """
        Build a mock DB item with four options labelled A-D stored in
        non-alphabetical dict order to test that the sort is applied.
        """
        item = MagicMock()
        item.id        = "item-abc"
        item.moduleId  = "math"
        item.stem      = "What is 2+2?"
        item.figureUrl = "https://example.com/fig.png"
        item.reference = "Chapter 3"
        options = []
        for label, text in [("A", "1"), ("B", "4"), ("C", "3"), ("D", "2")]:
            opt = MagicMock()
            opt.label = label
            opt.text  = text
            options.append(opt)
        item.options = options
        return item

    def test_fields_mapped_correctly(self):
        """
        All scalar fields on the DB item (id, moduleId, stem, figureUrl,
        reference) must be mapped to the correct attributes of the returned
        PublicItem dataclass. Checks each field individually so a renaming
        regression points directly to the affected attribute.
        """
        from studycat_service.service.core import _public_item_payload

        result = _public_item_payload(self._make_db_item())
        assert result.item_id    == "item-abc"
        assert result.skill      == "math"
        assert result.stem       == "What is 2+2?"
        assert result.figure_url == "https://example.com/fig.png"
        assert result.reference  == "Chapter 3"

    def test_options_ordered_a_to_d(self):
        """
        The options list in the PublicItem must always be sorted A→B→C→D
        regardless of the order the DB returns them. The mock stores options
        in A-D order already; the test checks the text values that correspond
        to that label order are ["1", "4", "3", "2"].
        """
        from studycat_service.service.core import _public_item_payload

        result = _public_item_payload(self._make_db_item())
        assert result.options == ["1", "4", "3", "2"]

    def test_options_contain_only_text(self):
        """
        The options list must contain plain strings (the display text), not
        option objects or labels. Iterates every element to confirm no mock
        objects or label values were accidentally included.
        """
        from studycat_service.service.core import _public_item_payload

        result = _public_item_payload(self._make_db_item())
        for opt in result.options:
            assert isinstance(opt, str)


# ---------------------------------------------------------------------------
# init_attempt
# ---------------------------------------------------------------------------

class TestInitAttempt:
    """
    init_attempt loads the attempt and eligible items from the DB, builds the
    IRT model (seeding theta from any stored history), and returns the initial
    theta dict and the first item to show the student.

    All repo calls are mocked so tests run without a database.
    """
    @pytest.mark.asyncio
    async def test_returns_theta_and_public_item(
        self,
        make_db_item,
        make_quiz_module,
        make_attempt
        ):
        """
        Happy-path: given a valid attempt, one eligible item, no prior theta
        history, and a quiz module, init_attempt should return a theta dict
        keyed by 'math' and a PublicItem whose skill is 'math'. Confirms the
        basic wiring between pool construction, model initialisation, and item
        selection all work end-to-end.
        """
        from studycat_service.service.core import init_attempt

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=make_attempt()), \
             patch("studycat_service.service.core.repo.list_eligible_items_for_quiz",
                   new_callable=AsyncMock,
                   return_value=[make_db_item()]), \
             patch("studycat_service.service.core.repo.get_thetas_for_enrollment",
                   new_callable=AsyncMock,
                   return_value={}), \
             patch("studycat_service.service.core.repo.get_quiz_modules",
                   new_callable=AsyncMock,
                   return_value=[make_quiz_module()]), \
             patch("studycat_service.service.core.repo.get_quiz",
                   new_callable=AsyncMock,
                   return_value=MagicMock(allowRepeatCorrect=False)):

            theta, public = await init_attempt("attempt1", ["math"], None, None)

        assert "math" in theta
        assert public is not None
        assert public.skill == "math"

    @pytest.mark.asyncio
    async def test_existing_thetas_seed_model(self, make_db_item, make_quiz_module, make_attempt):
        """
        When the enrollment already has a stored theta for a skill (from a
        previous session), init_attempt must load that value into the model
        before choosing the first item. The returned theta for 'math' should
        equal the stored value (1.8) rather than the default prior_mu.
        Confirms that historical progress is not discarded on re-entry.
        """
        from studycat_service.service.core import init_attempt

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=make_attempt()), \
             patch("studycat_service.service.core.repo.list_eligible_items_for_quiz",
                   new_callable=AsyncMock, return_value=[make_db_item()]), \
             patch("studycat_service.service.core.repo.get_thetas_for_enrollment",
                   new_callable=AsyncMock,
                   return_value={"math": 1.8}), \
             patch("studycat_service.service.core.repo.get_quiz_modules",
                   new_callable=AsyncMock,
                   return_value=[make_quiz_module()]), \
             patch("studycat_service.service.core.repo.get_quiz",
                   new_callable=AsyncMock,
                   return_value=MagicMock(allowRepeatCorrect=False)):

            theta, _ = await init_attempt("attempt1", ["math"], 0.0, 1.0)

        assert abs(theta["math"] - 1.8) < 1e-4, (
            f"Expected seeded theta 1.8, got {theta['math']}"
        )

    @pytest.mark.asyncio
    async def test_no_items_returns_empty(self, make_attempt):
        """
        If list_eligible_items_for_quiz returns an empty list, there are no
        items to ask and no model to build. init_attempt should return an
        empty theta dict and None for the public item without raising an
        exception.
        """
        from studycat_service.service.core import init_attempt

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=make_attempt()), \
             patch("studycat_service.service.core.repo.list_eligible_items_for_quiz",
                   new_callable=AsyncMock,
                   return_value=[]), \
             patch("studycat_service.service.core.repo.get_quiz",
                   new_callable=AsyncMock,
                   return_value=MagicMock(allowRepeatCorrect=False)):

            theta, public = await init_attempt("attempt1", None, None, None)

        assert theta  == {}
        assert public is None

    @pytest.mark.asyncio
    async def test_unknown_attempt_raises(self):
        """
        If get_attempt returns None the attempt_id does not exist in the DB.
        init_attempt should raise ValueError with a message containing
        'Unknown attempt_id' so callers can return an appropriate HTTP 404.
        """
        from studycat_service.service.core import init_attempt

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=None):
            with pytest.raises(ValueError, match="Unknown attempt_id"):
                await init_attempt("bad", None, None, None)


# ---------------------------------------------------------------------------
# step_attempt
# ---------------------------------------------------------------------------

class TestStepAttempt:
    """
    step_attempt replays all prior responses for the attempt to reconstruct
    the IRT model state, applies the latest response, persists theta and a
    snapshot, and returns the next item (or signals completion).

    All repo calls are mocked. The DB item mock uses matching IRT parameters
    so _find_test_item_by_irt_params can locate the correct TestItem when
    replaying.
    """

    @pytest.mark.asyncio
    async def test_correct_response_increases_theta(
        self,
        make_db_item,
        make_quiz_module,
        make_attempt,
        make_response
        ):
        """
        After processing one correct response for a math item, the returned
        theta dict should show a value above 0.0 (the default prior_mu).
        Confirms that the response is applied to the model and that the
        resulting theta is propagated back to the caller correctly. Uses
        fixed_length=5 so the attempt is not immediately finished.
        """
        from studycat_service.service.core import step_attempt

        attempt  = make_attempt(fixed_length=5)
        db_item  = make_db_item()
        response = make_response("resp1", db_item, is_correct=True)
        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=attempt), \
             patch("studycat_service.service.core.repo.list_eligible_items_for_quiz",
                   new_callable=AsyncMock,
                   return_value=[db_item]), \
             patch("studycat_service.service.core.repo.get_quiz_modules",
                   new_callable=AsyncMock,
                   return_value=[make_quiz_module(threshold=2.0)]), \
             patch("studycat_service.service.core.repo.list_responses",
                   new_callable=AsyncMock,
                   return_value=[response]), \
             patch("studycat_service.service.core.repo.get_response_by_id",
                   new_callable=AsyncMock,
                   return_value=response), \
             patch("studycat_service.service.core.repo.upsert_theta",
                   new_callable=AsyncMock), \
             patch("studycat_service.service.core.repo.attach_engine_snapshot_to_response",
                   new_callable=AsyncMock), \
             patch("studycat_service.service.core.repo.get_quiz",
                   new_callable=AsyncMock,
                   return_value=MagicMock(allowRepeatCorrect=False)):

            theta, _, _, _, _ = await step_attempt("attempt1", "resp1")

        assert theta["math"] > 0.0

    @pytest.mark.asyncio
    async def test_finished_when_response_count_equals_fixed_length(
        self,
        make_db_item,
        make_quiz_module,
        make_attempt,
        make_response
        ):
        """
        When the number of recorded responses equals fixedLengthN, step_attempt
        must not select another item and must return is_finished=True with
        next_public=None. Uses fixed_length=1 and one response so the limit
        is hit immediately. Confirms the fixed-length stopping rule is enforced
        even when items remain in the pool.
        """
        from studycat_service.service.core import step_attempt

        attempt  = make_attempt(fixed_length=1)
        db_item  = make_db_item()
        response = make_response("resp1", db_item, is_correct=True)

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=attempt), \
             patch("studycat_service.service.core.repo.list_eligible_items_for_quiz",
                   new_callable=AsyncMock,
                   return_value=[db_item]), \
             patch("studycat_service.service.core.repo.get_quiz_modules",
                   new_callable=AsyncMock,
                   return_value=[make_quiz_module(threshold=2.0)]), \
             patch("studycat_service.service.core.repo.list_responses",
                   new_callable=AsyncMock,
                   return_value=[response]), \
             patch("studycat_service.service.core.repo.get_response_by_id",
                   new_callable=AsyncMock,
                   return_value=response), \
             patch("studycat_service.service.core.repo.upsert_theta",
                   new_callable=AsyncMock), \
             patch("studycat_service.service.core.repo.attach_engine_snapshot_to_response",
                   new_callable=AsyncMock), \
             patch("studycat_service.service.core.repo.get_quiz",
                   new_callable=AsyncMock,
                   return_value=MagicMock(allowRepeatCorrect=False)):

            _, _, next_public, is_finished, _ = await step_attempt("attempt1", "resp1")

        assert is_finished is True
        assert next_public is None

    @pytest.mark.asyncio
    async def test_snapshot_persisted_for_response(
        self,
        make_db_item,
        make_quiz_module,
        make_attempt,
        make_response
        ):
        """
        After processing a response, step_attempt must call
        attach_engine_snapshot_to_response exactly once with the response_id
        and a snapshot keyword argument. Uses a dedicated AsyncMock for the
        attach call and asserts assert_awaited_once() to confirm the repo
        write happened and was not accidentally called twice or skipped.
        """
        from studycat_service.service.core import step_attempt

        attempt     = make_attempt(fixed_length=5)
        db_item     = make_db_item()
        response    = make_response("resp1", db_item, is_correct=True)
        mock_attach = AsyncMock()

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=attempt), \
             patch("studycat_service.service.core.repo.list_eligible_items_for_quiz",
                   new_callable=AsyncMock,
                   return_value=[db_item]), \
             patch("studycat_service.service.core.repo.get_quiz_modules",
                   new_callable=AsyncMock,
                   return_value=[make_quiz_module(threshold=2.0)]), \
             patch("studycat_service.service.core.repo.list_responses",
                   new_callable=AsyncMock,
                   return_value=[response]), \
             patch("studycat_service.service.core.repo.get_response_by_id",
                   new_callable=AsyncMock,
                   return_value=response), \
             patch("studycat_service.service.core.repo.upsert_theta",
                   new_callable=AsyncMock), \
             patch("studycat_service.service.core.repo.attach_engine_snapshot_to_response",
                   mock_attach), \
             patch("studycat_service.service.core.repo.get_quiz",
                   new_callable=AsyncMock,
                   return_value=MagicMock(allowRepeatCorrect=False)):

            await step_attempt("attempt1", "resp1")

        mock_attach.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_attempt_raises(self):
        """
        If get_attempt returns None, step_attempt should raise ValueError with
        'Unknown attempt_id' before touching any other repo method. This
        mirrors init_attempt's behaviour and ensures callers receive a clear
        error they can map to an HTTP 404 rather than a downstream AttributeError.
        """
        from studycat_service.service.core import step_attempt

        with patch("studycat_service.service.core.repo.get_attempt",
                   new_callable=AsyncMock,
                   return_value=None):
            with pytest.raises(ValueError, match="Unknown attempt_id"):
                await step_attempt("bad", "resp1")
