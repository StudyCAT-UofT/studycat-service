"""
Pydantic models for the engine API.
"""
from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---- Requests ----

class AttemptInitRequest(BaseModel):
    modules: Optional[List[str]] = None           # Modules to test; None => use quiz scope
    prior_mu: Optional[float] = None              # Optional override
    prior_sigma2: Optional[float] = None          # Optional override


class AttemptStepRequest(BaseModel):
    response_id: str                              # Reference to the Response record
    # Fallback fields if Response lookup fails
    item_id: Optional[str] = None
    answer_index: Optional[int] = None
    response_time_ms: Optional[int] = None


# ---- Responses ----

class ItemPayload(BaseModel):
    item_id: str
    skill: str                                   # concept/module chosen for this item
    stem: str
    options: List[str]                           # Option texts in label order A..D


class AttemptInitResponse(BaseModel):
    theta: Dict[str, float]                      # per-skill ability estimates
    next_item: Optional[ItemPayload] = None
    next_action: str = Field(default="CONTINUE") # Always CONTINUE for init


class AttemptStepResponse(BaseModel):
    theta: Dict[str, float]
    mastery: Dict[str, bool]
    next_action: str                             # CONTINUE | FINISH
    next_item: Optional[ItemPayload] = None
