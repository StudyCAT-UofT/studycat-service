#!/usr/bin/env python3
# studycat_cli_adaptive.py
#
# CLI MVP using adaptivetesting (no fallbacks, no web server).
# - Imports follow the library's documented module structure.
# - Uses BayesModal (MAP) + maximum information criterion.
# - Interactive: mark each question Correct/Wrong, or use --simulate.

import argparse
import os
import sys
from typing import Optional

import numpy as np
import pandas as pd

# ---- adaptivetesting imports (as per PyPI docs) ----
from adaptivetesting.models import ItemPool, TestItem, AdaptiveTest
from adaptivetesting.implementations import TestAssembler
from adaptivetesting.math.estimators import BayesModal, NormalPrior
from adaptivetesting.math.item_selection import maximum_information_criterion

# --------------------- data loading --------------------------
REQUIRED_COLS = ["IRT_a", "IRT_b", "IRT_c"]

def load_bank(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    # Ensure required columns exist and are numeric
    for col in REQUIRED_COLS:
        if col not in df.columns:
            raise ValueError(f"Bank missing required column: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with missing IRT params
    df = df.dropna(subset=REQUIRED_COLS).reset_index(drop=True)

    # Add a stable index column for reference (and ID if Question_ID missing)
    df["__row_index__"] = df.index
    if "Question_ID" not in df.columns:
        df["Question_ID"] = df["__row_index__"].astype(int)

    return df

def apply_filters(df: pd.DataFrame, module_filter: Optional[str], bloom_filter: Optional[str]) -> pd.DataFrame:
    mask = np.ones(len(df), dtype=bool)
    if module_filter is not None:
        if "Module" not in df.columns:
            raise ValueError("You passed --module but the bank has no 'Module' column.")
        mask &= df["Module"].astype(str) == module_filter
    if bloom_filter is not None:
        if "Bloom_Cat" not in df.columns:
            raise ValueError("You passed --bloom but the bank has no 'Bloom_Cat' column.")
        mask &= df["Bloom_Cat"].astype(str) == bloom_filter
    return df.loc[mask].reset_index(drop=True)

def make_item_pool(df: pd.DataFrame) -> ItemPool:
    # adaptivetesting expects columns named a,b,c[,d]; add d=1.0 (3PL upper asymptote)
    items_df = pd.DataFrame({
        "a": df["IRT_a"].astype(float),
        "b": df["IRT_b"].astype(float),
        "c": df["IRT_c"].astype(float),
        "d": 1.0,  # 3PL => upper asymptote is 1.0
        # adaptivetesting expects the identifier column to be named "ids"
        "ids": df["Question_ID"].astype(int),
    })
    # Many versions expose load_from_dataframe:
    try:
        pool = ItemPool.load_from_dataframe(items_df)
    except AttributeError:
        # Fallback constructor signature (older versions): pass arrays explicitly
        pool = ItemPool.load_from_list(
            a=items_df["a"].to_list(),
            b=items_df["b"].to_list(),
            c=items_df["c"].to_list(),
            d=items_df["d"].to_list(),
            ids=items_df["ids"].to_list(),
        )
    return pool

# --------------------- CLI driver ----------------------------
def run_cli(
    bank_path: str,
    module_filter: Optional[str],
    bloom_filter: Optional[str],
    max_questions: int,
    theta_init: float,
    simulate: bool,
    seed: Optional[int],
):
    if simulate and seed is not None:
        np.random.seed(seed)

    df_full = load_bank(bank_path)
    df = apply_filters(df_full, module_filter, bloom_filter)
    if df.empty:
        raise ValueError("No items after applying filters. Relax filters or check column values.")

    item_pool = make_item_pool(df)

    # Build an AdaptiveTest via TestAssembler
    prior = NormalPrior(mean=0.0, sd=1.0)
    adaptive_test: AdaptiveTest = TestAssembler(
        item_pool=item_pool,
        simulation_id="studycat_cli_demo",
        participant_id="student_001",
        ability_estimator=BayesModal,                 # MAP estimation
        estimator_args={"prior": prior},
        item_selector=maximum_information_criterion,  # Max-Info
        simulation=False,
        debug=False,
    )

    # Override get_response to use CLI (no PsychoPy).
    def get_response(item: TestItem) -> int:
        # Map back to your bank metadata using Question_ID
        qid = getattr(item, "id", None)
        if qid is None:
            # if id missing, fall back to index match (rare)
            raise RuntimeError("Item has no 'id' attribute to map back to question metadata.")

        row = df[df["Question_ID"] == qid]
        if row.empty:
            print(f"(Warning) Could not find metadata for item id={qid}.")
            stem = ""
            a=b=c=0.0
        else:
            row = row.iloc[0]
            stem = str(row.get("Stem") or "")
            a = float(row["IRT_a"]); b = float(row["IRT_b"]); c = float(row["IRT_c"])

        turn = len(adaptive_test.test_results) + 1
        print(f"\nTurn {turn}: ASK QID={qid}  a={a:.3f} b={b:.2f} c={c:.2f}")
        print("STEM:", stem[:160].replace("\n", " "), "..." if len(stem) > 160 else "")

        if simulate:
            # Use current ability estimate from the adaptive test (if available),
            # else fall back to theta_init for the very first question.
            theta_now = getattr(adaptive_test, "ability_estimate", theta_init)
            # Compute 3PL probability manually; the package also uses this internally.
            p = c + (1.0 - c) / (1.0 + np.exp(-a * (theta_now - b)))
            is_correct = bool(np.random.rand() < p)
            print(f"[cli] Simulated correct={is_correct} (P={p:.2f})")
            return 1 if is_correct else 0
        else:
            while True:
                ans = input("Mark (c=correct, w=wrong, q=quit): ").strip().lower()
                if ans in ("c", "w", "q"):
                    break
            if ans == "q":
                print("[cli] Quit requested.")
                # Gracefully exit the process so results so far are printed.
                sys.exit(0)
            return 1 if ans == "c" else 0

    adaptive_test.get_response = get_response  # override

    print(f"[cli] Loaded items: {len(df)}  | adaptivetesting=YES")
    if module_filter or bloom_filter:
        print(f"[cli] Filters: {{'Module': {module_filter}, 'Bloom_Cat': {bloom_filter}}}")

    # Run until we hit max-questions or pool exhaustion or a precision target
    asked = 0
    while asked < max_questions and len(adaptive_test.item_pool.test_items) > 0:
        adaptive_test.run_test_once()   # shows next item, collects response via get_response
        asked += 1

        # ability estimate and SE are maintained by the test object
        theta = getattr(adaptive_test, "ability_estimate", None)
        se = getattr(adaptive_test, "standard_error", None)
        if theta is not None:
            print(f"[cli] theta -> {theta:.3f}" + (f"  (SE={se:.3f})" if se is not None else ""))

        # Optional early stop on precision:
        # if se is not None and se <= 0.30:
        #     print("[cli] Stopping: target precision reached.")
        #     break

    # Print summary
    print(f"\n[cli] Finished. asked={asked}, remaining_items={len(adaptive_test.item_pool.test_items)}")
    if getattr(adaptive_test, "ability_estimate", None) is not None:
        print(f"[cli] final theta={adaptive_test.ability_estimate:.6f}")
    if len(adaptive_test.test_results) > 0:
        # test_results is typically a list of (item_id, response, theta_before/after, etc.) depending on version
        print("[cli] results (first few rows):")
        try:
            import pandas as pd  # already imported
            # Coerce to DataFrame if it looks like a list of dicts/tuples
            print(pd.DataFrame(adaptive_test.test_results).head())
        except Exception:
            print(adaptive_test.test_results[:3])

# --------------------- main ----------------------------
def main():
    parser = argparse.ArgumentParser(description="StudyCAT CLI MVP (adaptivetesting-only)")
    parser.add_argument("--bank", type=str, required=True,
                        help="Path to Excel/CSV bank with IRT_a, IRT_b, IRT_c (and metadata)")
    parser.add_argument("--module", type=str, default=None,
                        help="Optional filter: Module exact match (e.g., 'Module 1 - L1 & 2')")
    parser.add_argument("--bloom", type=str, default=None,
                        help="Optional filter: Bloom category exact match (e.g., 'Application')")
    parser.add_argument("--max-questions", type=int, default=8, help="Max questions to ask")
    parser.add_argument("--theta-init", type=float, default=0.0, help="(Not strictly needed; MAP uses prior)")
    parser.add_argument("--simulate", action="store_true", help="Auto-simulate correctness")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed (used only with --simulate)")
    args = parser.parse_args()

    run_cli(
        bank_path=args.bank,
        module_filter=args.module,
        bloom_filter=args.bloom,
        max_questions=args.max_questions,
        theta_init=args.theta_init,
        simulate=args.simulate,
        seed=args.seed,
    )

if __name__ == "__main__":
    main()
