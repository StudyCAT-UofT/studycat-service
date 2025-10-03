"""
FastAPI routes

ENDPOINTS
- GET  /v1/health
  PURPOSE: Liveness check for deploy/monitoring.

- POST /v1/session/init
  PURPOSE: Start an adaptive session (scope/prior).
  RETURNS: session_id, initial theta, and a pre-fetched first item.

- POST /v1/session/step
  PURPOSE: Submit the previous answer AND receive the next item in one call.
  USAGE:
    • First call after /init: omit item_id/answer_index to just fetch the next item.
    • Subsequent calls: include previous item_id & answer_index to update theta.
  RETURNS: updated theta, mastery, next_action, and next_item (if continuing).

- POST /v1/session/state  (optional but helpful)
  PURPOSE: Diagnostic snapshot for UI recovery (e.g., refresh).
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from schemas import (
    InitSessionRequest, InitSessionResponse,
    StepRequest, StepResponse,
    SessionStateRequest, SessionStateResponse,
    ItemPayload,
)
from session_service import SessionService, SessionStore
from irt_adapter import IRTAdapter
from dataset import Dataset

router = APIRouter(tags=["api"])

# Compose singletons (simple in-memory; swap to DI or startup events if needed)
_dataset = Dataset()
_store = SessionStore()
_irt = IRTAdapter()
_service = SessionService(dataset=_dataset, store=_store, irt=_irt)

@router.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}

@router.post("/session/init", response_model=InitSessionResponse)
def init_session(payload: InitSessionRequest) -> InitSessionResponse:
    """
    PURPOSE:
    - Start a new adaptive session with optional concept scope and prior.
    - Pre-fetch the first item to save a round-trip for the UI.
    """
    st = _service.init_session(
        concepts=payload.concepts,
        max_items=payload.max_items,
        prior_mu=payload.prior_mu,
        prior_sigma2=payload.prior_sigma2,
    )
    first_item = _service.next_item(st)
    return InitSessionResponse(
        session_id=st.session_id,
        theta=st.theta,
        next_item=_to_public(first_item) if first_item else None,
    )

@router.post("/session/step", response_model=StepResponse)
def step(payload: StepRequest) -> StepResponse:
    """
    PURPOSE:
    - Single-step API to submit the previous answer and receive the next item.
    - On the FIRST call after /init, omit item_id/answer_index to just advance.
    """
    try:
        result = _service.step(payload.session_id, payload.item_id, payload.answer_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    next_action = "FINISH" if result["finished"] else "CONTINUE"
    return StepResponse(
        session_id=payload.session_id,
        theta=result["theta"],
        mastery=result["mastery"],
        next_action=next_action,
        next_item=_to_public(result["next_item"]) if result["next_item"] else None,
    )

@router.post("/session/state", response_model=SessionStateResponse)
def state(payload: SessionStateRequest) -> SessionStateResponse:
    """
    PURPOSE:
    - Provide a diagnostic snapshot for UI recovery or debug views.
    """
    try:
        st = _service.state(payload.session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    mastery = {c: (v >= 0.5) for c, v in st.theta.items()}  # same heuristic as step()
    candidates = _dataset.items_by_concepts(st.concepts)
    remaining = max(0, min(len(candidates), st.max_items - len(st.asked)))
    return SessionStateResponse(
        session_id=payload.session_id,
        theta=st.theta,
        asked_items=st.asked,
        remaining_items=remaining,
        mastery=mastery,
    )

# ---- mapping helper ---------------------------------------------------------
def _to_public(item) -> ItemPayload:
    """Map internal ItemRecord to public schema."""
    return ItemPayload(
        item_id=item.item_id,
        stem=item.stem,
        options=item.options,
        concept=item.concept,
        metadata=item.metadata,
    )
