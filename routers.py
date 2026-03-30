"""
FastAPI routes for the engine.

We expose:
- GET  /v1/health                       (liveness)
- POST /v1/attempts/{attempt_id}/init   (start an attempt and get the first item)
- POST /v1/attempts/{attempt_id}/step   (apply the latest response and get the next item)

Authentication is not implemented. Add middleware if required.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas import (
    AttemptInitRequest,
    AttemptInitResponse,
    AttemptStepRequest,
    AttemptStepResponse,
    ItemPayload,
)
from service.core import PublicItem, init_attempt, step_attempt

router = APIRouter(tags=["engine"])


@router.get("/health")
def health() -> dict:
    """
    Liveness check endpoint.

    Returns a static {"status": "ok"} payload.
    Does not check database connectivity or any downstream dependencies.
    """
    return {"status": "ok"}


def _map_public_item(p: PublicItem | None) -> ItemPayload | None:
    """
    Convert a PublicItem dataclass returned by the service layer into the
    ItemPayload schema expected by API responses.

    Returns None when no item is available (e.g. the attempt is finished or
    the pool is exhausted), which serialises to null in the JSON response and
    signals to the client that no further question should be displayed.

    Args:
        p: A PublicItem or None.

    Returns:
        The equivalent ItemPayload, or None.
    """
    if not p:
        return None
    return ItemPayload(
        item_id=p.item_id,
        skill=p.skill,
        stem=p.stem,
        options=p.options,
        figure_url=p.figure_url,
        reference=p.reference
    )


@router.post("/attempts/{attempt_id}/init", response_model=AttemptInitResponse)
async def attempt_init(attempt_id: str, payload: AttemptInitRequest) -> AttemptInitResponse:
    """
    Initialise an attempt and return the first item to present to the student.

    Builds the IRT model for the attempt, seeds theta from any prior history
    stored against the enrollment, and selects the first item using the
    maximum information criterion.

    Args:
        attempt_id: The primary key of the Attempt record, taken from the URL path.
        payload:    Request body containing optional module scope, prior_mu,
                    and prior_sigma2 overrides. All fields are optional; the
                    service falls back to the configured defaults when omitted.

    Returns:
        AttemptInitResponse containing:
          - theta:       Current ability estimate per skill (will equal prior_mu
                         if no history exists, or the stored value if it does).
          - next_item:   The first question to show, or None if no items are
                         available for this quiz.
          - next_action: Either "CONTINUE" or "FINISH".

    Raises:
        HTTPException(400): If the attempt_id is not found or any other
                            ValueError is raised by the service layer.
    """
    try:
        theta, next_item = await init_attempt(
            attempt_id=attempt_id,
            modules=payload.modules,
            prior_mu=payload.prior_mu,
            prior_sigma2=payload.prior_sigma2
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    response = AttemptInitResponse(
        theta=theta,
        next_item=_map_public_item(next_item),
        next_action="CONTINUE"
    )

    if next_item is None:
        response.next_action = "FINISH"

    return response


@router.post("/attempts/{attempt_id}/step", response_model=AttemptStepResponse)
async def attempt_step(attempt_id: str, payload: AttemptStepRequest) -> AttemptStepResponse:
    """
    Process the student's latest response and return the next item or a
    completion signal.

    Replays all prior responses for the attempt to reconstruct the IRT model
    state, applies the new response, re-estimates theta for each skill,
    persists the updated theta values and a mastery snapshot, and selects the
    next item if the attempt has not yet reached its fixed length.

    The next_action field drives client-side navigation:
      - "CONTINUE"  — another item is available; display next_item.
      - "FINISH"    — the fixed question limit has been reached; show results.
      - "MASTERED"  — every skill has crossed its mastery threshold; show
                      the mastery celebration screen. Takes precedence over
                      FINISH if both conditions are met simultaneously.

    Args:
        attempt_id: The primary key of the Attempt record, taken from the URL path.
        payload:    Request body containing:
                      - response_id:  ID of the Response record written by the
                                      Core Backend. Used as the primary source
                                      of truth for correctness.
                      - item_id:      Fallback item identifier if the Response
                                      record cannot be found.
                      - answer_index: Fallback zero-based answer index (0=A,
                                      1=B, 2=C, 3=D) used alongside item_id
                                      when the Response record is unavailable.

    Returns:
        AttemptStepResponse containing:
          - theta:       Updated ability estimate per skill after applying the
                         response.
          - mastery:     Boolean mastery flag per skill (True if theta >=
                         mastery_threshold for that skill).
          - next_action: "CONTINUE", "FINISH", or "MASTERED" (see above).
          - next_item:   The next question to show, or null when next_action
                         is "FINISH" or "MASTERED".

    Raises:
        HTTPException(400): If the attempt_id is not found, the item_id is
                            unknown, or any other ValueError is raised by the
                            service layer.
    """
    try:
        theta, mastery, next_item, is_finished, all_mastered = await step_attempt(
            attempt_id=attempt_id,
            response_id=payload.response_id,
            item_id=payload.item_id,
            answer_index=payload.answer_index
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if all_mastered:
        next_action = "MASTERED"
    elif is_finished:
        next_action = "FINISH"
    else:
        next_action = "CONTINUE"

    return AttemptStepResponse(
        theta=theta,
        mastery=mastery,
        next_action=next_action,
        next_item=_map_public_item(next_item)
    )
