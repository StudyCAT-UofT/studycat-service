"""
Dataset adapter (tiny):
- Loads the bank once, exposes item lookup & concept filtering.
- Keeps IRT params server-side.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import pandas as pd

from config import settings
from dataset_loader import (
    load_dataset,
    DatasetValidationError,
    DEFAULT_OPTION_LABELS,
)

OPTION_LABELS: Tuple[str, ...] = DEFAULT_OPTION_LABELS
_CORRECT_INDEX_COLUMN = "__correct_index"
_REQUIRED_COLUMNS = [
    "Module",
    "Question_ID",
    "Stem",
    "Response_A",
    "Justification_A",
    "Response_B",
    "Justification_B",
    "Response_C",
    "Justification_C",
    "Response_D",
    "Justification_D",
    "IRT_a",
    "IRT_b",
    "IRT_c",
]


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


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    return False


def _safe_str(value: Any) -> Optional[str]:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _option_text(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _float_or_none(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> Optional[int]:
    if _is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_average(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.endswith("%"):
            try:
                return float(stripped.rstrip("%")) / 100.0
            except ValueError:
                return None
        try:
            as_float = float(stripped)
        except ValueError:
            return None
        return as_float / 100.0 if as_float > 1.0 else as_float
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric / 100.0 if numeric > 1.0 else numeric


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
        return load_dataset(
            path,
            required_columns=_REQUIRED_COLUMNS,
            derive_correct_from_bold=True,
            option_labels=OPTION_LABELS,
            correct_index_column=_CORRECT_INDEX_COLUMN,
        )

    def _index(self, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            item_id = _safe_str(row.get("Question_ID"))
            if item_id is None:
                raise DatasetValidationError(
                    f"Missing Question_ID for row: {row.to_dict()}"
                )

            correct_index_value = row.get(_CORRECT_INDEX_COLUMN)
            correct_index = _int_or_none(correct_index_value)
            if correct_index is None:
                raise DatasetValidationError(
                    f"Missing correct index for Question_ID={item_id}"
                )

            options = [_option_text(row.get(f"Response_{label}")) for label in OPTION_LABELS]
            concept = _safe_str(row.get("Module"))

            metadata: Dict[str, Any] = {
                "reference": _safe_str(row.get("Reference")),
                "bloom_category": _safe_str(row.get("Bloom_Cat")),
                "figure": _safe_str(row.get("Figure")),
                "ptbi": _float_or_none(row.get("PtBi")),
                "average_correct": _parse_average(row.get("Average")),
                "attempts": _int_or_none(row.get("Attempts")),
                "correct_label": OPTION_LABELS[correct_index],
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}

            justifications = {
                label: text
                for label in OPTION_LABELS
                if (text := _safe_str(row.get(f"Justification_{label}"))) is not None
            }
            if justifications:
                metadata["justifications"] = justifications
            if concept:
                metadata.setdefault("module", concept)

            rec = ItemRecord(
                item_id=str(item_id),
                stem=_safe_str(row.get("Stem")) or "",
                options=options,
                correct_index=correct_index,
                concept=concept,
                irt_a=_float_or_none(row.get("IRT_a")),
                irt_b=_float_or_none(row.get("IRT_b")),
                irt_c=_float_or_none(row.get("IRT_c")),
                metadata=metadata,
            )
            self._by_id[rec.item_id] = rec

    # ---- Public helpers --------------------------------------------------
    def get_item(self, item_id: str) -> ItemRecord | None:
        _ = self.df
        return self._by_id.get(item_id)

    def items_by_concepts(self, concepts: Optional[list[str]]) -> list[ItemRecord]:
        _ = self.df
        if not concepts:
            return list(self._by_id.values())
        cs = set(concepts)
        return [it for it in self._by_id.values() if it.concept in cs]
