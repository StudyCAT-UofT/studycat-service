"""
Singleton Prisma client for the application.

Loads DATABASE_URL from the .env file (local dev) and exposes a single
`db` instance to be shared across all database operations.
"""
from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()  # loads DATABASE_URL from .env for local dev

db = Prisma()  # uses DATABASE_URL by default
