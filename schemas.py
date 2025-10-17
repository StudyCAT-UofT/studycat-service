"""
Pydantic models for the engine API.
"""
from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---- Requests ----

class AttemptInitRequest(BaseModel):
    attempt_id: str
    concepts: Optional[List[str]] = None          # ASSUMPTION: modules; None => use quiz scope
    prior_mu: Optional[float] = None              # Optional override
    prior_sigma2: Optional[float] = None          # Optional override


class AttemptStepRequest(BaseModel):
    attempt_id: str
    # For the very first call after init, item_id/answer may be omitted.
    item_id: Optional[str] = None
    # ASSUMPTION: index aligned to labels A=0, B=1, C=2, D=3 (CHECK if Core sends label instead).
    answer_index: Optional[int] = None
    response_time_ms: Optional[int] = None


# ---- Responses ----

class ItemPayload(BaseModel):
    item_id: str
    skill: str                                   # concept/module chosen for this item
    stem: str
    options: List[str]                           # Option texts in label order A..D


class AttemptInitResponse(BaseModel):
    attempt_id: str
    theta: Dict[str, float]                      # per-skill ability estimates
    next_item: Optional[ItemPayload] = None
    next_action: str = Field(default="CONTINUE") # Always CONTINUE for init


class AttemptStepResponse(BaseModel):
    attempt_id: str
    theta: Dict[str, float]
    mastery: Dict[str, bool]
    next_action: str                             # CONTINUE | FINISH
    next_item: Optional[ItemPayload] = None
