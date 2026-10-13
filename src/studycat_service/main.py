"""
App entrypoint.

LIFECYCLE:
- Connect Prisma on startup (retrying while the database is unavailable) and
  disconnect on shutdown via lifespan.
- Include v1 routes under /v1
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prisma.errors import PrismaError

from . import routers
from .config import settings
from .db.client import db

logger = logging.getLogger(__name__)


async def connect_db() -> None:
    """Connect to the database, retrying a few times before giving up."""
    for attempt in range(1, settings.db_connect_attempts + 1):
        try:
            await db.connect()
            return
        except PrismaError as exc:
            if attempt == settings.db_connect_attempts:
                raise
            logger.warning(
                "Database connection attempt %d/%d failed (%s); retrying in %.0fs",
                attempt,
                settings.db_connect_attempts,
                exc,
                settings.db_connect_retry_delay_s,
            )
            await asyncio.sleep(settings.db_connect_retry_delay_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(
    title="StudyCAT Quiz Engine",
    version="0.1.0-mvp",
    description="Adaptive quiz engine using Unidimensional/Multidimensional IRT models",
    lifespan=lifespan
)

app.include_router(routers.router, prefix="/v1")
