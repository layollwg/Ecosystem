#!/usr/bin/env python3
"""
evaluate_executor.py
--------------------
Evaluate predicted action sequences against gold targets using a minimal
single-goal PPNL executor.

Executor semantics
  - Apply actions from start position.
  - Out-of-bounds or hitting an obstacle => infeasible.
  - Success = final position equals goal.
  - Optimal  = success AND len(pred_actions) <= len(gold_actions)
    (counting individual action tokens, not characters).

Aggregated metrics reported
  - Success Rate  (fraction of samples where agent reached goal)
  - Feasibility   (fraction of samples with no illegal move)
  - Optimality    (fraction of samples that are both successful and optimal)
  - ParseRate     (fraction of samples where at least one action was extracted)

Usage — evaluate a predictions JSONL
--------------------------------------
  python scripts/evaluate_executor.py \
      --predictions outputs/t5-small/predictions.jsonl \
      --output      outputs/t5-small/metrics.json

  Each line in predictions.jsonl must contain at least:
    "world"  : 2-D list[int]   (grid with 0/1/2/3 cell values)
    "target" : str             (gold action sequence, space-separated)
    "pred"   : str             (model output / predicted action sequence)

  Optional fields:
    "id"     : str             (for per-sample output)

Usage — quick smoke test (no file, pure Python)
------------------------------------------------
  python scripts/evaluate_executor.py --demo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CELL_OBSTACLE = 1
CELL_START    = 2
CELL_GOAL     = 3

VALID_ACTIONS = {"up", "down", "left", "right"}

DELTAS: Dict[str, Tuple[int, int]] = {
    "up":    (-1,  0),
    "down":  ( 1,  0),
    "left":  ( 0, -1),
    "right": ( 0,  1),
}

_ACTION_PATTERN = re.compile(r"\b(up|down|left|right)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Action extraction
# ---------------------------------------------------------------------------

def extract_actions(text: str) -> List[str]:
    """
    Extract an ordered list of valid action tokens from free-form text.

    All tokens are lowercased.  Tokens outside {up, down, left, right}
    are silently discarded.

    Examples
    --------
    >>> extract_actions("The path is: up, right, right, down.")
    ['up', 'right', 'right', 'down']
    >>> extract_actions("UP DOWN LEFT")
    ['up', 'down', 'left']
    >>> extract_actions("no valid actions here")
    []
    """
    return [m.group(0).lower() for m in _ACTION_PATTERN.finditer(text)]


# ---------------------------------------------------------------------------
# Single-goal executor
# ---------------------------------------------------------------------------

def run_point_sg_executor(
    world: List[List[int]],
    pred_text: str,
    gold_text: str,
) -> Dict[str, object]:
    """
    Execute predicted actions on `world` and return per-sample metrics.

    Parameters
    ----------
    world     : 2-D list[int] with CELL_* semantics.
    pred_text : Raw model output (will be parsed with extract_actions).
    gold_text : Gold action sequence (space-separated lowercase tokens).

    Returns
    -------
    dict with keys:
      success  (bool)  – agent reached goal cell
      feasible (bool)  – no out-of-bounds or obstacle collision occurred
      optimal  (bool)  – success and len(pred) <= len(gold)
      parsed   (bool)  – at least one action token was extracted
      pred_actions (list[str])
      gold_actions (list[str])
      fail_type    (str | None) – "out_of_bounds" | "hit_obstacle" |
                                   "not_reach_goal" | "parse_empty" | None
      steps_taken  (int)
    """
    grid_size = len(world)

    # Locate start and goal
    start: Optional[Tuple[int, int]] = None
    goal:  Optional[Tuple[int, int]] = None
    for r in range(grid_size):
        for c in range(grid_size):
            if world[r][c] == CELL_START:
                start = (r, c)
            elif world[r][c] == CELL_GOAL:
                goal = (r, c)

    if start is None or goal is None:
        raise ValueError("world must contain exactly one start (2) and one goal (3) cell.")

    pred_actions = extract_actions(pred_text)
    gold_actions = extract_actions(gold_text) if gold_text else gold_text.split()

    if not pred_actions:
        return {
            "success":      False,
            "feasible":     False,
            "optimal":      False,
            "parsed":       False,
            "pred_actions": [],
            "gold_actions": gold_actions,
            "fail_type":    "parse_empty",
            "steps_taken":  0,
        }

    # Simulate
    r, c = start
    feasible = True
    fail_type: Optional[str] = None
    steps = 0

    for action in pred_actions:
        if action not in VALID_ACTIONS:
            continue  # already filtered by extract_actions; guard anyway
        dr, dc = DELTAS[action]
        nr, nc = r + dr, c + dc
        steps += 1

        if not (0 <= nr < grid_size and 0 <= nc < grid_size):
            feasible  = False
            fail_type = "out_of_bounds"
            break

        if world[nr][nc] == CELL_OBSTACLE:
            feasible  = False
            fail_type = "hit_obstacle"
            break

        r, c = nr, nc

    success = feasible and (r, c) == goal
    if not success and fail_type is None:
        fail_type = "not_reach_goal"

    optimal = success and len(pred_actions) <= len(gold_actions)

    return {
        "success":      success,
        "feasible":     feasible,
        "optimal":      optimal,
        "parsed":       True,
        "pred_actions": pred_actions,
        "gold_actions": gold_actions,
        "fail_type":    fail_type,
        "steps_taken":  steps,
    }


# ---------------------------------------------------------------------------
# Metric aggregation over a dataset
# ---------------------------------------------------------------------------

def aggregate_metrics(results: List[Dict]) -> Dict[str, float]:
    """
    Aggregate per-sample executor results into dataset-level metrics.

    Parameters
    ----------
    results : list of dicts returned by run_point_sg_executor.

    Returns
    -------
    dict with 'success_rate', 'feasibility', 'optimality', 'parse_rate',
    and optional 'fail_type_counts'.
    """
    n = len(results)
    if n == 0:
        return {"success_rate": 0.0, "feasibility": 0.0, "optimality": 0.0, "parse_rate": 0.0}

    success   = sum(1 for r in results if r["success"])
    feasible  = sum(1 for r in results if r["feasible"])
    optimal   = sum(1 for r in results if r["optimal"])
    parsed    = sum(1 for r in results if r["parsed"])

    fail_type_counts: Dict[str, int] = {}
    for r in results:
        ft = r.get("fail_type")
        if ft is not None:
            fail_type_counts[ft] = fail_type_counts.get(ft, 0) + 1

    return {
        "n_samples":       n,
        "success_rate":    success  / n,
        "feasibility":     feasible / n,
        "optimality":      optimal  / n,
        "parse_rate":      parsed   / n,
        "fail_type_counts": fail_type_counts,
    }


# ---------------------------------------------------------------------------
# Evaluate a predictions JSONL file
# ---------------------------------------------------------------------------

def evaluate_file(
    predictions_path: str,
    output_path: Optional[str],
    save_per_sample: bool = False,
) -> Dict:
    """
    Read a predictions JSONL and return aggregated metrics.

    Each line must contain 'world', 'target', and 'pred' fields.
    """
    results: List[Dict] = []
    per_sample: List[Dict] = []

    with open(predictions_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            world  = rec["world"]
            target = rec["target"]
            pred   = rec.get("pred", "")

            res = run_point_sg_executor(world, pred, target)
            results.append(res)

            if save_per_sample:
                per_sample.append({
                    "id":          rec.get("id", str(i)),
                    "success":     res["success"],
                    "feasible":    res["feasible"],
                    "optimal":     res["optimal"],
                    "parsed":      res["parsed"],
                    "fail_type":   res["fail_type"],
                    "pred":        pred,
                    "target":      target,
                    "pred_actions": res["pred_actions"],
                    "gold_actions": res["gold_actions"],
                })

    metrics = aggregate_metrics(results)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        out = {"metrics": metrics}
        if save_per_sample:
            out["per_sample"] = per_sample  # type: ignore[assignment]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"[evaluate_executor] Results written to {output_path}")

    # Always print summary
    print("\n========== Evaluation Results ==========")
    print(f"  Samples      : {metrics['n_samples']}")
    print(f"  ParseRate    : {metrics['parse_rate']:.4f}")
    print(f"  Success Rate : {metrics['success_rate']:.4f}")
    print(f"  Feasibility  : {metrics['feasibility']:.4f}")
    print(f"  Optimality   : {metrics['optimality']:.4f}")
    if metrics.get("fail_type_counts"):
        print("  Fail types   :")
        for ft, cnt in sorted(metrics["fail_type_counts"].items()):
            print(f"    {ft}: {cnt}")
    print("=========================================\n")

    return metrics


# ---------------------------------------------------------------------------
# Quick demo (smoke test, no file I/O needed)
# ---------------------------------------------------------------------------

def _run_demo() -> None:
    """Self-contained demo that exercises the executor and prints results."""
    # 4x4 world:  S . . .
    #             . # . .
    #             . . . .
    #             . . . G
    world = [
        [CELL_START, 0, 0, 0],
        [0,          1, 0, 0],
        [0,          0, 0, 0],
        [0,          0, 0, CELL_GOAL],
    ]
    # right right right down down down  (avoids the obstacle at (1,1))
    gold = "right right right down down down"   # one valid path (length 6)

    # Case 1: gold path → should be success + feasible
    r1 = run_point_sg_executor(world, gold, gold)
    print(f"[demo] gold path  => success={r1['success']}  feasible={r1['feasible']}  optimal={r1['optimal']}")
    assert r1["success"]  is True,  "gold path should succeed"
    assert r1["feasible"] is True,  "gold path should be feasible"
    assert r1["optimal"]  is True,  "gold path should be optimal vs itself"

    # Case 2: bad path (all 'up') → out of bounds
    bad = "up up up up up"
    r2 = run_point_sg_executor(world, bad, gold)
    print(f"[demo] bad path   => success={r2['success']}  feasible={r2['feasible']}  fail={r2['fail_type']}")
    assert r2["success"]  is False, "bad path should not succeed"
    assert r2["feasible"] is False, "bad path should be infeasible"

    # Case 3: empty prediction
    r3 = run_point_sg_executor(world, "no valid tokens here", gold)
    print(f"[demo] empty pred => success={r3['success']}  parsed={r3['parsed']}")
    assert r3["parsed"]  is False
    assert r3["success"] is False

    print("[demo] All assertions passed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate predicted action sequences with the single-goal executor."
    )
    parser.add_argument("--predictions", type=str,
                        help="Input predictions JSONL (each line: world, target, pred).")
    parser.add_argument("--output",      type=str, default=None,
                        help="Path to write metrics JSON output.")
    parser.add_argument("--per_sample",  action="store_true",
                        help="Include per-sample results in output JSON.")
    parser.add_argument("--demo",        action="store_true",
                        help="Run built-in smoke test demo.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.demo:
        _run_demo()
        return

    if not args.predictions:
        print("[evaluate_executor] ERROR: --predictions is required (or use --demo).",
              file=sys.stderr)
        sys.exit(1)

    evaluate_file(
        predictions_path=args.predictions,
        output_path=args.output,
        save_per_sample=args.per_sample,
    )


if __name__ == "__main__":
    main()
