#!/usr/bin/env python3
"""
generate_single_goal_data.py
----------------------------
Generate single-goal PPNL-style grid navigation datasets (JSONL).

Grid cell semantics
  0 = empty   1 = obstacle   2 = start   3 = goal

Actions (lowercase, space-separated): up  down  left  right
Coordinate convention: (row, col), row 0 = top row
  up   -> row - 1
  down -> row + 1
  left -> col - 1
  right-> col + 1

Usage
-----
  python scripts/generate_single_goal_data.py \
      --out_dir data/single_goal/6x6 \
      --grid_size 6 \
      --num_samples 1000 \
      --seed 42 \
      --n_obstacles_min 4 \
      --n_obstacles_max 6 \
      --split_name train
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from collections import deque
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
World = List[List[int]]
Position = Tuple[int, int]

CELL_EMPTY = 0
CELL_OBSTACLE = 1
CELL_START = 2
CELL_GOAL = 3

ACTIONS: List[str] = ["up", "down", "left", "right"]
DELTAS: Dict[str, Tuple[int, int]] = {
    "up":    (-1,  0),
    "down":  ( 1,  0),
    "left":  ( 0, -1),
    "right": ( 0,  1),
}


# ---------------------------------------------------------------------------
# BFS shortest path
# ---------------------------------------------------------------------------

def bfs_shortest_path(world: World, start: Position, goal: Position) -> Optional[List[str]]:
    """Return a shortest action list from start to goal, or None if unsolvable."""
    grid_size = len(world)
    visited = {start}
    queue: deque[Tuple[Position, List[str]]] = deque()
    queue.append((start, []))

    while queue:
        pos, path = queue.popleft()
        if pos == goal:
            return path
        r, c = pos
        for action in ACTIONS:
            dr, dc = DELTAS[action]
            nr, nc = r + dr, c + dc
            if 0 <= nr < grid_size and 0 <= nc < grid_size:
                if world[nr][nc] != CELL_OBSTACLE and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append(((nr, nc), path + [action]))
    return None


# ---------------------------------------------------------------------------
# Grid generation
# ---------------------------------------------------------------------------

def generate_instance(
    rng: random.Random,
    grid_size: int,
    n_obstacles: int,
) -> Optional[Dict]:
    """
    Generate one solvable grid instance.

    Returns a dict with all required fields, or None if a solvable instance
    could not be produced (caller should retry).
    """
    total_cells = grid_size * grid_size
    if n_obstacles + 2 > total_cells:          # need room for start + goal
        return None

    # Sample obstacle positions
    all_positions: List[Position] = [
        (r, c) for r in range(grid_size) for c in range(grid_size)
    ]
    rng.shuffle(all_positions)
    obstacle_positions = set(all_positions[:n_obstacles])
    remaining = [p for p in all_positions if p not in obstacle_positions]

    if len(remaining) < 2:
        return None

    rng.shuffle(remaining)
    start: Position = remaining[0]
    goal: Position = remaining[1]

    # Build world grid
    world: World = [[CELL_EMPTY] * grid_size for _ in range(grid_size)]
    for (r, c) in obstacle_positions:
        world[r][c] = CELL_OBSTACLE
    world[start[0]][start[1]] = CELL_START
    world[goal[0]][goal[1]] = CELL_GOAL

    # BFS
    path = bfs_shortest_path(world, start, goal)
    if path is None:
        return None

    target = " ".join(path)

    # ---- input_coord template ----
    obs_str = " ".join(f"({r},{c})" for r, c in sorted(obstacle_positions))
    input_coord = (
        f"grid_size: {grid_size} | "
        f"start: ({start[0]},{start[1]}) | "
        f"goal: ({goal[0]},{goal[1]}) | "
        f"obstacles: {obs_str if obs_str else 'none'}"
    )

    # ---- input_grid template ----
    symbol_map = {
        CELL_EMPTY:    ".",
        CELL_OBSTACLE: "#",
        CELL_START:    "S",
        CELL_GOAL:     "G",
    }
    grid_rows = []
    for r in range(grid_size):
        row_str = " ".join(symbol_map[world[r][c]] for c in range(grid_size))
        grid_rows.append(row_str)
    grid_display = "\n".join(grid_rows)
    input_grid = f"Grid {grid_size}x{grid_size}:\n{grid_display}\nOutput actions:"

    # ---- grid hash (for dedup) ----
    world_flat = [cell for row in world for cell in row]
    grid_hash = hashlib.md5(str(world_flat).encode()).hexdigest()[:12]

    return {
        "world": world,
        "start": list(start),
        "goal": list(goal),
        "obstacles": sorted([list(p) for p in obstacle_positions]),
        "n_obstacles": n_obstacles,
        "path": path,
        "target": target,
        "input_coord": input_coord,
        "input_grid": input_grid,
        "grid_hash": grid_hash,
    }


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------

def generate_dataset(
    out_path: str,
    grid_size: int,
    num_samples: int,
    seed: int,
    n_obstacles_min: int,
    n_obstacles_max: int,
    split_name: str,
    max_retries: int = 100,
) -> None:
    rng = random.Random(seed)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    seen_hashes: set = set()
    records = []
    attempts = 0

    while len(records) < num_samples:
        attempts += 1
        if attempts > num_samples * max_retries:
            print(
                f"[WARNING] Could only generate {len(records)}/{num_samples} unique "
                f"solvable instances after {attempts} attempts.",
                file=sys.stderr,
            )
            break

        n_obs = rng.randint(n_obstacles_min, n_obstacles_max)
        inst = generate_instance(rng, grid_size, n_obs)
        if inst is None:
            continue
        if inst["grid_hash"] in seen_hashes:
            continue
        seen_hashes.add(inst["grid_hash"])

        idx = len(records)
        record = {
            "id": f"{split_name}_{idx:06d}",
            "grid_size": grid_size,
            "world": inst["world"],
            "input_coord": inst["input_coord"],
            "input_grid": inst["input_grid"],
            "target": inst["target"],
            "meta": {
                "start": inst["start"],
                "goal": inst["goal"],
                "obstacles": inst["obstacles"],
                "shortest_path_length": len(inst["path"]),
                "obstacle_count": inst["n_obstacles"],
                "grid_hash": inst["grid_hash"],
            },
        }
        records.append(record)

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(
        f"[generate] Wrote {len(records)} records to {out_path} "
        f"(seed={seed}, obstacles={n_obstacles_min}-{n_obstacles_max})"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate single-goal PPNL grid navigation datasets."
    )
    parser.add_argument("--out_dir",          type=str,  required=True,
                        help="Output directory (split file written inside it).")
    parser.add_argument("--grid_size",        type=int,  default=6)
    parser.add_argument("--num_samples",      type=int,  default=1000)
    parser.add_argument("--seed",             type=int,  default=42)
    parser.add_argument("--n_obstacles_min",  type=int,  default=4)
    parser.add_argument("--n_obstacles_max",  type=int,  default=6)
    parser.add_argument("--split_name",       type=str,  default="train",
                        help="Name of the split (e.g. train, valid, test_iid). "
                             "Output file will be <out_dir>/<split_name>.jsonl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = os.path.join(args.out_dir, f"{args.split_name}.jsonl")
    generate_dataset(
        out_path=out_path,
        grid_size=args.grid_size,
        num_samples=args.num_samples,
        seed=args.seed,
        n_obstacles_min=args.n_obstacles_min,
        n_obstacles_max=args.n_obstacles_max,
        split_name=args.split_name,
    )


if __name__ == "__main__":
    main()
