#!/usr/bin/env python3
"""
data_preprocess.py
------------------
Preprocess / convert raw JSONL dataset files for the single-goal PPNL pipeline.

If `generate_single_goal_data.py` already produced the final schema this script
acts as a validator + pass-through.  You can also use it to:
  - re-derive input templates from raw world grids
  - filter/deduplicate records
  - merge multiple splits

Usage (pass-through / validate)
--------------------------------
  python scripts/data_preprocess.py \
      --input  data/single_goal/6x6/train.jsonl \
      --output data/single_goal/6x6/train_clean.jsonl

Usage (re-derive templates from world grids)
---------------------------------------------
  python scripts/data_preprocess.py \
      --input  raw/train.jsonl \
      --output data/single_goal/6x6/train.jsonl \
      --rederive
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Cell / action constants (keep in sync with generate_single_goal_data.py)
# ---------------------------------------------------------------------------
CELL_EMPTY    = 0
CELL_OBSTACLE = 1
CELL_START    = 2
CELL_GOAL     = 3

SYMBOL_MAP = {
    CELL_EMPTY:    ".",
    CELL_OBSTACLE: "#",
    CELL_START:    "S",
    CELL_GOAL:     "G",
}

REQUIRED_FIELDS = {"id", "grid_size", "world", "input_coord", "input_grid", "target", "meta"}
REQUIRED_META   = {"start", "goal", "obstacles", "shortest_path_length", "obstacle_count"}


# ---------------------------------------------------------------------------
# Template derivation helpers
# ---------------------------------------------------------------------------

def derive_input_coord(world: List[List[int]], grid_size: int) -> str:
    """Re-derive input_coord template from a world grid."""
    start: Optional[Tuple[int, int]] = None
    goal:  Optional[Tuple[int, int]] = None
    obstacles: List[Tuple[int, int]] = []

    for r in range(grid_size):
        for c in range(grid_size):
            v = world[r][c]
            if v == CELL_START:
                start = (r, c)
            elif v == CELL_GOAL:
                goal = (r, c)
            elif v == CELL_OBSTACLE:
                obstacles.append((r, c))

    obs_str = " ".join(f"({r},{c})" for r, c in sorted(obstacles))
    return (
        f"grid_size: {grid_size} | "
        f"start: ({start[0]},{start[1]}) | "
        f"goal: ({goal[0]},{goal[1]}) | "
        f"obstacles: {obs_str if obs_str else 'none'}"
    )


def derive_input_grid(world: List[List[int]], grid_size: int) -> str:
    """Re-derive input_grid template from a world grid."""
    rows = []
    for r in range(grid_size):
        rows.append(" ".join(SYMBOL_MAP[world[r][c]] for c in range(grid_size)))
    return f"Grid {grid_size}x{grid_size}:\n" + "\n".join(rows) + "\nOutput actions:"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_record(rec: Dict, idx: int) -> List[str]:
    """Return a list of validation error strings (empty = OK)."""
    errors: List[str] = []

    missing = REQUIRED_FIELDS - set(rec.keys())
    if missing:
        errors.append(f"[{idx}] Missing top-level fields: {missing}")
        return errors  # Can't proceed if world/meta absent

    meta = rec.get("meta", {})
    missing_meta = REQUIRED_META - set(meta.keys())
    if missing_meta:
        errors.append(f"[{idx}] Missing meta fields: {missing_meta}")

    # target: only valid action tokens
    target = rec.get("target", "")
    valid_actions = {"up", "down", "left", "right"}
    tokens = target.lower().split()
    bad = [t for t in tokens if t not in valid_actions]
    if bad:
        errors.append(f"[{idx}] target contains invalid tokens: {bad}")
    if not tokens:
        errors.append(f"[{idx}] target is empty")

    # world dimensions
    world = rec.get("world", [])
    gs = rec.get("grid_size", 0)
    if len(world) != gs or any(len(row) != gs for row in world):
        errors.append(f"[{idx}] world dimensions mismatch grid_size={gs}")

    return errors


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_file(
    input_path: str,
    output_path: str,
    rederive: bool,
    skip_invalid: bool,
) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    total = 0
    kept  = 0
    all_errors: List[str] = []

    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        for line in fin:
            line = line.strip()
            if not line:
                continue
            total += 1

            try:
                rec: Dict = json.loads(line)
            except json.JSONDecodeError as exc:
                all_errors.append(f"[{total}] JSON parse error: {exc}")
                if skip_invalid:
                    continue
                raise

            if rederive:
                gs    = rec.get("grid_size", len(rec.get("world", [])))
                world = rec.get("world", [])
                if world and gs:
                    rec["input_coord"] = derive_input_coord(world, gs)
                    rec["input_grid"]  = derive_input_grid(world, gs)

            errors = validate_record(rec, total)
            all_errors.extend(errors)

            if errors and not skip_invalid:
                print(
                    f"[data_preprocess] Validation error — stopping. "
                    f"Use --skip_invalid to continue past errors.",
                    file=sys.stderr,
                )
                for e in errors:
                    print(f"  {e}", file=sys.stderr)
                sys.exit(1)

            if errors and skip_invalid:
                continue

            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kept += 1

    print(f"[data_preprocess] {input_path} -> {output_path}")
    print(f"  total={total}  kept={kept}  errors={len(all_errors)}")
    if all_errors:
        print("[data_preprocess] First 10 errors:")
        for e in all_errors[:10]:
            print(f"  {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess / validate single-goal PPNL JSONL datasets."
    )
    parser.add_argument("--input",        type=str, required=True,
                        help="Input JSONL file.")
    parser.add_argument("--output",       type=str, required=True,
                        help="Output JSONL file.")
    parser.add_argument("--rederive",     action="store_true",
                        help="Re-derive input_coord and input_grid from world grids.")
    parser.add_argument("--skip_invalid", action="store_true",
                        help="Skip (drop) invalid records instead of failing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    process_file(
        input_path=args.input,
        output_path=args.output,
        rederive=args.rederive,
        skip_invalid=args.skip_invalid,
    )


if __name__ == "__main__":
    main()
