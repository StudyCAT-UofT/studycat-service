"""
Dataset adapter (tiny):
- Loads the bank once, exposes item lookup & concept filtering.
- Keeps IRT params server-side.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd
from config import settings

@dataclass
class ItemRecord:
    item_id: str
    stem: str
    options: list[str]
    correct_index: int
    concept: str | None
    irt_a: float | None
    irt_b: float | None
    irt_c: float | None
    metadata: Dict[str, Any]

class Dataset:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or settings.DATASET_PATH
        self._df: Optional[pd.DataFrame] = None
        self._by_id: dict[str, ItemRecord] = {}

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = self._load(self._path)
            self._index(self._df)
        return self._df

    def _load(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() == ".xlsx":
            df = pd.read_excel(path, sheet_name=0)
        else:
            raise ValueError(f"Unsupported dataset format: {path.suffix}")
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def _index(self, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            opts = row.get("options")
            if isinstance(opts, str):
                options = [s.strip() for s in opts.split("|")]  # adapt to your format
            elif isinstance(opts, list):
                options = opts
            else:
                options = list(opts) if opts is not None else []

            rec = ItemRecord(
                item_id=str(row.get("item_id")),
                stem=str(row.get("stem", "")),
                options=options,
                correct_index=int(row.get("correct_index", -1)),
                concept=(str(row.get("concept")) if pd.notna(row.get("concept")) else None),
                irt_a=float(row.get("IRT_a")) if pd.notna(row.get("IRT_a")) else None,
                irt_b=float(row.get("IRT_b")) if pd.notna(row.get("IRT_b")) else None,
                irt_c=float(row.get("IRT_c")) if pd.notna(row.get("IRT_c")) else None,
                metadata={},
            )
            self._by_id[rec.item_id] = rec

    # ---- Public helpers ------------------------------------------------------
    def get_item(self, item_id: str) -> ItemRecord | None:
        _ = self.df
        return self._by_id.get(item_id)

    def items_by_concepts(self, concepts: Optional[list[str]]) -> list[ItemRecord]:
        _ = self.df
        if not concepts:
            return list(self._by_id.values())
        cs = set(concepts)
        return [it for it in self._by_id.values() if it.concept in cs]
