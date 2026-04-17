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
    ) -> None:
        self.grid_size = grid_size
        self.tick_delay = tick_delay
        self.manual_step = manual_step
        self.tick_count = 0
        self.organisms: List[Organism] = []
        self.grid: Dict[Position, Organism] = {}
        self._pending_additions: List[Organism] = []
        self._pending_removals: List[Organism] = []
        self.window: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        self.chart_canvas: Optional[tk.Canvas] = None
        self.status_label: Optional[tk.Label] = None
        self.plant_label: Optional[tk.Label] = None
        self.herbivore_label: Optional[tk.Label] = None
        self.carnivore_label: Optional[tk.Label] = None
        self.next_button: Optional[tk.Button] = None
        self.auto_button: Optional[tk.Button] = None
        self.quit_button: Optional[tk.Button] = None
        self.control_frame: Optional[tk.Frame] = None
        self.season_label: Optional[tk.Label] = None
        self.cell_size = 24
        self.window_closed = False
        self.advance_var: Optional[tk.IntVar] = None
        self.stop_requested = False
        self.is_auto = not self.manual_step
        self.plant_history: List[int] = []
        self.herbivore_history: List[int] = []
        self.carnivore_history: List[int] = []

        self._populate_initial_organisms(
            num_plants, num_herbivores, num_carnivores
        )

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
            order = list(self.organisms)
            random.shuffle(order)

            for organism in order:
                if not organism.alive:
                    continue
                organism.update(self)

            self._finalize_tick()
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
                self.status_label.config(
                    text=f"Tick {self.tick_count} — Click Next Tick or Quit to stop."
                )
                self.advance_var.set(0)
                self.window.wait_variable(self.advance_var)
                if self.stop_requested:
                    print("Simulation stopped by user.")
                    return

        if self.window and not self.window_closed:
            self._draw_history_chart()
            self.status_label.config(text="Simulation complete.")
            self.window.update()

    def _finalize_tick(self) -> None:
        if self._pending_removals:
            removal_set = set(self._pending_removals)
            self.organisms = [
                organism
                for organism in self.organisms
                if organism.alive and organism not in removal_set
            ]
            self._pending_removals.clear()

        if self._pending_additions:
            for organism in self._pending_additions:
                if (organism.x, organism.y) in self.grid:
                    continue
                organism.alive = True
                self.organisms.append(organism)
                self.grid[(organism.x, organism.y)] = organism
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
        self.window = tk.Tk()
        self.window.title("Ecosystem Viewer")
        width = self.grid_size * self.cell_size + 10
        height = self.grid_size * self.cell_size + 120
        self.canvas = tk.Canvas(self.window, width=width, height=height - 60)
        self.canvas.pack()
        self.status_label = tk.Label(self.window, text="", font=("Consolas", 11))
        self.status_label.pack(pady=4)

        counts_frame = tk.Frame(self.window)
        counts_frame.pack(pady=4)

        self.plant_label = tk.Label(
            counts_frame,
            text="Plants: 0",
            font=("Consolas", 11),
            fg="#2e7d32",
        )
        self.plant_label.pack(side="left", padx=8)

        self.herbivore_label = tk.Label(
            counts_frame,
            text="Herbivores: 0",
            font=("Consolas", 11),
            fg="#f57f17",
        )
        self.herbivore_label.pack(side="left", padx=8)

        self.carnivore_label = tk.Label(
            counts_frame,
            text="Carnivores: 0",
            font=("Consolas", 11),
            fg="#c62828",
        )
        self.carnivore_label.pack(side="left", padx=8)

        self.season_label = tk.Label(
            counts_frame,
            text="Season: —",
            font=("Consolas", 11),
            fg="#5c6bc0",
        )
        self.season_label.pack(side="left", padx=8)

        self.control_frame = tk.Frame(self.window)
        self.control_frame.pack(pady=4)

        self.advance_var = tk.IntVar(master=self.window, value=0)

        self.next_button = tk.Button(
            self.control_frame,
            text="Next Tick",
            width=12,
            command=self._on_next_tick,
        )
        self.next_button.pack(side="left", padx=4)

        self.auto_button = tk.Button(
            self.control_frame,
            text="Auto Run" if not self.is_auto else "Pause",
            width=12,
            command=self._on_toggle_auto,
        )
        self.auto_button.pack(side="left", padx=4)

        self.quit_button = tk.Button(
            self.control_frame,
            text="Quit",
            width=12,
            command=self._on_quit,
        )
        self.quit_button.pack(side="left", padx=4)

        chart_label = tk.Label(self.window, text="Population history", font=("Consolas", 11, "bold"))
        chart_label.pack(pady=(10, 0))

        self.chart_canvas = tk.Canvas(
            self.window,
            width=self.grid_size * self.cell_size + 10,
            height=180,
            bg="#f7f7f7",
        )
        self.chart_canvas.pack(pady=4)

        self.window.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _on_next_tick(self) -> None:
        if self.window_closed:
            return
        self.advance_var.set(1)

    def _on_toggle_auto(self) -> None:
        if self.window_closed:
            return
        self.is_auto = not self.is_auto
        if self.auto_button:
            self.auto_button.config(text="Pause" if self.is_auto else "Auto Run")
        if self.is_auto:
            self.advance_var.set(1)

    def _on_quit(self) -> None:
        self.stop_requested = True
        self.window_closed = True
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass

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
        grid = [["." for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        plant_count = 0
        herbivore_count = 0
        carnivore_count = 0

        for organism in self.organisms:
            if not organism.alive:
                continue
            grid[organism.y][organism.x] = organism.symbol
            if isinstance(organism, Plant):
                plant_count += 1
            elif isinstance(organism, Herbivore):
                herbivore_count += 1
            elif isinstance(organism, Carnivore):
                carnivore_count += 1

        self.plant_history.append(plant_count)
        self.herbivore_history.append(herbivore_count)
        self.carnivore_history.append(carnivore_count)

        print(
            f"--- Tick {self.tick_count} | Plants: {plant_count} "
            f"| Herbivores: {herbivore_count} | Carnivores: {carnivore_count} "
            f"| Season: {config.get_current_season(self.tick_count)} ---"
        )
        for row in grid:
            print(" ".join(row))

        if self.window_closed:
            return

        if self.window is None or self.canvas is None or self.status_label is None:
            self._create_window()

        assert self.canvas is not None and self.status_label is not None
        self.canvas.delete("all")

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                x1 = x * self.cell_size
                y1 = y * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                occupant = self.grid.get((x, y))
                if occupant and occupant.alive:
                    if isinstance(occupant, Plant):
                        fill_color = "#82c784"
                        symbol = "🌿"
                    elif isinstance(occupant, Herbivore):
                        fill_color = "#ffd54f"
                        symbol = "🐇"
                    elif isinstance(occupant, Carnivore):
                        fill_color = "#e57373"
                        symbol = "🐺"
                    else:
                        fill_color = "#bdbdbd"
                        symbol = "?"
                else:
                    fill_color = "#ffffff"
                    symbol = ""

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=fill_color,
                    outline="#bbbbbb",
                )
                if symbol:
                    self.canvas.create_text(
                        x1 + self.cell_size / 2,
                        y1 + self.cell_size / 2,
                        text=symbol,
                        font=("Segoe UI Emoji", int(self.cell_size * 0.6)),
                    )

        self.status_label.config(
            text=f"Tick {self.tick_count} — Simulation running"
        )
        if self.plant_label:
            self.plant_label.config(text=f"Plants: {plant_count}")
        if self.herbivore_label:
            self.herbivore_label.config(text=f"Herbivores: {herbivore_count}")
        if self.carnivore_label:
            self.carnivore_label.config(text=f"Carnivores: {carnivore_count}")
        if self.season_label:
            season = config.get_current_season(self.tick_count)
            emoji = config.SEASON_EMOJIS.get(season, "")
            self.season_label.config(text=f"Season: {emoji} {season}")

        self._draw_history_chart()

        try:
            self.window.update_idletasks()
            self.window.update()
        except tk.TclError:
            self.window_closed = True

    def _draw_history_chart(self) -> None:
        if self.chart_canvas is None:
            return

        self.chart_canvas.delete("all")
        history_length = len(self.plant_history)
        if history_length == 0:
            return

        width = int(self.chart_canvas.winfo_width())
        height = int(self.chart_canvas.winfo_height())
        if width <= 0:
            width = self.grid_size * self.cell_size + 10
        if height <= 0:
            height = 180

        margin = 30
        legend_width = 110
        legend_spacing = 10
        chart_width = width - 2 * margin - legend_width - legend_spacing
        chart_height = height - 2 * margin
        max_value = max(
            max(self.plant_history),
            max(self.herbivore_history),
            max(self.carnivore_history),
            1,
        )
        if history_length == 1:
            x_step = chart_width
        else:
            x_step = chart_width / (history_length - 1)
        y_scale = chart_height / max_value

        self.chart_canvas.create_line(
            margin,
            margin,
            margin,
            height - margin,
            fill="#444444",
        )
        self.chart_canvas.create_line(
            margin,
            height - margin,
            margin + chart_width,
            height - margin,
            fill="#444444",
        )

        for tick in range(0, history_length, max(1, history_length // 10)):
            x = margin + tick * x_step
            self.chart_canvas.create_text(
                x,
                height - margin + 12,
                text=str(tick + 1),
                font=("Consolas", 9),
                fill="#333333",
            )

        def draw_line(history: List[int], color: str) -> None:
            points = []
            for index, value in enumerate(history):
                x = margin + index * x_step
                y = height - margin - value * y_scale
                points.extend([x, y])
            if len(points) >= 4:
                self.chart_canvas.create_line(
                    *points,
                    fill=color,
                    width=2,
                    smooth=True,
                )
            for index, value in enumerate(history):
                x = margin + index * x_step
                y = height - margin - value * y_scale
                self.chart_canvas.create_oval(
                    x - 3,
                    y - 3,
                    x + 3,
                    y + 3,
                    fill=color,
                    outline=color,
                )

        draw_line(self.plant_history, "#388e3c")
        draw_line(self.herbivore_history, "#f9a825")
        draw_line(self.carnivore_history, "#c62828")

        legend_x = width - margin - legend_width
        legend_y = margin + 5
        self.chart_canvas.create_rectangle(
            legend_x,
            legend_y,
            legend_x + legend_width,
            legend_y + 60,
            fill="#ffffff",
            outline="#cccccc",
        )
        self.chart_canvas.create_text(
            legend_x + 8,
            legend_y + 12,
            text="Legend",
            anchor="w",
            font=("Consolas", 9, "bold"),
        )
        self.chart_canvas.create_line(
            legend_x + 12,
            legend_y + 28,
            legend_x + 28,
            legend_y + 28,
            fill="#388e3c",
            width=2,
        )
        self.chart_canvas.create_text(
            legend_x + 36,
            legend_y + 28,
            text="Plants",
            anchor="w",
            fill="#388e3c",
            font=("Consolas", 9),
        )
        self.chart_canvas.create_line(
            legend_x + 12,
            legend_y + 42,
            legend_x + 28,
            legend_y + 42,
            fill="#f9a825",
            width=2,
        )
        self.chart_canvas.create_text(
            legend_x + 36,
            legend_y + 42,
            text="Herbivores",
            anchor="w",
            fill="#f9a825",
            font=("Consolas", 9),
        )
        self.chart_canvas.create_line(
            legend_x + 12,
            legend_y + 56,
            legend_x + 28,
            legend_y + 56,
            fill="#c62828",
            width=2,
        )
        self.chart_canvas.create_text(
            legend_x + 36,
            legend_y + 56,
            text="Carnivores",
            anchor="w",
            fill="#c62828",
            font=("Consolas", 9),
        )
