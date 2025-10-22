"""
Central settings for the Quiz Engine (FastAPI) service.

ASSUMPTIONS / CHECK:
- DATABASE_URL is provided (e.g., in a `.env`) and Prisma Python client is generated.
- Concept field maps to Item.module (MVP). Change CONCEPT_FIELD if the schema changes.
- Mastery thresholds are static defaults for now; can later be read per concept/course.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List


class Settings(BaseModel):
    service_name: str = "studycat-quiz-engine"
    version: str = "0.1.0-mvp"

    # DB connection (Prisma uses DATABASE_URL env var; see db/client.py)
    prisma_log_queries: bool = False

    # Default priors for theta (per concept) if not present in DB
    prior_mu: float = 0.0
    prior_sigma2: float = 1.0

    # Simple mastery thresholds by concept (uniform default). Later: load per course.
    mastery_thresholds: Dict[str, float] = Field(default_factory=dict)
    default_mastery_threshold: float = 1.0

    # Whether to return FINISH instead of 404 when pool exhausted (per your requirement)
    return_finish_flag: bool = True

    # Tie-break determinism for item selection (engine remains deterministic)
    selection_seed: int = 42


settings = Settings()
