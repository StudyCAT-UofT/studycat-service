"""
Pydantic models for the engine API.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# ---- Requests ----

class AttemptInitRequest(BaseModel):
    modules: list[str] | None = None           # Modules to test; None => use quiz scope
    prior_mu: float | None = None              # Optional override
    prior_sigma2: float | None = None          # Optional override


class AttemptStepRequest(BaseModel):
    response_id: str                              # Reference to the Response record
    # Fallback fields if Response lookup fails
    item_id: str | None = None
    answer_index: int | None = None


# ---- Responses ----

class ItemPayload(BaseModel):
    item_id: str
    skill: str                                   # concept/module chosen for this item
    stem: str
    options: list[str]                           # Option texts in label order A..D
    figure_url: str | None = None
    reference: str | None = None


class AttemptInitResponse(BaseModel):
    theta: dict[str, float]                      # per-skill ability estimates
    next_item: ItemPayload | None = None
    next_action: str = Field(default="CONTINUE") # Always CONTINUE for init


class AttemptStepResponse(BaseModel):
    theta: dict[str, float]
    mastery: dict[str, bool]
    next_action: str                             # CONTINUE | FINISH | MASTERED
    next_item: ItemPayload | None = None
