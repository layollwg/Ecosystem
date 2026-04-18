from __future__ import annotations

import random
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import numpy as np
from gymnasium import spaces
from pettingzoo import ParallelEnv

import config
from organisms import Animal, Carnivore, Herbivore
from terrain import TerrainType, generate_terrain_grid, is_land_passable

Position = Tuple[int, int]


class EcosystemEnv(ParallelEnv):
    """PettingZoo parallel ecosystem environment with pooled agent IDs."""

    metadata = {"render_modes": ["human", "rgb_array", None], "name": "ecosystem_parallel_v1"}

    ACTION_UP = 0
    ACTION_DOWN = 1
    ACTION_LEFT = 2
    ACTION_RIGHT = 3
    ACTION_STAY = 4
    ACTION_REPRODUCE = 5
    MIN_SPEED_DIVISOR = 0.5
    HERBIVORE_MAX_ENERGY_FACTOR = 100.0
    CARNIVORE_MAX_ENERGY_FACTOR = 150.0
    REPRODUCE_FRACTION = 0.8
    MUTATION_RATE = 0.05
    PARENT_POST_REPRODUCE_ENERGY_RATIO = 0.6
    REPRODUCTION_MATURITY_AGE_RATIO = 0.2
    SPECIES_RABBIT = "rabbit"
    SPECIES_FOX = "fox"

    def __init__(
        self,
        max_rabbits: int = 500,
        max_foxes: int = 100,
        grid_size: int = 50,
        initial_rabbits: int = 50,
        initial_foxes: int = 10,
        initial_plants: int = 250,
        max_steps: Optional[int] = None,
        render_mode: Optional[str] = None,
    ) -> None:
        super().__init__()

        self.grid_size = grid_size
        self.max_rabbits = max_rabbits
        self.max_foxes = max_foxes
        self.initial_rabbits = min(initial_rabbits, max_rabbits)
        self.initial_foxes = min(initial_foxes, max_foxes)
        self.initial_plants = max(0, initial_plants)
        self.max_steps = max_steps
        self.render_mode = render_mode

        self.possible_agents = [f"rabbit_{i}" for i in range(max_rabbits)] + [
            f"fox_{i}" for i in range(max_foxes)
        ]
        self.agents: List[str] = []

        self.available_rabbits: Deque[str] = deque(f"rabbit_{i}" for i in range(max_rabbits))
        self.available_foxes: Deque[str] = deque(f"fox_{i}" for i in range(max_foxes))
        self.agent_generations: Dict[str, int] = {agent_id: 0 for agent_id in self.possible_agents}

        self.agent_to_object: Dict[str, Animal] = {}
        self.terrain_grid: Dict[Position, TerrainType] = {}
        self.plants: Set[Position] = set()
        self._occupied_positions: Set[Position] = set()
        self._rabbit_positions: Set[Position] = set()
        self._fox_positions: Set[Position] = set()

        self._step_count = 0
        self._rng = random.Random()
        self._np_rng = np.random.default_rng()

        self.action_spaces: Dict[str, spaces.Discrete] = {
            agent_id: spaces.Discrete(6) for agent_id in self.possible_agents
        }
        self.observation_spaces: Dict[str, spaces.Dict] = {
            agent_id: spaces.Dict(
                {
                    "grid": spaces.Box(low=-1.0, high=1.0, shape=(4, 11, 11), dtype=np.float32),
                    "state": spaces.Box(low=0.0, high=1.0, shape=(3,), dtype=np.float32),
                    "action_mask": spaces.Box(low=0, high=1, shape=(6,), dtype=np.int8),
                }
            )
            for agent_id in self.possible_agents
        }

        self._tk_root = None
        self._tk_canvas = None
        self._cell_px = 12

    def observation_space(self, agent: str) -> spaces.Dict:
        return self.observation_spaces[agent]

    def action_space(self, agent: str) -> spaces.Discrete:
        return self.action_spaces[agent]

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        if seed is not None:
            self._rng.seed(seed)
            self._np_rng = np.random.default_rng(seed)

        self._step_count = 0
        self.agents.clear()
        self.agent_to_object.clear()
        self.plants.clear()

        self.available_rabbits = deque(f"rabbit_{i}" for i in range(self.max_rabbits))
        self.available_foxes = deque(f"fox_{i}" for i in range(self.max_foxes))
        self.agent_generations = {agent_id: 0 for agent_id in self.possible_agents}

        self.terrain_grid = generate_terrain_grid(self.grid_size)

        self._spawn_initial_plants()
        self._spawn_initial_animals(self.SPECIES_RABBIT, self.initial_rabbits)
        self._spawn_initial_animals(self.SPECIES_FOX, self.initial_foxes)
        self._rebuild_position_indices()

        observations = {agent_id: self._get_obs(agent_id) for agent_id in self.agents}
        infos = {
            agent_id: {
                "true_generation": self.agent_generations[agent_id],
                "species": self._species_of(agent_id),
            }
            for agent_id in self.agents
        }
        return observations, infos

    def step(self, actions: Dict[str, int]):
        if not self.agents:
            return {}, {}, {}, {}, {}

        current_agents = list(self.agents)
        self._step_count += 1

        rewards: Dict[str, float] = {agent_id: 0.0 for agent_id in current_agents}
        terminations: Dict[str, bool] = {agent_id: False for agent_id in current_agents}
        truncations: Dict[str, bool] = {agent_id: False for agent_id in current_agents}
        infos: Dict[str, Dict[str, Any]] = {agent_id: {} for agent_id in current_agents}

        desired_positions: Dict[str, Position] = {}
        for agent_id in current_agents:
            organism = self.agent_to_object[agent_id]
            action = int(actions.get(agent_id, self.ACTION_STAY))
            dx, dy = self._action_to_delta(action)
            target = (organism.x + dx, organism.y + dy)

            if not self._is_valid_target(*target):
                target = (organism.x, organism.y)
                rewards[agent_id] -= 0.1
                infos[agent_id]["collision"] = "terrain_or_bounds"

            desired_positions[agent_id] = target

        collision_by_species_and_position: Dict[Tuple[str, Position], List[str]] = {}
        for agent_id, target in desired_positions.items():
            collision_by_species_and_position.setdefault(
                (self._species_of(agent_id), target),
                [],
            ).append(agent_id)

        for (species, _), ids in collision_by_species_and_position.items():
            if len(ids) <= 1:
                continue
            winner = self._rng.choice(ids)
            for loser in ids:
                if loser == winner:
                    continue
                organism = self.agent_to_object[loser]
                desired_positions[loser] = (organism.x, organism.y)
                rewards[loser] -= 0.05
                infos[loser]["collision"] = f"{species}_collision"

        for agent_id, target in desired_positions.items():
            organism = self.agent_to_object[agent_id]
            organism.x, organism.y = target
        self._rebuild_position_indices()

        eaten_rabbits: Set[str] = set()

        position_to_rabbits: Dict[Position, List[str]] = {}
        position_to_foxes: Dict[Position, List[str]] = {}
        for agent_id in current_agents:
            organism = self.agent_to_object[agent_id]
            pos = (organism.x, organism.y)
            if self._species_of(agent_id) == self.SPECIES_RABBIT:
                position_to_rabbits.setdefault(pos, []).append(agent_id)
            else:
                position_to_foxes.setdefault(pos, []).append(agent_id)

        for pos, fox_ids in position_to_foxes.items():
            rabbits = position_to_rabbits.get(pos)
            if not rabbits:
                continue
            victim = self._rng.choice(rabbits)
            eaten_rabbits.add(victim)
            for fox_id in fox_ids:
                fox = self.agent_to_object[fox_id]
                prey = self.agent_to_object[victim]
                fox.energy += config.get("CARNIVORE_ENERGY_GAIN") * (1.0 + prey.genome.size)
                rewards[fox_id] += 5.0

        for agent_id in current_agents:
            if agent_id in eaten_rabbits:
                continue
            if self._species_of(agent_id) != self.SPECIES_RABBIT:
                continue
            rabbit = self.agent_to_object[agent_id]
            pos = (rabbit.x, rabbit.y)
            if pos in self.plants:
                self.plants.remove(pos)
                rabbit.energy += config.get("HERBIVORE_ENERGY_GAIN") / max(
                    self.MIN_SPEED_DIVISOR,
                    rabbit.genome.speed,
                )
                rewards[agent_id] += 1.0

        for agent_id in current_agents:
            if agent_id in eaten_rabbits:
                continue
            organism = self.agent_to_object[agent_id]
            organism.energy -= organism.calculate_energy_cost()
            organism.age += 1

        for agent_id in current_agents:
            organism = self.agent_to_object[agent_id]
            action = int(actions.get(agent_id, self.ACTION_STAY))
            if action != self.ACTION_REPRODUCE:
                continue
            if agent_id in eaten_rabbits:
                continue
            if not self._can_reproduce(organism):
                continue

            species = self._species_of(agent_id)
            birth_pos = self._find_birth_position(organism.x, organism.y, self._occupied_positions)
            if birth_pos is None:
                continue

            child_genome = organism.genome.mutate(mutation_rate=self.MUTATION_RATE)
            child_id = self._spawn_agent(species, birth_pos[0], birth_pos[1], genome=child_genome)
            if child_id is None:
                continue

            organism.energy *= self.PARENT_POST_REPRODUCE_ENERGY_RATIO
            rewards[agent_id] += 5.0
            infos[agent_id]["spawned"] = child_id
        self._rebuild_position_indices()

        dead_agents: List[str] = []
        for agent_id in current_agents:
            organism = self.agent_to_object[agent_id]
            if (
                agent_id in eaten_rabbits
                or organism.energy <= 0
                or (organism.max_age > 0 and organism.age >= organism.max_age)
            ):
                dead_agents.append(agent_id)

        observations: Dict[str, Dict[str, np.ndarray]] = {}
        for agent_id in current_agents:
            if agent_id in self.agent_to_object:
                observations[agent_id] = self._get_obs(agent_id)

        for agent_id in dead_agents:
            terminations[agent_id] = True
            rewards[agent_id] -= 10.0
            infos[agent_id]["true_generation"] = self.agent_generations[agent_id]
            self._kill_agent(agent_id)
        self._rebuild_position_indices()

        episode_truncated = self.max_steps is not None and self._step_count >= self.max_steps
        if episode_truncated:
            for agent_id in list(self.agents):
                truncations[agent_id] = True
            self.agents.clear()
            self.agent_to_object.clear()
            self._rebuild_position_indices()

        for agent_id in self.agents:
            if agent_id not in rewards:
                rewards[agent_id] = 0.0
            if agent_id not in terminations:
                terminations[agent_id] = False
            if agent_id not in truncations:
                truncations[agent_id] = episode_truncated
            infos[agent_id] = {
                "true_generation": self.agent_generations[agent_id],
                "species": self._species_of(agent_id),
            }
            observations[agent_id] = self._get_obs(agent_id)

        self._regrow_plants()
        self._rebuild_position_indices()

        return observations, rewards, terminations, truncations, infos

    def render(self):
        if self.render_mode is None:
            return None
        if self.render_mode == "rgb_array":
            return self._render_rgb_array()
        if self.render_mode != "human":
            return None

        try:
            import tkinter as tk
        except Exception:
            return None

        if self._tk_root is None:
            self._tk_root = tk.Tk()
            self._tk_root.title("EcosystemEnv")
            size = self.grid_size * self._cell_px
            self._tk_canvas = tk.Canvas(self._tk_root, width=size, height=size)
            self._tk_canvas.pack()

        assert self._tk_canvas is not None
        self._tk_canvas.delete("all")

        colors = {
            TerrainType.WATER: "#2b6cb0",
            TerrainType.SAND: "#d6bc7b",
            TerrainType.DIRT: "#6b8e23",
            TerrainType.MOUNTAIN: "#4a5568",
        }

        for x in range(self.grid_size):
            for y in range(self.grid_size):
                x0 = x * self._cell_px
                y0 = y * self._cell_px
                x1 = x0 + self._cell_px
                y1 = y0 + self._cell_px
                self._tk_canvas.create_rectangle(
                    x0,
                    y0,
                    x1,
                    y1,
                    fill=colors[self.terrain_grid[(x, y)]],
                    width=0,
                )

        for x, y in self.plants:
            x0 = x * self._cell_px + self._cell_px // 4
            y0 = y * self._cell_px + self._cell_px // 4
            x1 = x0 + self._cell_px // 2
            y1 = y0 + self._cell_px // 2
            self._tk_canvas.create_oval(x0, y0, x1, y1, fill="#22c55e", width=0)

        for agent_id in self.agents:
            organism = self.agent_to_object[agent_id]
            color = (
                "#f97316"
                if self._species_of(agent_id) == self.SPECIES_FOX
                else "#f8fafc"
            )
            x0 = organism.x * self._cell_px + 1
            y0 = organism.y * self._cell_px + 1
            x1 = x0 + self._cell_px - 2
            y1 = y0 + self._cell_px - 2
            self._tk_canvas.create_rectangle(x0, y0, x1, y1, fill=color, width=0)

        self._tk_root.update_idletasks()
        self._tk_root.update()
        return None

    def close(self) -> None:
        if self._tk_root is not None:
            self._tk_root.destroy()
        self._tk_root = None
        self._tk_canvas = None

    def _spawn_initial_plants(self) -> None:
        dirt_cells = [
            (x, y)
            for x in range(self.grid_size)
            for y in range(self.grid_size)
            if self.terrain_grid[(x, y)] == TerrainType.DIRT
        ]
        self._rng.shuffle(dirt_cells)
        for x, y in dirt_cells[: self.initial_plants]:
            self.plants.add((x, y))

    def _spawn_initial_animals(self, species: str, count: int) -> None:
        for _ in range(count):
            pos = self._sample_empty_land_position()
            if pos is None:
                break
            self._spawn_agent(species, pos[0], pos[1])

    def _spawn_agent(
        self,
        species: str,
        x: int,
        y: int,
        genome=None,
    ) -> Optional[str]:
        queue = (
            self.available_rabbits
            if species == self.SPECIES_RABBIT
            else self.available_foxes
        )
        if not queue:
            return None

        new_id = queue.popleft()
        self.agent_generations[new_id] += 1

        if species == self.SPECIES_RABBIT:
            organism = Herbivore(x, y, genome=genome)
        else:
            organism = Carnivore(x, y, genome=genome)

        self.agent_to_object[new_id] = organism
        self.agents.append(new_id)
        pos = (x, y)
        self._occupied_positions.add(pos)
        if species == self.SPECIES_RABBIT:
            self._rabbit_positions.add(pos)
        else:
            self._fox_positions.add(pos)
        return new_id

    def _kill_agent(self, agent_id: str) -> None:
        organism = self.agent_to_object.get(agent_id)
        if organism is not None:
            pos = (organism.x, organism.y)
            self._occupied_positions.discard(pos)
            if self._species_of(agent_id) == self.SPECIES_RABBIT:
                self._rabbit_positions.discard(pos)
            else:
                self._fox_positions.discard(pos)
        queue = (
            self.available_rabbits
            if self._species_of(agent_id) == self.SPECIES_RABBIT
            else self.available_foxes
        )
        queue.append(agent_id)
        if agent_id in self.agent_to_object:
            del self.agent_to_object[agent_id]
        if agent_id in self.agents:
            self.agents.remove(agent_id)

    def _sample_empty_land_position(self) -> Optional[Position]:
        candidates = [
            (x, y)
            for x in range(self.grid_size)
            for y in range(self.grid_size)
            if is_land_passable(self.terrain_grid[(x, y)]) and (x, y) not in self._occupied_positions
        ]
        if not candidates:
            return None
        return self._rng.choice(candidates)

    def _find_birth_position(
        self,
        x: int,
        y: int,
        occupied: Set[Position],
    ) -> Optional[Position]:
        candidates: List[Position] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not self._is_valid_target(nx, ny):
                    continue
                if (nx, ny) in occupied:
                    continue
                candidates.append((nx, ny))
        if not candidates:
            return None
        return self._rng.choice(candidates)

    def _regrow_plants(self) -> None:
        growth_chance = config.get_plant_reproduction_chance(self._step_count)
        if self._rng.random() >= growth_chance:
            return

        candidates = [
            (x, y)
            for x in range(self.grid_size)
            for y in range(self.grid_size)
            if self.terrain_grid[(x, y)] == TerrainType.DIRT
            and (x, y) not in self.plants
            and (x, y) not in self._occupied_positions
        ]
        if candidates:
            self.plants.add(self._rng.choice(candidates))

    def _get_obs(self, agent_id: str) -> Dict[str, np.ndarray]:
        organism = self.agent_to_object[agent_id]
        radius = 5

        grid_obs = np.zeros((4, 11, 11), dtype=np.float32)
        terrain_channel_map = {
            TerrainType.WATER: -1.0,
            TerrainType.SAND: -0.33,
            TerrainType.DIRT: 0.33,
            TerrainType.MOUNTAIN: 1.0,
        }

        for iy, dy in enumerate(range(-radius, radius + 1)):
            for ix, dx in enumerate(range(-radius, radius + 1)):
                x = organism.x + dx
                y = organism.y + dy
                if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
                    grid_obs[0, iy, ix] = -1.0
                    continue

                pos = (x, y)
                terrain = self.terrain_grid[pos]
                grid_obs[0, iy, ix] = terrain_channel_map[terrain]
                grid_obs[1, iy, ix] = 1.0 if pos in self.plants else 0.0
                grid_obs[2, iy, ix] = 1.0 if pos in self._rabbit_positions else 0.0
                grid_obs[3, iy, ix] = 1.0 if pos in self._fox_positions else 0.0

        state_obs = np.array(
            [
                self._normalized_energy(organism),
                1.0 if organism.max_age <= 0 else min(1.0, organism.age / organism.max_age),
                1.0 if self._can_reproduce(organism) else 0.0,
            ],
            dtype=np.float32,
        )

        return {
            "grid": grid_obs,
            "state": state_obs,
            "action_mask": self._get_action_mask(agent_id),
        }

    def _normalized_energy(self, organism: Animal) -> float:
        if isinstance(organism, Herbivore):
            max_energy = self.HERBIVORE_MAX_ENERGY_FACTOR * organism.genome.size
        else:
            max_energy = self.CARNIVORE_MAX_ENERGY_FACTOR * organism.genome.size
        if max_energy <= 0:
            return 0.0
        return float(np.clip(organism.energy / max_energy, 0.0, 1.0))

    def _can_reproduce(self, organism: Animal) -> bool:
        if not self._is_reproductive_age(organism):
            return False
        if isinstance(organism, Herbivore):
            threshold = (
                self.HERBIVORE_MAX_ENERGY_FACTOR
                * self.REPRODUCE_FRACTION
                * organism.genome.size
            )
            return organism.energy > threshold
        threshold = (
            self.CARNIVORE_MAX_ENERGY_FACTOR
            * self.REPRODUCE_FRACTION
            * organism.genome.size
        )
        return organism.energy > threshold

    def _is_reproductive_age(self, organism: Animal) -> bool:
        maturity_age = max(1, int(organism.max_age * self.REPRODUCTION_MATURITY_AGE_RATIO))
        return organism.age >= maturity_age

    def _has_birth_space(self, x: int, y: int) -> bool:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not self._is_valid_target(nx, ny):
                    continue
                if (nx, ny) in self._occupied_positions:
                    continue
                return True
        return False

    def _get_action_mask(self, agent_id: str) -> np.ndarray:
        organism = self.agent_to_object[agent_id]
        mask = np.ones(6, dtype=np.int8)

        for action in (self.ACTION_UP, self.ACTION_DOWN, self.ACTION_LEFT, self.ACTION_RIGHT):
            dx, dy = self._action_to_delta(action)
            nx, ny = organism.x + dx, organism.y + dy
            if not self._is_valid_target(nx, ny):
                mask[action] = 0

        species = self._species_of(agent_id)
        pool_available = (
            len(self.available_rabbits) > 0
            if species == self.SPECIES_RABBIT
            else len(self.available_foxes) > 0
        )
        if not self._is_reproduction_allowed(organism, pool_available):
            mask[self.ACTION_REPRODUCE] = 0

        return mask

    def _is_reproduction_allowed(self, organism: Animal, pool_available: bool) -> bool:
        return (
            pool_available
            and self._can_reproduce(organism)
            and self._has_birth_space(organism.x, organism.y)
        )

    def _rebuild_position_indices(self) -> None:
        self._occupied_positions = set()
        self._rabbit_positions = set()
        self._fox_positions = set()
        for agent_id in self.agents:
            organism = self.agent_to_object.get(agent_id)
            if organism is None:
                continue
            pos = (organism.x, organism.y)
            self._occupied_positions.add(pos)
            if self._species_of(agent_id) == self.SPECIES_RABBIT:
                self._rabbit_positions.add(pos)
            else:
                self._fox_positions.add(pos)

    def _species_of(self, agent_id: str) -> str:
        return (
            self.SPECIES_RABBIT
            if agent_id.startswith(f"{self.SPECIES_RABBIT}_")
            else self.SPECIES_FOX
        )

    def _action_to_delta(self, action: int) -> Tuple[int, int]:
        if action == self.ACTION_UP:
            return 0, -1
        if action == self.ACTION_DOWN:
            return 0, 1
        if action == self.ACTION_LEFT:
            return -1, 0
        if action == self.ACTION_RIGHT:
            return 1, 0
        return 0, 0

    def _is_valid_target(self, x: int, y: int) -> bool:
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return False
        return is_land_passable(self.terrain_grid[(x, y)])

    def _render_rgb_array(self) -> np.ndarray:
        image = np.zeros((self.grid_size, self.grid_size, 3), dtype=np.uint8)
        terrain_colors = {
            TerrainType.WATER: (43, 108, 176),
            TerrainType.SAND: (214, 188, 123),
            TerrainType.DIRT: (107, 142, 35),
            TerrainType.MOUNTAIN: (74, 85, 104),
        }
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                image[y, x] = terrain_colors[self.terrain_grid[(x, y)]]
        for x, y in self.plants:
            image[y, x] = (34, 197, 94)
        for agent_id in self.agents:
            organism = self.agent_to_object[agent_id]
            image[organism.y, organism.x] = (
                (249, 115, 22)
                if self._species_of(agent_id) == self.SPECIES_FOX
                else (241, 245, 249)
            )
        return image
