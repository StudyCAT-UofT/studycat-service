"""
TODO: Replace this with the actual Prisma client.

Prisma client bootstrap.

LIFECYCLE:
- FastAPI lifespan connects/disconnects a single shared client instance.
"""
from __future__ import annotations
import os
from prisma import Prisma
from dotenv import load_dotenv

load_dotenv()  # loads DATABASE_URL for local dev

db = Prisma(log_queries=bool(os.getenv("PRISMA_LOG_QUERIES", "0") == "1"))
