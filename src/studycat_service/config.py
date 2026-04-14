"""
Central settings for the Quiz Engine (FastAPI) service.
"""
from __future__ import annotations

from pydantic import BaseModel


class Settings(BaseModel):
    version: str = "0.1.0-mvp"

    # Default priors for theta (per concept) if not present in DB
    prior_mu: float = 0.0
    prior_sigma2: float = 1.0


settings = Settings()
