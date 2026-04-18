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
# Spring and Autumn boosts are moderated to prevent grid over-saturation;
# Winter penalty is softened so plant populations can partially recover.
_PLANT_SEASON_MULTIPLIERS: Dict[str, float] = {
    "Spring": 1.2,
    "Summer": 0.9,
    "Autumn": 1.1,
    "Winter": 0.5,
}

# Extra energy drained from every animal per tick during winter.
# Set to 0 so that seasonal variation comes only from reduced plant growth,
# avoiding the compounding effect of simultaneous food shortage + energy drain
# that previously caused winter crashes.
_ANIMAL_WINTER_EXTRA_COST: int = 0

# ─── Parameter presets ────────────────────────────────────────────────────────

PRESETS: Dict[str, dict] = {
    "stable": {
        "description": "稳定生态——三种生物可长期共存",
        # Plants: moderate reproduction rate with shorter lifespan to prevent
        # grid over-saturation during spring booms.
        "PLANT_REPRODUCTION_CHANCE": 0.35,
        "PLANT_MAX_AGE": 20,
        # Herbivores: slightly lower energy gain and crowding guard prevent
        # population explosions when food is abundant.
        "HERBIVORE_INITIAL_ENERGY": 20,
        "HERBIVORE_CHILD_ENERGY": 12,
        "HERBIVORE_ENERGY_GAIN": 12,
        "HERBIVORE_REPRODUCTION_THRESHOLD": 20,
        "HERBIVORE_REPRODUCTION_CHANCE": 0.18,
        "HERBIVORE_REPRODUCTION_COST": 8,
        "HERBIVORE_MAX_AGE": 40,
        # Satiation: herbivore stops eating when already well-fed,
        # leaving plants available for the rest of the ecosystem.
        "HERBIVORE_SATIATION_THRESHOLD": 28,
        # Crowding: suppress reproduction when the local area is packed,
        # implementing natural density-dependent population control.
        "HERBIVORE_CROWDING_THRESHOLD": 3,
        # Carnivores: reduced energy gain per hunt and higher reproduction
        # cost significantly slow population growth, preventing over-hunting.
        "CARNIVORE_INITIAL_ENERGY": 15,
        "CARNIVORE_CHILD_ENERGY": 10,
        "CARNIVORE_ENERGY_GAIN": 12,
        "CARNIVORE_REPRODUCTION_THRESHOLD": 40,
        "CARNIVORE_REPRODUCTION_CHANCE": 0.10,
        "CARNIVORE_REPRODUCTION_COST": 30,
        "CARNIVORE_MAX_AGE": 50,
        "CARNIVORE_SATIATION_THRESHOLD": 45,
        "CARNIVORE_CROWDING_THRESHOLD": 3,
    },
    "balanced": {
        "description": "均衡生态——捕食压力适中",
        "PLANT_REPRODUCTION_CHANCE": 0.28,
        "PLANT_MAX_AGE": 28,
        "HERBIVORE_INITIAL_ENERGY": 18,
        "HERBIVORE_CHILD_ENERGY": 12,
        "HERBIVORE_ENERGY_GAIN": 12,
        "HERBIVORE_REPRODUCTION_THRESHOLD": 22,
        "HERBIVORE_REPRODUCTION_CHANCE": 0.18,
        "HERBIVORE_REPRODUCTION_COST": 8,
        "HERBIVORE_MAX_AGE": 45,
        "HERBIVORE_SATIATION_THRESHOLD": 30,
        "HERBIVORE_CROWDING_THRESHOLD": 4,
        "CARNIVORE_INITIAL_ENERGY": 18,
        "CARNIVORE_CHILD_ENERGY": 12,
        "CARNIVORE_ENERGY_GAIN": 14,
        "CARNIVORE_REPRODUCTION_THRESHOLD": 38,
        "CARNIVORE_REPRODUCTION_CHANCE": 0.12,
        "CARNIVORE_REPRODUCTION_COST": 22,
        "CARNIVORE_MAX_AGE": 55,
        "CARNIVORE_SATIATION_THRESHOLD": 42,
        "CARNIVORE_CROWDING_THRESHOLD": 4,
    },
    "intense": {
        "description": "激烈竞争——种群波动显著，可能出现阶段性崩溃",
        "PLANT_REPRODUCTION_CHANCE": 0.20,
        "PLANT_MAX_AGE": 22,
        "HERBIVORE_INITIAL_ENERGY": 15,
        "HERBIVORE_CHILD_ENERGY": 10,
        "HERBIVORE_ENERGY_GAIN": 12,
        "HERBIVORE_REPRODUCTION_THRESHOLD": 20,
        "HERBIVORE_REPRODUCTION_CHANCE": 0.18,
        "HERBIVORE_REPRODUCTION_COST": 6,
        "HERBIVORE_MAX_AGE": 40,
        "HERBIVORE_SATIATION_THRESHOLD": 35,
        "HERBIVORE_CROWDING_THRESHOLD": 5,
        "CARNIVORE_INITIAL_ENERGY": 20,
        "CARNIVORE_CHILD_ENERGY": 14,
        "CARNIVORE_ENERGY_GAIN": 16,
        "CARNIVORE_REPRODUCTION_THRESHOLD": 38,
        "CARNIVORE_REPRODUCTION_CHANCE": 0.14,
        "CARNIVORE_REPRODUCTION_COST": 18,
        "CARNIVORE_MAX_AGE": 50,
        "CARNIVORE_SATIATION_THRESHOLD": 50,
        "CARNIVORE_CROWDING_THRESHOLD": 5,
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
            f"未知预设：'{name}'。可用预设：{list(PRESETS.keys())}"
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
        f"预设：{_active_preset_name}\n"
        f"  植物繁殖概率            ：{_active['PLANT_REPRODUCTION_CHANCE']:.0%}\n"
        f"  草食动物繁殖所需进食次数：{herb_feeds:.1f}\n"
        f"  草食动物饱食阈值能量    ：{_active['HERBIVORE_SATIATION_THRESHOLD']}\n"
        f"  肉食动物繁殖所需捕猎次数：{carn_hunts:.1f}\n"
        f"  肉食动物饱食阈值能量    ：{_active['CARNIVORE_SATIATION_THRESHOLD']}"
    )
