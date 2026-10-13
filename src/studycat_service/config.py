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

    # Database connection retries on startup (e.g. while the database is still starting)
    db_connect_attempts: int = 5
    db_connect_retry_delay_s: float = 2.0


settings = Settings()
