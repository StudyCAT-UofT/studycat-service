"""
Entrypoint to run the FastAPI app.

Dev:
    uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI
import routers

app = FastAPI(
    title="StudyCAT IRT API",
    version="1.0.0",
    description="Minimal API that wraps an external IRT library for adaptive testing.",
)

# v1 routes
app.include_router(routers.router, prefix="/v1")
