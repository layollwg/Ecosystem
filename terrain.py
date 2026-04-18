from __future__ import annotations

import math
import random
from enum import Enum
from typing import Dict, Tuple

Position = Tuple[int, int]

try:
    import noise  # type: ignore
except ImportError:
    noise = None  # type: ignore[assignment]


class TerrainType(Enum):
    WATER = 1
    SAND = 2
    DIRT = 3
    MOUNTAIN = 4


# Elevation thresholds (mapped from [-1.0, 1.0]).
WATER_THRESHOLD = -0.1
SAND_THRESHOLD = 0.1
MOUNTAIN_THRESHOLD = 0.6


def terrain_from_elevation(elevation: float) -> TerrainType:
    if elevation < WATER_THRESHOLD:
        return TerrainType.WATER
    if elevation < SAND_THRESHOLD:
        return TerrainType.SAND
    if elevation < MOUNTAIN_THRESHOLD:
        return TerrainType.DIRT
    return TerrainType.MOUNTAIN


def _fallback_fbm(x: float, y: float, octaves: int, seed: int) -> float:
    value = 0.0
    frequency = 1.0
    amplitude = 1.0
    total_amp = 0.0
    for i in range(octaves):
        phase = seed * (i + 1) * 0.0007
        wave = math.sin((x * frequency) + phase) * math.cos((y * frequency) - phase)
        value += wave * amplitude
        total_amp += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return (value / total_amp) if total_amp > 0 else 0.0


def generate_terrain_grid(
    grid_size: int,
    *,
    scale: float = 24.0,
    octaves: int = 4,
    persistence: float = 0.5,
    lacunarity: float = 2.0,
    seed: int | None = None,
) -> Dict[Position, TerrainType]:
    resolved_seed = seed if seed is not None else random.randint(0, 10000)
    effective_scale = scale if scale > 0 else 1.0
    terrain_grid: Dict[Position, TerrainType] = {}

    for x in range(grid_size):
        for y in range(grid_size):
            nx = x / effective_scale
            ny = y / effective_scale
            if noise is not None:
                elevation = float(
                    noise.pnoise2(
                        nx,
                        ny,
                        octaves=octaves,
                        persistence=persistence,
                        lacunarity=lacunarity,
                        repeatx=max(1, grid_size),
                        repeaty=max(1, grid_size),
                        base=resolved_seed,
                    )
                )
            else:
                elevation = _fallback_fbm(nx, ny, octaves, resolved_seed)
            terrain_grid[(x, y)] = terrain_from_elevation(elevation)

    return terrain_grid


def is_land_passable(terrain: TerrainType) -> bool:
    return terrain in (TerrainType.DIRT, TerrainType.SAND)


def is_plant_habitable(terrain: TerrainType) -> bool:
    return terrain in (TerrainType.DIRT, TerrainType.SAND)


def movement_multiplier(terrain: TerrainType) -> float:
    """Return terrain movement energy scale (finite) or infinity for impassable terrain."""
    if terrain == TerrainType.SAND:
        return 1.2
    if terrain == TerrainType.WATER:
        return float("inf")
    if terrain == TerrainType.MOUNTAIN:
        return float("inf")
    return 1.0
