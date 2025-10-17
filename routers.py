"""
FastAPI routes for the engine.

We expose:
- GET  /v1/health           (liveness)
- POST /v1/attempt/init     (start an attempt and get the first item)
- POST /v1/attempt/step     (apply the latest response and get the next item)

ASSUMPTION: No auth for MVP (you requested to skip). Add middleware later if needed.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from schemas import (
    AttemptInitRequest, AttemptInitResponse,
    AttemptStepRequest, AttemptStepResponse,
    ItemPayload,
)
from service.core import init_attempt, step_attempt, PublicItem

router = APIRouter(tags=["engine"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _map_public_item(p: PublicItem | None) -> ItemPayload | None:
    if not p:
        return None
    return ItemPayload(item_id=p.item_id, skill=p.skill, stem=p.stem, options=p.options)


@router.post("/attempt/init", response_model=AttemptInitResponse)
async def attempt_init(payload: AttemptInitRequest) -> AttemptInitResponse:
    try:
        theta, next_item = await init_attempt(
            attempt_id=payload.attempt_id,
            concepts=payload.concepts,
            prior_mu=payload.prior_mu,
            prior_sigma2=payload.prior_sigma2
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return AttemptInitResponse(
        attempt_id=payload.attempt_id,
        theta=theta,
        next_item=_map_public_item(next_item),
        next_action="CONTINUE"
    )


@router.post("/attempt/step", response_model=AttemptStepResponse)
async def attempt_step(payload: AttemptStepRequest) -> AttemptStepResponse:
    try:
        theta, mastery, next_item, is_finished = await step_attempt(
            attempt_id=payload.attempt_id,
            item_id=payload.item_id,
            answer_index=payload.answer_index
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return AttemptStepResponse(
        attempt_id=payload.attempt_id,
        theta=theta,
        mastery=mastery,
        next_action="FINISH" if is_finished else "CONTINUE",
        next_item=_map_public_item(next_item)
    )
