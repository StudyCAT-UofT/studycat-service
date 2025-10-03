"""
Centralized settings. Keep it tiny:
- DATASET_PATH: where the item bank is stored (CSV/XLSX).
- MAX_SESSION_ITEMS: guardrail for session length.
"""
from pathlib import Path
from pydantic import BaseModel, Field

class Settings(BaseModel):
    DATASET_PATH: Path = Field(default=Path("../../data/utsc-utoronto-ca-2025-09-22_combine.xlsx"))
    MAX_SESSION_ITEMS: int = 30
    CORS_ORIGINS: list[str] = []  # add frontend origin(s) if needed

settings = Settings()
