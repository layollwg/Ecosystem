from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme
    from ecosystem import Ecosystem

from ui_widgets import TooltipManager
from ui_overlay import DrawerPanel, PlaybackOverlay, StatsOverlay
from camera_system import CameraSystem
from organisms import Carnivore, Herbivore, Plant
from terrain import TerrainType


class SimulationPanel(tk.Frame):
    """Full-screen simulation panel with camera-based zoom/pan and overlay UI.

    Layout
    ------
    ::

        ┌─────────────────────────────────────────────────────────┐
        │  GRID CANVAS  (fills entire frame)                      │
        │  ┌──────────────────────┐             ┌──────────────┐  │
        │  │ 🌍 ECOSYSTEM          │             │ ✕  📊 Data   │  │
        │  │ Tick 123 🌱           │             │ Statistics   │  │
        │  │ 🌿 45  🐇 28  🐺 8    │             │ Population   │  │
        │  │ Balance: ████░░ 75%  │             │ Chart        │  │
        │  │ FPS: 60              │             └──────────────┘  │
        │  └──────────────────────┘                               │
        │                                                         │
        │           ┌───────────────────────────┐                 │
        │           │ [⏸ Pause] [⏵ Step] [⏹ Stop] │                │
        │           │  Speed: ◀──────●──────▶   │                 │
        │           └───────────────────────────┘                 │
        └─────────────────────────────────────────────────────────┘

    Controls
    --------
    * **Mouse wheel** — zoom in / out (centred on cursor)
    * **Middle-button drag** — pan the map
    * **Right-button drag** — pan the map
    * **Double left-click** — reset to default (fit-all) view
    * **⏵ Step** button — execute exactly one tick while staying paused
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: "Theme",
        ecosystem: "Ecosystem",
        total_ticks: int,
        on_pause_toggle: Callable[[], None],
        on_step: Callable[[], None],
        on_stop: Callable[[], None],
        on_speed_change: Callable[[float], None],
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._eco = ecosystem
        self._total_ticks = total_ticks
        self._on_pause_toggle = on_pause_toggle
        self._on_step = on_step
        self._on_stop = on_stop
        self._on_speed_change = on_speed_change
        self._paused = False
        self._camera_initialized = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._build()

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_display(self, data: Dict[str, Any]) -> None:
        """Redraw all UI elements with the latest simulation data."""
        self._update_entities_only()
        try:
            self._stats_overlay.update(data)
            self._drawer.update_data(data)
        except tk.TclError:
            pass

    def set_status(self, text: str) -> None:
        """Update the status message shown inside the stats overlay."""
        try:
            self._stats_overlay.set_status(text)
        except (tk.TclError, AttributeError):
            pass

    def set_complete(self) -> None:
        """Mark the simulation as finished."""
        self.set_status("✅  Complete — loading results…")

    def set_paused(self, paused: bool) -> None:
        """Reflect the paused state in the playback overlay."""
        self._paused = paused
        try:
            self._playback.set_paused(paused)
        except (tk.TclError, AttributeError):
            pass

    @property
    def speed_var(self) -> tk.DoubleVar:
        """The speed (delay) variable exposed for external bindings."""
        return self._playback.speed_var

    # ── Build ───────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = self._theme
        self.config(bg=t["bg"])

        eco = self._eco
        world_w = eco.grid_size * eco.cell_size
        world_h = eco.grid_size * eco.cell_size

        # 1. Full-screen grid canvas
        self._grid_canvas = tk.Canvas(
            self,
            bg=t["grid_bg"],
            highlightthickness=0,
        )
        self._grid_canvas.pack(fill="both", expand=True)

        # 2. Camera system — viewport dimensions start at 1x1 and are updated
        #    on the first <Configure> event once the canvas is rendered.
        self._camera = CameraSystem(1, 1, world_w, world_h)

        # 3. Tooltip (hover card on grid cells)
        self._tooltip = TooltipManager(self.winfo_toplevel(), theme=self._theme)

        # 4. Overlay panels (placed on top of the canvas via place() geometry)
        #    Stats — top-left
        self._stats_overlay = StatsOverlay(self, t)
        self._stats_overlay.place(x=8, y=8)

        #    Playback — bottom-centre
        self._playback = PlaybackOverlay(
            self, t,
            on_pause_toggle=self._on_pause_toggle,
            on_step=self._on_step,
            on_stop=self._on_stop,
            on_speed_change=self._on_speed_change,
            initial_delay=eco.tick_delay,
        )
        self._playback.place(relx=0.5, rely=1.0, y=-8, anchor="s")

        #    Drawer — right side (starts open)
        self._drawer = DrawerPanel(self, t)
        self._drawer.place(
            relx=1.0, y=0, anchor="ne",
            relheight=1.0, width=DrawerPanel.OPEN_W,
        )

        # 5. Canvas event bindings
        self._grid_canvas.bind("<Configure>",       self._on_canvas_resize)
        self._grid_canvas.bind("<MouseWheel>",      self._on_mousewheel)   # Win/macOS
        self._grid_canvas.bind("<Button-4>",        self._on_scroll_up)    # Linux
        self._grid_canvas.bind("<Button-5>",        self._on_scroll_down)  # Linux
        self._grid_canvas.bind("<ButtonPress-2>",   self._on_pan_start)    # Middle btn
        self._grid_canvas.bind("<B2-Motion>",       self._on_pan_motion)
        self._grid_canvas.bind("<ButtonPress-3>",   self._on_pan_start)    # Right btn
        self._grid_canvas.bind("<B3-Motion>",       self._on_pan_motion)
        self._grid_canvas.bind("<Double-Button-1>", self._on_reset_view)   # Dbl-click
        self._grid_canvas.bind("<Motion>",          self._on_grid_motion)
        self._grid_canvas.bind("<Leave>",           self._on_grid_leave)

    # ── Canvas event handlers ─────────────────────────────────────────────────

    def _on_canvas_resize(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._camera.viewport_width  = event.width
        self._camera.viewport_height = event.height
        if not self._camera_initialized:
            self._camera.reset_view(ui_padding_x=self._stats_padding())
            self._camera_initialized = True
        self._redraw_full_scene()

    def _stats_padding(self) -> int:
        """Return the horizontal pixel width to reserve for the stats overlay."""
        w = self._stats_overlay.winfo_reqwidth()
        # Add 8 px left margin (the overlay is placed at x=8) plus an 8 px
        # right gap so the map does not start flush against the panel edge.
        return (w + 16) if w > 0 else 320

    def _on_mousewheel(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        # Windows / macOS: event.delta > 0 means scroll up => zoom in
        factor = 1.1 if event.delta > 0 else (1.0 / 1.1)
        self._camera.zoom_at(factor, event.x, event.y)
        self._redraw_full_scene()

    def _on_scroll_up(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._camera.zoom_at(1.1, event.x, event.y)
        self._redraw_full_scene()

    def _on_scroll_down(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._camera.zoom_at(1.0 / 1.1, event.x, event.y)
        self._redraw_full_scene()

    def _on_pan_start(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._pan_start_x = event.x
        self._pan_start_y = event.y

    def _on_pan_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        self._camera.pan(dx, dy)
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._redraw_full_scene()

    def _on_reset_view(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._camera.reset_view(ui_padding_x=self._stats_padding())
        self._redraw_full_scene()

    # ── Grid rendering ────────────────────────────────────────────────────────

    def _iter_visible_cells(self):
        eco    = self._eco
        camera = self._camera

        cs = eco.cell_size
        min_wx, min_wy, max_wx, max_wy = camera.get_visible_bounds()

        min_cx = max(0, int(min_wx // cs))
        min_cy = max(0, int(min_wy // cs))
        max_cx = min(eco.grid_size - 1, int(max_wx // cs) + 1)
        max_cy = min(eco.grid_size - 1, int(max_wy // cs) + 1)
        for cy in range(min_cy, max_cy + 1):
            for cx in range(min_cx, max_cx + 1):
                wx1 = cx * cs
                wy1 = cy * cs
                sx1, sy1 = camera.world_to_screen(wx1,      wy1)
                sx2, sy2 = camera.world_to_screen(wx1 + cs, wy1 + cs)
                yield cx, cy, sx1, sy1, sx2, sy2

    def _terrain_fill(self, terrain: TerrainType) -> str:
        t = self._theme
        if terrain == TerrainType.WATER:
            return t.get("terrain_water", "#3B82F6")
        if terrain == TerrainType.SAND:
            return t.get("terrain_sand", "#D6B16A")
        if terrain == TerrainType.MOUNTAIN:
            return t.get("terrain_mountain", "#6B7280")
        return t.get("terrain_dirt", t["empty_fill"])

    def _redraw_full_scene(self) -> None:
        t      = self._theme
        canvas = self._grid_canvas

        canvas_w = canvas.winfo_width()
        canvas_h = canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return  # canvas not yet rendered

        canvas.config(bg=t["grid_bg"])
        canvas.delete("all")

        for cx, cy, sx1, sy1, sx2, sy2 in self._iter_visible_cells():
            terrain = self._eco.get_terrain(cx, cy)
            canvas.create_rectangle(
                sx1, sy1, sx2, sy2,
                fill=self._terrain_fill(terrain),
                outline=t["grid_line"],
                tags=("terrain",),
            )
        self._update_entities_only()

    def _update_entities_only(self) -> None:
        eco = self._eco
        t = self._theme
        canvas = self._grid_canvas
        canvas_w = canvas.winfo_width()
        canvas_h = canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return

        canvas.delete("entity")
        for cx, cy, sx1, sy1, sx2, sy2 in self._iter_visible_cells():
            occupant = eco.grid.get((cx, cy))
            if not (occupant and occupant.alive):
                continue
            if isinstance(occupant, Plant):
                fill, symbol = t["plant_fill"], "🌿"
            elif isinstance(occupant, Herbivore):
                fill, symbol = occupant.genome.get_hex_color(), "🐇"
            elif isinstance(occupant, Carnivore):
                fill, symbol = occupant.genome.get_hex_color(), "🐺"
            else:
                fill, symbol = t.get("accent_bg", "#444"), "?"

            canvas.create_rectangle(
                sx1, sy1, sx2, sy2,
                fill=fill, outline=t["grid_line"],
                tags=("entity",),
            )

            cell_px = sx2 - sx1
            if symbol and cell_px >= 8:
                font_size = max(8, int(cell_px * 0.55))
                canvas.create_text(
                    (sx1 + sx2) // 2, (sy1 + sy2) // 2,
                    text=symbol,
                    font=("Segoe UI Emoji", font_size),
                    tags=("entity",),
                )

    # ── Tooltip / hover ───────────────────────────────────────────────────────

    def _on_grid_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        eco = self._eco
        cs  = eco.cell_size
        wx, wy = self._camera.screen_to_world(event.x, event.y)
        gx = int(wx // cs)
        gy = int(wy // cs)

        if not (0 <= gx < eco.grid_size and 0 <= gy < eco.grid_size):
            self._tooltip.hide()
            return

        occupant = eco.grid.get((gx, gy))
        t = self._theme
        terrain = eco.get_terrain(gx, gy)
        terrain_name = terrain.name.title()
        if occupant and occupant.alive:
            kind = type(occupant).__name__
            if isinstance(occupant, Plant):
                icon, color = "🌿", t["text_plant"]
                lines = [
                    f"{icon}  {kind}  ({gx}, {gy})",
                    f"Terrain: {terrain_name}",
                    f"Age: {occupant.age}",
                    "Energy: N/A",
                ]
                secondary = t.get("fg_secondary", t["fg"])
                colors = [color, secondary, secondary, secondary]
            else:
                icon  = "🐇" if kind == "Herbivore" else "🐺"
                color = t["text_herbivore"] if kind == "Herbivore" else t["text_carnivore"]
                g = occupant.genome  # type: ignore[attr-defined]
                lines = [
                    f"{icon}  {kind}  ({gx}, {gy})",
                    f"Terrain: {terrain_name}",
                    f"Age: {occupant.age}  |  Energy: {occupant.energy:.1f}",  # type: ignore[attr-defined]
                    f"Size: {g.size:.2f}  Speed: {g.speed:.2f}  Vision: {g.vision}",
                    f"Metabolism: {g.metabolism:.2f}  |  {g.get_hex_color()}",
                ]
                secondary = t.get("fg_secondary", t["fg"])
                colors = [color, secondary, secondary, secondary, secondary]
        else:
            lines  = [f"Empty  ({gx}, {gy})", f"Terrain: {terrain_name}"]
            colors = [t["label_fg"], t.get("fg_secondary", t["fg"])]

        self._tooltip.show(lines, colors, event.x_root, event.y_root)

    def _on_grid_leave(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._tooltip.hide()
