from __future__ import annotations

import random
import time
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from organisms import Carnivore, Herbivore, Organism, Plant
import config
from terrain import (
    TerrainType,
    generate_terrain_grid,
    is_land_passable,
    is_plant_habitable,
)

TOrganism = TypeVar("TOrganism", bound=Organism)
Position = Tuple[int, int]


class Ecosystem:
    """Manages the grid world and orchestrates organism interactions."""

    def __init__(
        self,
        grid_size: int,
        num_plants: int,
        num_herbivores: int,
        num_carnivores: int,
        tick_delay: float = 0.2,
        manual_step: bool = False,
        theme: str = "light",
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

        # Initial population counts (used by params panel)
        self._init_plants = num_plants
        self._init_herbivores = num_herbivores
        self._init_carnivores = num_carnivores

        # Theme preference passed to UIManager
        self._initial_theme_dark = theme.lower() == "dark"

        # UI references (set in _create_window)
        self.window: Optional[tk.Tk] = None
        self.advance_var: Optional[tk.IntVar] = None
        self.ui_manager = None  # type: ignore[assignment]

        # Scale cell size so the grid fits comfortably on screen:
        # targets ~32 px for a 25×25 grid, clamped to [20, 40].
        self.cell_size = max(20, min(40, 800 // max(grid_size, 1)))
        self.window_closed = False
        self.stop_requested = False
        self.is_auto = not self.manual_step

        # Population history for charting
        self.plant_history: List[int] = []
        self.herbivore_history: List[int] = []
        self.carnivore_history: List[int] = []

        # Per-tick statistics
        self.births_this_tick: int = 0
        self.deaths_this_tick: int = 0
        self._last_tick_ms: float = 0.0

        self._generate_terrain()
        self._populate_initial_organisms(num_plants, num_herbivores, num_carnivores)

    def _generate_terrain(self) -> None:
        self.terrain_grid = generate_terrain_grid(self.grid_size)

    def _populate_initial_organisms(
        self, num_plants: int, num_herbivores: int, num_carnivores: int
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
            self.organisms.append(plant)
            self.grid[(x, y)] = plant

        available_land_positions = self._filter_unoccupied_positions(
            available_land_positions
        )

        for _ in range(num_herbivores):
            if not available_land_positions:
                break
            x, y = available_land_positions.pop()
            herbivore = Herbivore(x, y)
            self.organisms.append(herbivore)
            self.grid[(x, y)] = herbivore

        for _ in range(num_carnivores):
            if not available_land_positions:
                break
            x, y = available_land_positions.pop()
            carnivore = Carnivore(x, y)
            self.organisms.append(carnivore)
            self.grid[(x, y)] = carnivore

    def _get_spawn_positions(self, predicate: Callable[[Position], bool]) -> List[Position]:
        """Return all grid positions matching the provided predicate."""
        return [
            (x, y)
            for x in range(self.grid_size)
            for y in range(self.grid_size)
            if predicate((x, y))
        ]

    def _filter_unoccupied_positions(self, positions: List[Position]) -> List[Position]:
        """Return only positions that are currently not occupied by organisms."""
        return [position for position in positions if position not in self.grid]

    def run(self, total_ticks: int) -> None:
        if self.window is None:
            self._create_window()

        for _ in range(total_ticks):
            if not self.organisms:
                print("All organisms have perished. Simulation ends.")
                return

            self.tick_count += 1
            tick_start = time.time()

            order = list(self.organisms)
            random.shuffle(order)

            for organism in order:
                if not organism.alive:
                    continue
                organism.update(self)

            self._finalize_tick()
            self._last_tick_ms = (time.time() - tick_start) * 1000

            self.display()
            if self.window_closed or self.stop_requested:
                print("Simulation stopped by user.")
                return

            if self.is_auto:
                if self.tick_delay > 0:
                    self.window.update()
                    time.sleep(self.tick_delay)
                else:
                    self.window.update()
            else:
                self.ui_manager.set_status(
                    f"Tick {self.tick_count} — Click Next Tick or Quit to stop."
                )
                self.advance_var.set(0)
                self.window.wait_variable(self.advance_var)
                if self.stop_requested:
                    print("Simulation stopped by user.")
                    return

        if self.window and not self.window_closed:
            self.ui_manager.set_simulation_complete()
            self.window.update()
            # Keep the window open and processing events until user closes it
            while not self.window_closed:
                try:
                    self.window.update()
                    time.sleep(0.05)  # Prevent busy-waiting
                except tk.TclError:
                    break

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
                organism.alive = True
                self.organisms.append(organism)
                self.grid[(organism.x, organism.y)] = organism
                self.births_this_tick += 1
            self._pending_additions.clear()

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

    def step(self) -> None:
        """Advance the simulation by exactly one tick (used by GameUI tick loop)."""
        if not self.organisms:
            return

        self.tick_count += 1
        tick_start = time.time()

        order = list(self.organisms)
        random.shuffle(order)

        for organism in order:
            if not organism.alive:
                continue
            organism.update(self)

        self._finalize_tick()
        self._last_tick_ms = (time.time() - tick_start) * 1000

        # Record population history
        plant_count = sum(1 for o in self.organisms if isinstance(o, Plant) and o.alive)
        herb_count = sum(1 for o in self.organisms if isinstance(o, Herbivore) and o.alive)
        carn_count = sum(1 for o in self.organisms if isinstance(o, Carnivore) and o.alive)
        self.plant_history.append(plant_count)
        self.herbivore_history.append(herb_count)
        self.carnivore_history.append(carn_count)

    def get_display_data(self) -> Dict[str, Any]:
        """Compute and return the current display data dict for UI panels."""
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
        """Return a summary statistics dict suitable for the result panel."""
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

    def get_adjacent_empty_cells(self, x: int, y: int) -> List[Position]:
        return [
            (nx, ny)
            for nx, ny in self.get_adjacent_positions(x, y)
            if self.get_organism_at(nx, ny) is None
            and is_land_passable(self.get_terrain(nx, ny))
        ]

    def get_adjacent_organisms(
        self, x: int, y: int, organism_type: Type[TOrganism]
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

    def _create_window(self) -> None:
        from ui_manager import UIManager

        self.ui_manager = UIManager(self, is_dark=self._initial_theme_dark)
        self.window = self.ui_manager.window
        self.advance_var = self.ui_manager.advance_var

    def queue_add_organism(self, organism: Organism) -> None:
        organism.alive = False  # Prevent acting before addition
        self._pending_additions.append(organism)

    def queue_remove_organism(self, organism: Organism) -> None:
        if not organism.alive:
            return
        organism.alive = False
        self.grid.pop((organism.x, organism.y), None)
        self._pending_removals.append(organism)

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

    def display(self) -> None:
        plant_count = 0
        herbivore_count = 0
        carnivore_count = 0
        total_age = 0
        age_count = 0
        total_energy = 0.0
        energy_count = 0

        grid_rows = [["." for _ in range(self.grid_size)] for _ in range(self.grid_size)]

        for organism in self.organisms:
            if not organism.alive:
                continue
            grid_rows[organism.y][organism.x] = organism.symbol
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

        self.plant_history.append(plant_count)
        self.herbivore_history.append(herbivore_count)
        self.carnivore_history.append(carnivore_count)

        print(
            f"--- Tick {self.tick_count} | Plants: {plant_count} "
            f"| Herbivores: {herbivore_count} | Carnivores: {carnivore_count} "
            f"| Season: {config.get_current_season(self.tick_count)} ---"
        )
        for row in grid_rows:
            print(" ".join(row))

        if self.window_closed:
            return

        if self.ui_manager is None:
            return

        data = {
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
            "season": config.get_current_season(self.tick_count),
            "season_emoji": config.SEASON_EMOJIS.get(
                config.get_current_season(self.tick_count), ""
            ),
        }
        self.ui_manager.update(data)
