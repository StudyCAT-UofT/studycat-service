"""
App entrypoint.

HARDCODED VERSION:
- No database dependencies
- Returns hardcoded data to expose endpoints
- Include v1 routes under /v1
"""
from __future__ import annotations
from fastapi import FastAPI

import routers


app = FastAPI(
    title="StudyCAT Quiz Engine",
    version="0.1.0-mvp-hardcoded",
    description="Hardcoded FastAPI service to expose endpoints for frontend development"
)

app.include_router(routers.router, prefix="/v1")
