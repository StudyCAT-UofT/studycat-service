"""
App entrypoint.

LIFECYCLE:
- Connect Prisma on startup and disconnect on shutdown via lifespan.
- Include v1 routes under /v1
"""
from __future__ import annotations
from fastapi import FastAPI
from contextlib import asynccontextmanager

from db.client import db
import routers


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
    description="Stateless FastAPI wrapper around Unidimensional/Multidimensional IRT models",
    lifespan=lifespan
)

app.include_router(routers.router, prefix="/v1")
