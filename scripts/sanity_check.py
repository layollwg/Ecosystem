#!/usr/bin/env python3
"""
sanity_check.py
---------------
Verify the correctness of generated datasets by running the single-goal
executor on a sample of records and asserting expected outcomes.

Checks performed
  1. Gold target => Success=1, Feasible=1, Optimal=1   (for each sampled record)
  2. Bad action sequence (all 'up') => Infeasible or not-reach-goal

Usage
-----
  python scripts/sanity_check.py \
      --data data/single_goal/6x6/train.jsonl \
      --n_samples 10

  python scripts/sanity_check.py \
      --data data/single_goal/6x6_dense/test_ood.jsonl \
      --n_samples 10
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Import executor from sibling script
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS_DIR))
from evaluate_executor import run_point_sg_executor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: str, n_samples: int, seed: int) -> List[Dict]:
    """Load all records and return a random sample of size n_samples."""
    records: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise ValueError(f"No records found in {path}")
    rng = random.Random(seed)
    n = min(n_samples, len(records))
    return rng.sample(records, n)


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

def check_gold_paths(records: List[Dict], verbose: bool) -> bool:
    """
    Assert that running the gold target on each record yields
    Success=1, Feasible=1, Optimal=1.

    Returns True if all checks pass.
    """
    ok = True
    for rec in records:
        rid   = rec.get("id", "?")
        world = rec["world"]
        gold  = rec["target"]

        res = run_point_sg_executor(world, gold, gold)

        if verbose:
            print(
                f"  [{rid}]  gold path  "
                f"success={int(res['success'])}  "
                f"feasible={int(res['feasible'])}  "
                f"optimal={int(res['optimal'])}  "
                f"steps={res['steps_taken']}"
            )

        if not res["success"]:
            print(f"  [FAIL] {rid}: gold path did not reach goal!", file=sys.stderr)
            ok = False
        if not res["feasible"]:
            print(f"  [FAIL] {rid}: gold path is infeasible!", file=sys.stderr)
            ok = False
        if not res["optimal"]:
            print(f"  [FAIL] {rid}: gold path is not optimal!", file=sys.stderr)
            ok = False

    return ok


def check_bad_paths(records: List[Dict], verbose: bool) -> bool:
    """
    Assert that an obviously wrong action sequence ('up up up …') results in
    infeasibility or not-reach-goal (i.e. NOT success=1).

    Returns True if all checks pass.
    """
    # Repeated 'up' will either go out-of-bounds or stop at the wrong cell.
    BAD_SEQUENCE = " ".join(["up"] * 20)

    ok = True
    for rec in records:
        rid   = rec.get("id", "?")
        world = rec["world"]
        gold  = rec["target"]

        res = run_point_sg_executor(world, BAD_SEQUENCE, gold)

        if verbose:
            print(
                f"  [{rid}]  bad path   "
                f"success={int(res['success'])}  "
                f"feasible={int(res['feasible'])}  "
                f"fail_type={res['fail_type']}"
            )

        if res["success"]:
            print(f"  [FAIL] {rid}: bad path unexpectedly succeeded!", file=sys.stderr)
            ok = False

    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanity-check single-goal PPNL datasets using the executor."
    )
    parser.add_argument("--data",      type=str, required=True,
                        help="Path to a JSONL dataset file.")
    parser.add_argument("--n_samples", type=int, default=20,
                        help="Number of records to sample for checks.")
    parser.add_argument("--seed",      type=int, default=0)
    parser.add_argument("--verbose",   action="store_true",
                        help="Print per-sample executor results.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"\n[sanity_check] Loading {args.n_samples} samples from: {args.data}")
    try:
        records = load_jsonl(args.data, args.n_samples, args.seed)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[sanity_check] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[sanity_check] Sampled {len(records)} records.\n")

    # --- Check 1: gold paths ---
    print("--- Check 1: Gold target => Success=1, Feasible=1, Optimal=1 ---")
    gold_ok = check_gold_paths(records, verbose=args.verbose)
    if gold_ok:
        print(f"  PASSED ({len(records)} records)\n")
    else:
        print("  FAILED\n")

    # --- Check 2: bad paths ---
    print("--- Check 2: Bad sequence ('up'*20) => NOT success ---")
    bad_ok = check_bad_paths(records, verbose=args.verbose)
    if bad_ok:
        print(f"  PASSED ({len(records)} records)\n")
    else:
        print("  FAILED\n")

    # --- Summary ---
    if gold_ok and bad_ok:
        print("[sanity_check] All checks PASSED ✓")
    else:
        print("[sanity_check] Some checks FAILED ✗", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
