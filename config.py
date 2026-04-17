from __future__ import annotations

from typing import Dict, Tuple

# ─── Season system ────────────────────────────────────────────────────────────

SEASON_CYCLE: int = 100  # ticks per full year

# Each season occupies a 25-tick window within the cycle.
_SEASON_RANGES: Dict[str, Tuple[int, int]] = {
    "Spring": (0, 25),
    "Summer": (25, 50),
    "Autumn": (50, 75),
    "Winter": (75, 100),
}

SEASON_EMOJIS: Dict[str, str] = {
    "Spring": "🌱",
    "Summer": "☀️",
    "Autumn": "🍂",
    "Winter": "❄️",
}

# Plant reproduction rate multiplier per season.
_PLANT_SEASON_MULTIPLIERS: Dict[str, float] = {
    "Spring": 1.5,
    "Summer": 0.8,
    "Autumn": 1.2,
    "Winter": 0.3,
}

# Extra energy drained from every animal per tick during winter.
_ANIMAL_WINTER_EXTRA_COST: int = 1

# ─── Parameter presets ────────────────────────────────────────────────────────

PRESETS: Dict[str, dict] = {
    "stable": {
        "description": "Stable ecosystem — all three species coexist long-term",
        "PLANT_REPRODUCTION_CHANCE": 0.25,
        "PLANT_MAX_AGE": 40,
        "HERBIVORE_INITIAL_ENERGY": 20,
        "HERBIVORE_CHILD_ENERGY": 15,
        "HERBIVORE_ENERGY_GAIN": 15,
        "HERBIVORE_REPRODUCTION_THRESHOLD": 25,
        "HERBIVORE_REPRODUCTION_CHANCE": 0.20,
        "HERBIVORE_REPRODUCTION_COST": 8,
        "HERBIVORE_MAX_AGE": 50,
        "CARNIVORE_INITIAL_ENERGY": 30,
        "CARNIVORE_CHILD_ENERGY": 20,
        "CARNIVORE_ENERGY_GAIN": 20,
        "CARNIVORE_REPRODUCTION_THRESHOLD": 35,
        "CARNIVORE_REPRODUCTION_CHANCE": 0.15,
        "CARNIVORE_REPRODUCTION_COST": 15,
        "CARNIVORE_MAX_AGE": 60,
    },
    "balanced": {
        "description": "Balanced ecosystem — moderate predator pressure",
        "PLANT_REPRODUCTION_CHANCE": 0.20,
        "PLANT_MAX_AGE": 35,
        "HERBIVORE_INITIAL_ENERGY": 18,
        "HERBIVORE_CHILD_ENERGY": 12,
        "HERBIVORE_ENERGY_GAIN": 12,
        "HERBIVORE_REPRODUCTION_THRESHOLD": 22,
        "HERBIVORE_REPRODUCTION_CHANCE": 0.18,
        "HERBIVORE_REPRODUCTION_COST": 8,
        "HERBIVORE_MAX_AGE": 50,
        "CARNIVORE_INITIAL_ENERGY": 28,
        "CARNIVORE_CHILD_ENERGY": 20,
        "CARNIVORE_ENERGY_GAIN": 18,
        "CARNIVORE_REPRODUCTION_THRESHOLD": 38,
        "CARNIVORE_REPRODUCTION_CHANCE": 0.12,
        "CARNIVORE_REPRODUCTION_COST": 18,
        "CARNIVORE_MAX_AGE": 60,
    },
    "intense": {
        "description": "Intense competition — dramatic population cycles with occasional crashes",
        "PLANT_REPRODUCTION_CHANCE": 0.15,
        "PLANT_MAX_AGE": 30,
        "HERBIVORE_INITIAL_ENERGY": 15,
        "HERBIVORE_CHILD_ENERGY": 10,
        "HERBIVORE_ENERGY_GAIN": 12,
        "HERBIVORE_REPRODUCTION_THRESHOLD": 20,
        "HERBIVORE_REPRODUCTION_CHANCE": 0.18,
        "HERBIVORE_REPRODUCTION_COST": 6,
        "HERBIVORE_MAX_AGE": 45,
        "CARNIVORE_INITIAL_ENERGY": 25,
        "CARNIVORE_CHILD_ENERGY": 18,
        "CARNIVORE_ENERGY_GAIN": 18,
        "CARNIVORE_REPRODUCTION_THRESHOLD": 35,
        "CARNIVORE_REPRODUCTION_CHANCE": 0.12,
        "CARNIVORE_REPRODUCTION_COST": 16,
        "CARNIVORE_MAX_AGE": 55,
    },
}

# ─── Active configuration (module-level state) ────────────────────────────────

_active: dict = dict(PRESETS["stable"])
_active_preset_name: str = "stable"


def load_preset(name: str) -> None:
    """Activate a named preset.  Call this before organisms are created."""
    global _active, _active_preset_name
    if name not in PRESETS:
        raise ValueError(
            f"Unknown preset '{name}'. Available presets: {list(PRESETS.keys())}"
        )
    _active = dict(PRESETS[name])
    _active_preset_name = name


def get(key: str):
    """Return the current value of a simulation parameter."""
    return _active[key]


def active_preset_name() -> str:
    """Return the name of the currently active preset."""
    return _active_preset_name


# ─── Season helpers ───────────────────────────────────────────────────────────

def get_current_season(tick_count: int) -> str:
    """Return the season name for the given tick count."""
    phase = tick_count % SEASON_CYCLE
    for season, (start, end) in _SEASON_RANGES.items():
        if start <= phase < end:
            return season
    return "Winter"


def get_plant_reproduction_chance(tick_count: int) -> float:
    """Return the season-adjusted plant reproduction probability."""
    season = get_current_season(tick_count)
    return _active["PLANT_REPRODUCTION_CHANCE"] * _PLANT_SEASON_MULTIPLIERS[season]


def get_animal_extra_energy_cost(tick_count: int) -> int:
    """Return extra per-tick energy cost imposed by winter (0 outside winter, 1 in winter)."""
    if get_current_season(tick_count) == "Winter":
        return _ANIMAL_WINTER_EXTRA_COST
    return 0


# ─── Diagnostics ──────────────────────────────────────────────────────────────

def energy_flow_summary() -> str:
    """Return a human-readable summary of the current energy-flow balance."""
    herb_feeds = _active["HERBIVORE_REPRODUCTION_THRESHOLD"] / _active["HERBIVORE_ENERGY_GAIN"]
    carn_hunts = _active["CARNIVORE_REPRODUCTION_THRESHOLD"] / _active["CARNIVORE_ENERGY_GAIN"]
    return (
        f"Preset : {_active_preset_name}\n"
        f"  Plant repro chance         : {_active['PLANT_REPRODUCTION_CHANCE']:.0%}\n"
        f"  Herbivore feeds to reproduce: {herb_feeds:.1f}\n"
        f"  Carnivore hunts to reproduce: {carn_hunts:.1f}"
    )
