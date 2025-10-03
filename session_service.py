"""
Session orchestration (business logic):
- Owns session state, calls IRT adapter, enforces stop rules.
- Keeps the web layer thin and swappable.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import uuid

from config import settings
from dataset import Dataset, ItemRecord
from irt_adapter import IRTAdapter

@dataclass
class SessionState:
    session_id: str
    concepts: List[str]
    max_items: int
    theta: Dict[str, float]
    asked: List[str] = field(default_factory=list)
    finished: bool = False

class SessionStore:
    """In-memory store (swap for Redis/DB when needed)."""
    def __init__(self) -> None:
        self._data: Dict[str, SessionState] = {}

    def create(self, state: SessionState) -> None:
        self._data[state.session_id] = state

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._data.get(session_id)

    def update(self, state: SessionState) -> None:
        self._data[state.session_id] = state

class SessionService:
    def __init__(self, dataset: Dataset, store: SessionStore, irt: IRTAdapter) -> None:
        self._dataset = dataset
        self._store = store
        self._irt = irt

    # ---- Flow ---------------------------------------------------------------
    def init_session(self, concepts: Optional[List[str]], max_items: Optional[int],
                     prior_mu: Optional[float], prior_sigma2: Optional[float]) -> SessionState:
        # Resolve concepts; default to all available
        if not concepts:
            all_items = self._dataset.items_by_concepts(None)
            unique_concepts = sorted({it.concept for it in all_items if it.concept})
            concepts = unique_concepts or ["general"]

        max_items = max_items or min(settings.MAX_SESSION_ITEMS, 20)
        theta = self._irt.init_theta(concepts, prior_mu or 0.0, prior_sigma2 or 1.0)

        state = SessionState(
            session_id=str(uuid.uuid4()),
            concepts=concepts,
            max_items=max_items,
            theta=theta,
        )
        self._store.create(state)
        return state

    def next_item(self, state: SessionState) -> Optional[ItemRecord]:
        if state.finished or len(state.asked) >= state.max_items:
            state.finished = True
            self._store.update(state)
            return None
        candidates = self._dataset.items_by_concepts(state.concepts)
        return self._irt.select_next(state.theta, candidates, set(state.asked))

    def step(self, session_id: str, item_id: Optional[str], answer_index: Optional[int]) -> dict:
        """
        PURPOSE:
        - Single-step call: optionally submit previous answer, then return next item.

        BEHAVIOR:
        - If (item_id, answer_index) provided: validate, update theta via adapter, mark asked.
        - Check stop conditions; if not finished, select next item.
        - Return updated theta, mastery heuristic, next_action, and next_item (if any).
        """
        state = self._require_session(session_id)

        # Submit previous answer if present
        if item_id is not None and answer_index is not None:
            item = self._dataset.get_item(item_id)
            if item is None:
                raise ValueError("Unknown item_id")
            if not (0 <= answer_index < len(item.options)):
                raise ValueError("answer_index is out of range for the item options")

            is_correct = (answer_index == item.correct_index)
            state.theta = self._irt.update_theta(state.theta, item, is_correct)
            if item_id not in state.asked:
                state.asked.append(item_id)

        # Stop rule (MVP): max_items reached
        if len(state.asked) >= state.max_items:
            state.finished = True
            self._store.update(state)
            next_item = None
        else:
            next_item = self.next_item(state)

        self._store.update(state)

        mastery = {c: (v >= 0.5) for c, v in state.theta.items()}  # placeholder heuristic
        return {
            "theta": state.theta,
            "mastery": mastery,
            "finished": state.finished,
            "next_item": next_item,
        }

    def state(self, session_id: str) -> SessionState:
        return self._require_session(session_id)

    # ---- internals -----------------------------------------------------------
    def _require_session(self, session_id: str) -> SessionState:
        st = self._store.get(session_id)
        if st is None:
            raise ValueError("Invalid session_id")
        return st
