"""
Hardcoded version of core orchestration for exposing endpoints without database dependencies.

This version returns hardcoded data to unblock frontend development while the full
database integration is being completed.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PublicItem:
    item_id: str
    skill: str
    stem: str
    options: List[str]


# Hardcoded sample data
SAMPLE_ITEMS = [
    PublicItem(
        item_id="item_001",
        skill="algebra",
        stem="What is the value of x in the equation 2x + 5 = 13?",
        options=["x = 4", "x = 6", "x = 8", "x = 9"]
    ),
    PublicItem(
        item_id="item_002", 
        skill="geometry",
        stem="What is the area of a circle with radius 5?",
        options=["25π", "10π", "50π", "100π"]
    ),
    PublicItem(
        item_id="item_003",
        skill="algebra", 
        stem="Solve for y: 3y - 7 = 14",
        options=["y = 7", "y = 9", "y = 21", "y = 3"]
    ),
    PublicItem(
        item_id="item_004",
        skill="geometry",
        stem="What is the perimeter of a square with side length 6?",
        options=["12", "24", "36", "18"]
    ),
    PublicItem(
        item_id="item_005",
        skill="algebra",
        stem="Factor the expression: x² - 9",
        options=["(x-3)(x+3)", "(x-9)(x+1)", "(x-3)²", "(x+3)²"]
    )
]

# Track attempt state in memory (simple dict for MVP)
_attempt_states: Dict[str, Dict] = {}


def _get_next_item_for_attempt(attempt_id: str) -> Optional[PublicItem]:
    """Get the next item for an attempt based on simple round-robin logic."""
    if attempt_id not in _attempt_states:
        _attempt_states[attempt_id] = {"current_index": 0, "answered_items": set()}
    
    state = _attempt_states[attempt_id]
    current_index = state["current_index"]
    
    # Simple round-robin through available items
    if current_index >= len(SAMPLE_ITEMS):
        return None
    
    item = SAMPLE_ITEMS[current_index]
    state["current_index"] += 1
    return item


def _get_theta_for_attempt(attempt_id: str) -> Dict[str, float]:
    """Return hardcoded theta values for skills."""
    if attempt_id not in _attempt_states:
        _attempt_states[attempt_id] = {"current_index": 0, "answered_items": set()}
    
    # Return some sample theta values
    return {
        "algebra": 0.5,
        "geometry": 0.3
    }


def _get_mastery_for_attempt(attempt_id: str) -> Dict[str, bool]:
    """Return hardcoded mastery values for skills."""
    if attempt_id not in _attempt_states:
        _attempt_states[attempt_id] = {"current_index": 0, "answered_items": set()}
    
    # Return some sample mastery values
    return {
        "algebra": True,
        "geometry": False
    }


def _is_attempt_finished(attempt_id: str) -> bool:
    """Check if attempt is finished based on simple logic."""
    if attempt_id not in _attempt_states:
        return False
    
    state = _attempt_states[attempt_id]
    return state["current_index"] >= len(SAMPLE_ITEMS)


# ---- Public API (matching original core.py interface) ----

async def init_attempt(
    attempt_id: str, 
    concepts: Optional[List[str]], 
    prior_mu: Optional[float], 
    prior_sigma2: Optional[float]
) -> Tuple[Dict[str, float], Optional[PublicItem]]:
    """
    Initialize an attempt and return the first item.
    
    Args:
        attempt_id: Unique identifier for the attempt
        concepts: List of concepts to test (ignored in hardcoded version)
        prior_mu: Prior mean (ignored in hardcoded version)
        prior_sigma2: Prior variance (ignored in hardcoded version)
    
    Returns:
        Tuple of (theta values, first item)
    """
    # Initialize attempt state
    _attempt_states[attempt_id] = {"current_index": 0, "answered_items": set()}
    
    # Get initial theta values
    theta = _get_theta_for_attempt(attempt_id)
    
    # Get first item
    next_item = _get_next_item_for_attempt(attempt_id)
    
    return theta, next_item


async def step_attempt(
    attempt_id: str,
    item_id: Optional[str],
    answer_index: Optional[int]
) -> Tuple[Dict[str, float], Dict[str, bool], Optional[PublicItem], bool]:
    """
    Process a response and return the next item.
    
    Args:
        attempt_id: Unique identifier for the attempt
        item_id: ID of the item that was answered (ignored in hardcoded version)
        answer_index: Index of the selected answer (ignored in hardcoded version)
    
    Returns:
        Tuple of (theta values, mastery values, next item, is_finished)
    """
    # Record the answered item if provided
    if item_id and attempt_id in _attempt_states:
        _attempt_states[attempt_id]["answered_items"].add(item_id)
    
    # Get current state
    theta = _get_theta_for_attempt(attempt_id)
    mastery = _get_mastery_for_attempt(attempt_id)
    
    # Check if finished
    is_finished = _is_attempt_finished(attempt_id)
    
    # Get next item if not finished
    next_item = None if is_finished else _get_next_item_for_attempt(attempt_id)
    
    return theta, mastery, next_item, is_finished
