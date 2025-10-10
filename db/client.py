import os
from prisma import Prisma
from dotenv import load_dotenv

load_dotenv()  # loads DATABASE_URL from .env for local dev

db = Prisma()  # uses DATABASE_URL by default
