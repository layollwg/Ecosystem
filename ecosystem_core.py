from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

import config
from organisms import Animal, Carnivore, Herbivore, Organism, Plant
from terrain import (
    TerrainType,
    generate_terrain_grid,
    is_land_passable,
    is_plant_habitable,
)

TOrganism = TypeVar("TOrganism", bound=Organism)
Position = Tuple[int, int]
ObservationTensor = List[List[List[float]]]


@dataclass(frozen=True)
class RewardConfig:
    eat_success: float = 5.0
    reproduce_success: float = 8.0
    move_cost: float = -0.05
    invalid_collision: float = -1.0
    failed_reproduce: float = -0.2
    death_penalty: float = -10.0


class EcosystemCore:
    """Tk-independent simulation core with RL-friendly API."""

    ACTION_STAY = 0
    ACTION_UP = 1
    ACTION_DOWN = 2
    ACTION_LEFT = 3
    ACTION_RIGHT = 4
    ACTION_REPRODUCE = 5

    ACTIONS = (
        ACTION_STAY,
        ACTION_UP,
        ACTION_DOWN,
        ACTION_LEFT,
        ACTION_RIGHT,
        ACTION_REPRODUCE,
    )
    # Growth-limiter stages:
    # - Very young: highest action failure probability.
    # - Young: reduced failure probability.
    # - Vision edge mask: fades slightly after "very young" to smooth transition.
    VERY_YOUNG_AGE_RATIO = 0.25
    YOUNG_AGE_RATIO = 0.4
    VISION_MASK_AGE_RATIO = 0.3
    VERY_YOUNG_ACTION_FAIL_PROB = 0.35
    YOUNG_ACTION_FAIL_PROB = 0.15
    # Lower bounds to avoid unstable normalization / division near zero.
    MIN_GENOME_SIZE_NORMALIZER = 0.5
    MIN_SPEED_NORMALIZER = 0.5
    # Shared observation normalization constant for animal energy channel.
    ENERGY_NORMALIZATION_BASE = 150.0

    def __init__(
        self,
        grid_size: int,
        num_plants: int,
        num_herbivores: int,
        num_carnivores: int,
        tick_delay: float = 0.2,
        manual_step: bool = False,
        theme: str = "light",
        observation_radius: int = 2,
        reward_config: Optional[RewardConfig] = None,
    ) -> None:
        self.grid_size = grid_size
        self.tick_delay = tick_delay
        self.manual_step = manual_step
        self.tick_count = 0
        self.organisms: List[Organism] = []
        self.grid: Dict[Position, Organism] = {}
        self.terrain_grid: Dict[Position, TerrainType] = {}
        self._pending_additions: List[Organism] = []
        self._pending_removals: List[Organism] = []

        self._init_plants = num_plants
        self._init_herbivores = num_herbivores
        self._init_carnivores = num_carnivores

        self._theme = theme.lower()
        self.cell_size = max(20, min(40, 800 // max(grid_size, 1)))

        self.plant_history: List[int] = []
        self.herbivore_history: List[int] = []
        self.carnivore_history: List[int] = []

        self.births_this_tick = 0
        self.deaths_this_tick = 0
        self._last_tick_ms = 0.0

        self.observation_radius = max(1, observation_radius)
        self.reward_config = reward_config or RewardConfig()

        self._next_agent_id = 1
        self._step_rewards: Dict[int, float] = {}

        self.reset()

    # ── RL standard API ──────────────────────────────────────────────────────

    def reset(self) -> Dict[str, Any]:
        self.tick_count = 0
        self.organisms.clear()
        self.grid.clear()
        self._pending_additions.clear()
        self._pending_removals.clear()
        self.plant_history.clear()
        self.herbivore_history.clear()
        self.carnivore_history.clear()
        self.births_this_tick = 0
        self.deaths_this_tick = 0
        self._last_tick_ms = 0.0
        self._next_agent_id = 1

        self._generate_terrain()
        self._populate_initial_organisms(
            self._init_plants,
            self._init_herbivores,
            self._init_carnivores,
        )

        self._record_population_history()
        return self._compose_observation()

    def step(
        self, action_dict: Optional[Dict[int, int]] = None
    ) -> Tuple[Dict[str, Any], Dict[int, float], Dict[Any, bool], Dict[str, Any]]:
        if not self.organisms:
            obs = self._compose_observation()
            return obs, {}, {"__all__": True}, {"reason": "no_organisms"}

        tick_start = time.time()
        self.tick_count += 1

        pre_agents = self._alive_animals()
        pre_agent_ids = {a.agent_id for a in pre_agents}
        self._step_rewards = {agent_id: 0.0 for agent_id in pre_agent_ids}

        order = list(self.organisms)
        random.shuffle(order)

        controlled_ids = set(action_dict.keys()) if action_dict else set()

        for organism in order:
            if not organism.alive:
                continue

            if isinstance(organism, Animal) and organism.agent_id in controlled_ids:
                organism.update_vitals(self)
                if organism.alive:
                    action = action_dict.get(organism.agent_id, self.ACTION_STAY)
                    self._apply_external_action(organism, action)
            else:
                organism.update(self)

        self._finalize_tick()
        self._last_tick_ms = (time.time() - tick_start) * 1000
        self._record_population_history()

        post_agent_ids = {a.agent_id for a in self._alive_animals()}
        rewards = {aid: self._step_rewards.get(aid, 0.0) for aid in pre_agent_ids}
        dones: Dict[Any, bool] = {aid: aid not in post_agent_ids for aid in pre_agent_ids}
        dones["__all__"] = len(post_agent_ids) == 0

        info = {
            "tick": self.tick_count,
            "births_this_tick": self.births_this_tick,
            "deaths_this_tick": self.deaths_this_tick,
            "agent_species": self.get_agent_species_map(),
        }
        return self._compose_observation(), rewards, dones, info

    def render(self) -> Dict[str, Any]:
        return self.get_display_data()

    # ── RL utilities ──────────────────────────────────────────────────────────

    def get_action_space(self) -> Dict[str, Any]:
        return {
            "type": "discrete",
            "actions": {
                self.ACTION_STAY: "stay",
                self.ACTION_UP: "move_up",
                self.ACTION_DOWN: "move_down",
                self.ACTION_LEFT: "move_left",
                self.ACTION_RIGHT: "move_right",
                self.ACTION_REPRODUCE: "reproduce",
            },
        }

    def get_agent_species_map(self) -> Dict[int, str]:
        mapping: Dict[int, str] = {}
        for organism in self.organisms:
            if not organism.alive or not isinstance(organism, Animal):
                continue
            mapping[organism.agent_id] = type(organism).__name__
        return mapping

    def save_checkpoint(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "tick": self.tick_count,
            "display": self.get_display_data(),
            "metadata": metadata or {},
        }
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Core simulation internals ─────────────────────────────────────────────

    def _generate_terrain(self) -> None:
        self.terrain_grid = generate_terrain_grid(self.grid_size)

    def _populate_initial_organisms(
        self,
        num_plants: int,
        num_herbivores: int,
        num_carnivores: int,
    ) -> None:
        available_plant_positions = self._get_spawn_positions(
            lambda p: self.get_terrain(*p) == TerrainType.DIRT
        )
        available_land_positions = self._get_spawn_positions(
            lambda p: is_land_passable(self.get_terrain(*p))
        )

        random.shuffle(available_plant_positions)
        random.shuffle(available_land_positions)

        for _ in range(num_plants):
            if not available_plant_positions:
                break
            x, y = available_plant_positions.pop()
            if (x, y) in self.grid:
                continue
            plant = Plant(x, y)
            self._assign_agent_id(plant)
            self.organisms.append(plant)
            self.grid[(x, y)] = plant

        available_land_positions = self._filter_unoccupied_positions(available_land_positions)

        for _ in range(num_herbivores):
            if not available_land_positions:
                break
            x, y = available_land_positions.pop()
            herbivore = Herbivore(x, y)
            self._assign_agent_id(herbivore)
            self.organisms.append(herbivore)
            self.grid[(x, y)] = herbivore

        for _ in range(num_carnivores):
            if not available_land_positions:
                break
            x, y = available_land_positions.pop()
            carnivore = Carnivore(x, y)
            self._assign_agent_id(carnivore)
            self.organisms.append(carnivore)
            self.grid[(x, y)] = carnivore

    def _record_population_history(self) -> None:
        plant_count = sum(1 for o in self.organisms if isinstance(o, Plant) and o.alive)
        herb_count = sum(1 for o in self.organisms if isinstance(o, Herbivore) and o.alive)
        carn_count = sum(1 for o in self.organisms if isinstance(o, Carnivore) and o.alive)
        self.plant_history.append(plant_count)
        self.herbivore_history.append(herb_count)
        self.carnivore_history.append(carn_count)

    def _alive_animals(self) -> List[Animal]:
        return [o for o in self.organisms if isinstance(o, Animal) and o.alive]

    def _assign_agent_id(self, organism: Organism) -> None:
        organism.agent_id = self._next_agent_id
        self._next_agent_id += 1

    def _reward(self, organism: Animal, amount: float) -> None:
        self._step_rewards[organism.agent_id] = self._step_rewards.get(organism.agent_id, 0.0) + amount

    def _normalize_energy(self, animal: Animal) -> float:
        normalized = animal.energy / (
            self.ENERGY_NORMALIZATION_BASE
            * max(self.MIN_GENOME_SIZE_NORMALIZER, animal.genome.size)
        )
        return min(1.0, max(0.0, normalized))

    def _add_death_penalty(self, animal: Animal) -> None:
        self._step_rewards[animal.agent_id] = (
            self._step_rewards.get(animal.agent_id, 0.0)
            + self.reward_config.death_penalty
        )

    def _action_failure_probability(self, animal: Animal) -> float:
        age_ratio = 1.0 if animal.max_age <= 0 else animal.age / animal.max_age
        if age_ratio < self.VERY_YOUNG_AGE_RATIO:
            return self.VERY_YOUNG_ACTION_FAIL_PROB
        if age_ratio < self.YOUNG_AGE_RATIO:
            return self.YOUNG_ACTION_FAIL_PROB
        return 0.0

    def _apply_external_action(self, animal: Animal, action: int) -> None:
        if action not in self.ACTIONS:
            action = self.ACTION_STAY

        if action == self.ACTION_STAY:
            return

        if random.random() < self._action_failure_probability(animal):
            self._reward(animal, self.reward_config.move_cost)
            return

        if action == self.ACTION_REPRODUCE:
            if animal.try_reproduce(self):
                self._reward(animal, self.reward_config.reproduce_success)
            else:
                self._reward(animal, self.reward_config.failed_reproduce)
            return

        dx, dy = 0, 0
        if action == self.ACTION_UP:
            dy = -1
        elif action == self.ACTION_DOWN:
            dy = 1
        elif action == self.ACTION_LEFT:
            dx = -1
        elif action == self.ACTION_RIGHT:
            dx = 1

        target_x = animal.x + dx
        target_y = animal.y + dy
        self._attempt_move_or_feed(animal, target_x, target_y)

    def _attempt_move_or_feed(self, animal: Animal, target_x: int, target_y: int) -> None:
        if not (0 <= target_x < self.grid_size and 0 <= target_y < self.grid_size):
            self._reward(animal, self.reward_config.invalid_collision)
            return

        if not self.can_move_to_terrain(target_x, target_y):
            self._reward(animal, self.reward_config.invalid_collision)
            return

        occupant = self.get_organism_at(target_x, target_y)

        if isinstance(animal, Herbivore) and isinstance(occupant, Plant):
            self.queue_remove_organism(occupant)
            # Faster herbivores burn more baseline energy, so feeding conversion
            # is intentionally slightly lower to preserve a speed-vs-efficiency
            # trade-off in policy learning (balance design).
            animal.energy += config.get("HERBIVORE_ENERGY_GAIN") / max(
                self.MIN_SPEED_NORMALIZER,
                animal.genome.speed,
            )
            self.move_organism(animal, target_x, target_y)
            self._reward(animal, self.reward_config.eat_success)
            return

        if isinstance(animal, Carnivore) and isinstance(occupant, Herbivore):
            self.queue_remove_organism(occupant)
            animal.energy += config.get("CARNIVORE_ENERGY_GAIN") * (1.0 + occupant.genome.size)
            self.move_organism(animal, target_x, target_y)
            self._reward(animal, self.reward_config.eat_success)
            return

        if occupant is not None:
            self._reward(animal, self.reward_config.invalid_collision)
            return

        if animal.move_to(self, target_x, target_y):
            self._reward(animal, self.reward_config.move_cost)
        else:
            self._reward(animal, self.reward_config.invalid_collision)

    def _finalize_tick(self) -> None:
        self.deaths_this_tick = len(self._pending_removals)

        if self._pending_removals:
            removal_set = set(self._pending_removals)
            self.organisms = [
                organism
                for organism in self.organisms
                if organism.alive and organism not in removal_set
            ]
            self._pending_removals.clear()

        self.births_this_tick = 0
        if self._pending_additions:
            for organism in self._pending_additions:
                if (organism.x, organism.y) in self.grid:
                    continue
                self._assign_agent_id(organism)
                organism.alive = True
                self.organisms.append(organism)
                self.grid[(organism.x, organism.y)] = organism
                self.births_this_tick += 1
            self._pending_additions.clear()

    def _get_spawn_positions(self, predicate: Callable[[Position], bool]) -> List[Position]:
        return [
            (x, y)
            for x in range(self.grid_size)
            for y in range(self.grid_size)
            if predicate((x, y))
        ]

    def _filter_unoccupied_positions(self, positions: List[Position]) -> List[Position]:
        return [position for position in positions if position not in self.grid]

    # ── Observation construction (POMDP) ──────────────────────────────────────

    def _compose_observation(self) -> Dict[str, Any]:
        return {
            "global": self.get_global_observation(),
            "agents": self.get_all_agent_observations(),
        }

    def get_global_observation(self) -> Dict[str, Any]:
        terrain = [
            [int(self.get_terrain(x, y).value) for x in range(self.grid_size)]
            for y in range(self.grid_size)
        ]
        entities = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        for organism in self.organisms:
            if not organism.alive:
                continue
            if isinstance(organism, Plant):
                entities[organism.y][organism.x] = 1
            elif isinstance(organism, Herbivore):
                entities[organism.y][organism.x] = 2
            elif isinstance(organism, Carnivore):
                entities[organism.y][organism.x] = 3
        return {
            "tick": self.tick_count,
            "terrain": terrain,
            "entities": entities,
            "stats": self.get_display_data(),
        }

    def get_all_agent_observations(self) -> Dict[int, ObservationTensor]:
        observations: Dict[int, ObservationTensor] = {}
        for organism in self.organisms:
            if not organism.alive or not isinstance(organism, Animal):
                continue
            observations[organism.agent_id] = self.get_agent_observation(organism)
        return observations

    def get_agent_observation(self, animal: Animal) -> ObservationTensor:
        radius = self.observation_radius
        size = radius * 2 + 1

        energy_norm = self._normalize_energy(animal)
        age_norm = (
            1.0
            if animal.max_age <= 0
            else min(1.0, max(0.0, animal.age / animal.max_age))
        )

        tensor: ObservationTensor = []
        for dy in range(-radius, radius + 1):
            row: List[List[float]] = []
            for dx in range(-radius, radius + 1):
                x, y = animal.x + dx, animal.y + dy
                obstacle = 1.0
                prey = 0.0
                ally = 0.0

                if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                    obstacle = 0.0 if self.can_move_to_terrain(x, y) else 1.0
                    occupant = self.get_organism_at(x, y)
                    if isinstance(animal, Herbivore):
                        prey = 1.0 if isinstance(occupant, Plant) else 0.0
                        ally = 1.0 if isinstance(occupant, Herbivore) else 0.0
                    else:
                        prey = 1.0 if isinstance(occupant, Herbivore) else 0.0
                        ally = 1.0 if isinstance(occupant, Carnivore) else 0.0

                row.append([obstacle, prey, ally, energy_norm, age_norm])
            tensor.append(row)

        self._apply_growth_limiter_mask(tensor, age_norm)
        return tensor

    def _apply_growth_limiter_mask(self, tensor: ObservationTensor, age_norm: float) -> None:
        if age_norm >= self.VISION_MASK_AGE_RATIO:
            return
        zero_obs = [0.0] * 5
        edge = 0
        size = len(tensor)
        last = size - 1
        for i in range(size):
            tensor[edge][i] = zero_obs[:]
            tensor[last][i] = zero_obs[:]
            tensor[i][edge] = zero_obs[:]
            tensor[i][last] = zero_obs[:]

    # ── Public helpers used by organisms / UI ─────────────────────────────────

    def get_organism_at(self, x: int, y: int) -> Optional[Organism]:
        organism = self.grid.get((x, y))
        if organism and organism.alive:
            return organism
        return None

    def get_adjacent_positions(self, x: int, y: int) -> List[Position]:
        positions: List[Position] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    positions.append((nx, ny))
        return positions

    def get_adjacent_empty_cells(self, x: int, y: int) -> List[Position]:
        return [
            (nx, ny)
            for nx, ny in self.get_adjacent_positions(x, y)
            if self.get_organism_at(nx, ny) is None and is_land_passable(self.get_terrain(nx, ny))
        ]

    def get_adjacent_organisms(
        self,
        x: int,
        y: int,
        organism_type: Type[TOrganism],
    ) -> List[TOrganism]:
        matches: List[TOrganism] = []
        for nx, ny in self.get_adjacent_positions(x, y):
            occupant = self.get_organism_at(nx, ny)
            if occupant and isinstance(occupant, organism_type):
                matches.append(occupant)
        return matches

    def move_organism(self, organism: Organism, new_x: int, new_y: int) -> None:
        if not is_land_passable(self.get_terrain(new_x, new_y)):
            return
        origin = (organism.x, organism.y)
        if self.grid.get(origin) is organism:
            self.grid.pop(origin, None)
        organism.x = new_x
        organism.y = new_y
        self.grid[(new_x, new_y)] = organism

    def queue_add_organism(self, organism: Organism) -> None:
        organism.alive = False
        self._pending_additions.append(organism)

    def queue_remove_organism(self, organism: Organism) -> None:
        if not organism.alive:
            return
        organism.alive = False
        self.grid.pop((organism.x, organism.y), None)
        self._pending_removals.append(organism)

        if isinstance(organism, Animal):
            self._add_death_penalty(organism)

    def get_terrain(self, x: int, y: int) -> TerrainType:
        return self.terrain_grid.get((x, y), TerrainType.DIRT)

    def can_plant_grow_at(self, x: int, y: int) -> bool:
        return is_plant_habitable(self.get_terrain(x, y))

    def can_move_to_terrain(self, x: int, y: int) -> bool:
        return is_land_passable(self.get_terrain(x, y))

    def has_line_of_sight(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        if (x1, y1) == (x2, y2):
            return True

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1
        while (x, y) != (x2, y2):
            e2 = err * 2
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
            if (x, y) != (x2, y2) and self.get_terrain(x, y) == TerrainType.MOUNTAIN:
                return False
        return True

    def get_display_data(self) -> Dict[str, Any]:
        plant_count = 0
        herbivore_count = 0
        carnivore_count = 0
        total_age = 0
        age_count = 0
        total_energy = 0.0
        energy_count = 0

        for organism in self.organisms:
            if not organism.alive:
                continue
            total_age += organism.age
            age_count += 1
            if isinstance(organism, Plant):
                plant_count += 1
            elif isinstance(organism, Herbivore):
                herbivore_count += 1
                total_energy += organism.energy
                energy_count += 1
            elif isinstance(organism, Carnivore):
                carnivore_count += 1
                total_energy += organism.energy
                energy_count += 1

        avg_age = total_age / age_count if age_count > 0 else 0.0
        avg_energy = total_energy / energy_count if energy_count > 0 else 0.0
        season = config.get_current_season(self.tick_count)

        return {
            "tick": self.tick_count,
            "plant_count": plant_count,
            "herbivore_count": herbivore_count,
            "carnivore_count": carnivore_count,
            "plant_history": self.plant_history,
            "herbivore_history": self.herbivore_history,
            "carnivore_history": self.carnivore_history,
            "births_this_tick": self.births_this_tick,
            "deaths_this_tick": self.deaths_this_tick,
            "avg_age": avg_age,
            "avg_energy": avg_energy,
            "tick_time_ms": self._last_tick_ms,
            "organism_count": len(self.organisms),
            "season": season,
            "season_emoji": config.SEASON_EMOJIS.get(season, ""),
        }

    def get_statistics(self) -> Dict[str, Any]:
        plant_count = sum(1 for o in self.organisms if isinstance(o, Plant) and o.alive)
        herb_count = sum(1 for o in self.organisms if isinstance(o, Herbivore) and o.alive)
        carn_count = sum(1 for o in self.organisms if isinstance(o, Carnivore) and o.alive)
        return {
            "tick": self.tick_count,
            "plant_count": plant_count,
            "herbivore_count": herb_count,
            "carnivore_count": carn_count,
            "plant_history": list(self.plant_history),
            "herbivore_history": list(self.herbivore_history),
            "carnivore_history": list(self.carnivore_history),
            "init_plants": self._init_plants,
            "init_herbivores": self._init_herbivores,
            "init_carnivores": self._init_carnivores,
            "grid_size": self.grid_size,
        }
