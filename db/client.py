from dotenv import load_dotenv
from prisma import Prisma

load_dotenv()  # loads DATABASE_URL from .env for local dev

db = Prisma()  # uses DATABASE_URL by default
