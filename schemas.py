"""
Pydantic models for request/response payloads.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# ---- Public-facing item (we hide a/b/c from clients) ------------------------
class ItemPayload(BaseModel):
    item_id: str
    stem: str
    options: List[str]
    concept: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ---- Session init -----------------------------------------------------------
class InitSessionRequest(BaseModel):
    concepts: Optional[List[str]] = None     # restrict pool; None = all
    max_items: Optional[int] = None          # hard cap this session
    prior_mu: Optional[float] = None         # prior mean for theta
    prior_sigma2: Optional[float] = None     # prior variance

class InitSessionResponse(BaseModel):
    session_id: str
    theta: Dict[str, float]
    next_item: Optional[ItemPayload] = None  # prefetch first item

# ---- Single-step flow: submit previous answer & get next --------------------
class StepRequest(BaseModel):
    session_id: str
    # For the first step right after /init, client can omit item_id/answer_index
    # (meaning: there's no prior response to submit yet).
    item_id: Optional[str] = None
    answer_index: Optional[int] = None
    response_time_ms: Optional[int] = None

class StepResponse(BaseModel):
    session_id: str
    theta: Dict[str, float]
    mastery: Dict[str, bool]
    next_action: str                 # CONTINUE | FINISH
    next_item: Optional[ItemPayload] = None

# ---- Optional diagnostics ---------------------------------------------------
class SessionStateRequest(BaseModel):
    session_id: str

class SessionStateResponse(BaseModel):
    session_id: str
    theta: Dict[str, float]
    asked_items: List[str]
    remaining_items: int
    mastery: Dict[str, bool]
