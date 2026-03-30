"""
App entrypoint.

LIFECYCLE:
- Connect Prisma on startup and disconnect on shutdown via lifespan.
- Include v1 routes under /v1
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

import routers
from db.client import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(
    title="StudyCAT Quiz Engine",
    version="0.1.0-mvp",
    description="FastAPI service wrapping Unidimensional/Multidimensional IRT models with database-backed theta persistence",
    lifespan=lifespan
)

app.include_router(routers.router, prefix="/v1")
