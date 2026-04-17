from __future__ import annotations

import random
import time
import tkinter as tk
from typing import Dict, List, Optional, Tuple, Type, TypeVar

from organisms import Carnivore, Herbivore, Organism, Plant
import config

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

        self.cell_size = 24
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

        self._populate_initial_organisms(num_plants, num_herbivores, num_carnivores)

    def _populate_initial_organisms(
        self, num_plants: int, num_herbivores: int, num_carnivores: int
    ) -> None:
        positions = self._sample_unique_positions(
            num_plants + num_herbivores + num_carnivores
        )

        for _ in range(num_plants):
            x, y = positions.pop()
            plant = Plant(x, y)
            self.organisms.append(plant)
            self.grid[(x, y)] = plant

        for _ in range(num_herbivores):
            x, y = positions.pop()
            herbivore = Herbivore(x, y)
            self.organisms.append(herbivore)
            self.grid[(x, y)] = herbivore

        for _ in range(num_carnivores):
            x, y = positions.pop()
            carnivore = Carnivore(x, y)
            self.organisms.append(carnivore)
            self.grid[(x, y)] = carnivore

    def _sample_unique_positions(self, count: int) -> List[Position]:
        all_positions = [
            (x, y) for x in range(self.grid_size) for y in range(self.grid_size)
        ]
        random.shuffle(all_positions)
        return all_positions[:count]

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

    def get_adjacent_empty_cells(self, x: int, y: int) -> List[Position]:
        return [
            (nx, ny)
            for nx, ny in self.get_adjacent_positions(x, y)
            if self.get_organism_at(nx, ny) is None
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
