"""
Thin wrapper around the external IRT library.

WHAT:
- Hide vendor-specific APIs behind a tiny interface.
- Centralize theta init, update, and information/selection logic.

TODO:
- Replace stubs with real calls to the chosen 3PL library.
- Ensure thread-safety (single shared model vs per-request objects).
"""
from __future__ import annotations
from typing import Dict, List, Optional
import random

from dataset import ItemRecord

class IRTAdapter:
    def __init__(self, seed: Optional[int] = 42) -> None:
        # In real usage, initialize vendor model/configs here (once).
        self._rng = random.Random(seed)

    # ---- Theta lifecycle -----------------------------------------------------
    def init_theta(self, concepts: List[str], prior_mu: float = 0.0, prior_sigma2: float = 1.0) -> Dict[str, float]:
        """
        PURPOSE: Provide initial ability estimates per concept.
        TODO: call vendor API to sample or set prior means; here we return prior_mu.
        """
        return {c: float(prior_mu) for c in concepts}

    def update_theta(self, theta: Dict[str, float], item: ItemRecord, is_correct: bool) -> Dict[str, float]:
        """
        PURPOSE: Update theta given an item response.
        TODO: replace with vendor MAP/Bayes update using item (a,b,c) and response.
        CURRENT: placeholder ±0.1 on the item's concept.
        """
        concept = item.concept or next(iter(theta.keys()))
        step = 0.1 if is_correct else -0.1
        new_theta = dict(theta)
        new_theta[concept] = new_theta.get(concept, 0.0) + step
        return new_theta

    # ---- Selection -----------------------------------------------------------
    def information(self, theta: Dict[str, float], item: ItemRecord) -> float:
        """
        PURPOSE: Return Fisher information at current theta for this item.
        TODO: compute with vendor function under 3PL.
        CURRENT: constant (no-op) so selection falls back to random.
        """
        return 1.0

    def select_next(self, theta: Dict[str, float], candidates: List[ItemRecord], asked: set[str]) -> Optional[ItemRecord]:
        """
        PURPOSE: Choose the next item (ideally by max-information under 3PL).
        TODO: use vendor vectorized info and argmax; tie-break deterministically.
        CURRENT: random unasked item.
        """
        pool = [it for it in candidates if it.item_id not in asked]
        if not pool:
            return None
        return self._rng.choice(pool)
