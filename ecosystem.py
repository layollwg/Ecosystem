from __future__ import annotations

import random
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

import config
from ecosystem_env import EcosystemEnv
from organisms import Animal, Carnivore, Herbivore, Plant
from terrain import TerrainType

Position = Tuple[int, int]
SPECIES_POOL_MULTIPLIER = 10
MAX_RABBIT_POOL_CAP = 500
MAX_FOX_POOL_CAP = 200
RABBIT_POLICY_ID = "rabbit_policy"
FOX_POLICY_ID = "fox_policy"
SPECIES_POLICY_MAP = {
    EcosystemEnv.SPECIES_RABBIT: RABBIT_POLICY_ID,
    EcosystemEnv.SPECIES_FOX: FOX_POLICY_ID,
}


class Ecosystem:
    """Backward-compatible UI-facing adapter over EcosystemEnv."""

    def __init__(
        self,
        grid_size: int,
        num_plants: int,
        num_herbivores: int,
        num_carnivores: int,
        tick_delay: float = 0.2,
        manual_step: bool = False,
        theme: str = "light",
        **_: Any,
    ) -> None:
        self.grid_size = grid_size
        self.tick_delay = tick_delay
        self.manual_step = manual_step
        self._theme = theme.lower()
        self.cell_size = max(20, min(40, 800 // max(grid_size, 1)))
        self.tick_count = 0

        self._init_plants = num_plants
        self._init_herbivores = num_herbivores
        self._init_carnivores = num_carnivores
        self._step_rng = random.Random()
        self._next_agent_id = 1

        self.plant_history: List[int] = []
        self.herbivore_history: List[int] = []
        self.carnivore_history: List[int] = []
        self.births_this_tick = 0
        self.deaths_this_tick = 0
        self._last_tick_ms = 0.0

        capacity = max(1, grid_size * grid_size)
        # Over-provision species pools for births during UI runs while keeping
        # a hard upper bound tied to map capacity.
        rabbit_capacity_cap = min(capacity, MAX_RABBIT_POOL_CAP)
        fox_capacity_cap = min(capacity, MAX_FOX_POOL_CAP)
        max_rabbits = max(num_herbivores * SPECIES_POOL_MULTIPLIER, rabbit_capacity_cap)
        max_foxes = max(num_carnivores * SPECIES_POOL_MULTIPLIER, fox_capacity_cap)
        self._env = EcosystemEnv(
            grid_size=grid_size,
            max_rabbits=max_rabbits,
            max_foxes=max_foxes,
            initial_rabbits=num_herbivores,
            initial_foxes=num_carnivores,
            initial_plants=num_plants,
            render_mode=None,
        )

        self._agent_public_ids: Dict[str, int] = {}
        self._grid: Dict[Position, Any] = {}
        self._organisms: List[Any] = []
        self._plant_objects: Dict[Position, Plant] = {}
        self._last_obs: Dict[str, Dict[str, Any]] = {}
        self._last_infos: Dict[str, Dict[str, Any]] = {}
        self.reset()

    @property
    def terrain_grid(self) -> Dict[Position, TerrainType]:
        return self._env.terrain_grid

    @property
    def grid(self) -> Dict[Position, Any]:
        return self._grid

    @property
    def organisms(self) -> List[Any]:
        return self._organisms

    def reset(self) -> Dict[str, Any]:
        self.tick_count = 0
        self.births_this_tick = 0
        self.deaths_this_tick = 0
        self._last_tick_ms = 0.0
        self.plant_history.clear()
        self.herbivore_history.clear()
        self.carnivore_history.clear()
        self._agent_public_ids.clear()
        self._plant_objects.clear()
        self._next_agent_id = 1
        self._last_obs, self._last_infos = self._env.reset()
        self._sync_from_env()
        self._record_population_history()
        return {"agents": self._last_obs}

    def step(self, action_dict: Optional[Dict[int, int]] = None):
        tick_start = perf_counter()
        if not self._env.agents:
            self._sync_from_env()
            return {"agents": {}}, {}, {"__all__": True}, {"reason": "no_agents"}

        env_actions = self._build_env_actions(action_dict)
        self._last_obs, rewards, terminations, truncations, infos = self._env.step(env_actions)
        self._last_infos = infos
        self.tick_count = self._env._step_count
        self.births_this_tick = sum(1 for payload in infos.values() if payload.get("spawned"))
        self.deaths_this_tick = sum(1 for done in terminations.values() if done)
        self._last_tick_ms = (perf_counter() - tick_start) * 1000.0
        self._sync_from_env()
        self._record_population_history()
        dones = dict(terminations)
        dones["__all__"] = len(self._env.agents) == 0
        info = {"truncations": truncations}
        return {"agents": self._last_obs}, rewards, dones, info

    def get_terrain(self, x: int, y: int) -> TerrainType:
        return self._env.terrain_grid.get((x, y), TerrainType.DIRT)

    def get_display_data(self) -> Dict[str, Any]:
        plants = len(self._env.plants)
        herbs = sum(1 for aid in self._env.agents if aid.startswith("rabbit_"))
        carns = sum(1 for aid in self._env.agents if aid.startswith("fox_"))
        all_organisms = self._organisms
        total_age = sum(getattr(o, "age", 0) for o in all_organisms if getattr(o, "alive", False))
        age_count = sum(1 for o in all_organisms if getattr(o, "alive", False))
        animal_energies = [
            o.energy
            for o in all_organisms
            if getattr(o, "alive", False) and isinstance(o, Animal)
        ]
        season = config.get_current_season(self.tick_count)
        return {
            "tick": self.tick_count,
            "plant_count": plants,
            "herbivore_count": herbs,
            "carnivore_count": carns,
            "plant_history": self.plant_history,
            "herbivore_history": self.herbivore_history,
            "carnivore_history": self.carnivore_history,
            "births_this_tick": self.births_this_tick,
            "deaths_this_tick": self.deaths_this_tick,
            "avg_age": (total_age / age_count) if age_count else 0.0,
            "avg_energy": (sum(animal_energies) / len(animal_energies)) if animal_energies else 0.0,
            "tick_time_ms": self._last_tick_ms,
            "organism_count": len(self._organisms),
            "season": season,
            "season_emoji": config.SEASON_EMOJIS.get(season, ""),
        }

    def get_statistics(self) -> Dict[str, Any]:
        plants = len(self._env.plants)
        herbs = sum(1 for aid in self._env.agents if aid.startswith("rabbit_"))
        carns = sum(1 for aid in self._env.agents if aid.startswith("fox_"))
        return {
            "tick": self.tick_count,
            "plant_count": plants,
            "herbivore_count": herbs,
            "carnivore_count": carns,
            "plant_history": list(self.plant_history),
            "herbivore_history": list(self.herbivore_history),
            "carnivore_history": list(self.carnivore_history),
            "init_plants": self._init_plants,
            "init_herbivores": self._init_herbivores,
            "init_carnivores": self._init_carnivores,
            "grid_size": self.grid_size,
        }

    def get_inference_batch(self) -> Dict[int, Dict[str, Any]]:
        """Return current alive-agent observations keyed by UI public agent id."""
        batch: Dict[int, Dict[str, Any]] = {}
        for env_agent_id in self._env.agents:
            public_id = self._agent_public_ids.get(env_agent_id)
            if public_id is None:
                continue
            obs = self._last_obs.get(env_agent_id)
            if obs is None:
                continue
            species = self._env.get_agent_species(env_agent_id)
            policy_id = SPECIES_POLICY_MAP.get(species)
            if policy_id is None:
                raise KeyError(f"unsupported species for policy mapping: {species}")
            batch[public_id] = {
                "species": species,
                "policy_id": policy_id,
                "observation": obs,
            }
        return batch

    def _build_env_actions(self, action_dict: Optional[Dict[int, int]]) -> Dict[str, int]:
        if not action_dict:
            return self._sample_autonomous_actions()
        reverse_map = {pub: agent_id for agent_id, pub in self._agent_public_ids.items()}
        env_actions: Dict[str, int] = {}
        for public_id, action in action_dict.items():
            agent_id = reverse_map.get(public_id)
            if agent_id is None or agent_id not in self._env.agents:
                continue
            env_actions[agent_id] = int(action)
        for agent_id in self._env.agents:
            env_actions.setdefault(agent_id, EcosystemEnv.ACTION_STAY)
        return env_actions

    def _sample_autonomous_actions(self) -> Dict[str, int]:
        actions: Dict[str, int] = {}
        for agent_id in self._env.agents:
            obs = self._last_obs.get(agent_id, {})
            mask = obs.get("action_mask")
            if mask is None:
                actions[agent_id] = EcosystemEnv.ACTION_STAY
                continue
            legal = [idx for idx, enabled in enumerate(mask) if int(enabled) == 1]
            actions[agent_id] = self._step_rng.choice(legal) if legal else EcosystemEnv.ACTION_STAY
        return actions

    def _sync_from_env(self) -> None:
        self._grid = {}
        self._organisms = []

        for agent_id in self._env.agents:
            organism = self._env.agent_to_object.get(agent_id)
            if organism is None:
                continue
            public_id = self._agent_public_ids.get(agent_id)
            if public_id is None:
                public_id = self._next_agent_id
                self._next_agent_id += 1
                self._agent_public_ids[agent_id] = public_id
            organism.agent_id = public_id
            self._grid[(organism.x, organism.y)] = organism
            self._organisms.append(organism)

        next_plants: Dict[Position, Plant] = {}
        for pos in self._env.plants:
            plant = self._plant_objects.get(pos)
            if plant is None:
                plant = Plant(pos[0], pos[1])
            next_plants[pos] = plant
            self._grid[pos] = plant
            self._organisms.append(plant)
        self._plant_objects = next_plants

    def _record_population_history(self) -> None:
        self.plant_history.append(len(self._env.plants))
        self.herbivore_history.append(sum(1 for aid in self._env.agents if aid.startswith("rabbit_")))
        self.carnivore_history.append(sum(1 for aid in self._env.agents if aid.startswith("fox_")))
