from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme
    from ecosystem import Ecosystem

from ui_widgets import EnhancedChart, StatisticsPanel, TooltipManager
from organisms import Carnivore, Herbivore, Plant

_UI_FONT = "Arial"
_MONO_FONT = "Courier New"
_SIDEBAR_W = 270


class SimulationPanel(tk.Frame):
    """Panel displayed while the simulation is running.

    Layout mirrors the professional UIManager layout but lives inside the
    shared GameUI window rather than creating its own tk.Tk().

    Public API used by GameUI:
        update_display(data)  – redraw the grid, stats, chart
        set_status(text)      – update header status text
        set_complete()        – mark simulation as finished
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: "Theme",
        ecosystem: "Ecosystem",
        total_ticks: int,
        on_pause_toggle: Callable[[], None],
        on_stop: Callable[[], None],
        on_speed_change: Callable[[float], None],
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._eco = ecosystem
        self._total_ticks = total_ticks
        self._on_pause_toggle = on_pause_toggle
        self._on_stop = on_stop
        self._on_speed_change = on_speed_change
        self._paused = False
        self._build()

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_display(self, data: Dict[str, Any]) -> None:
        """Redraw all display elements from the latest simulation data dict."""
        tick = data.get("tick", 0)
        season = data.get("season", "")
        season_emoji = data.get("season_emoji", "")
        season_str = f"  {season_emoji} {season}" if season else ""
        state_str = "⏸ Paused" if self._paused else "▶ Running"
        progress = tick / max(self._total_ticks, 1)
        self._header_status.config(
            text=f"Tick {tick} / {self._total_ticks}{season_str}  —  {state_str}"
        )
        self._progress_bar_fill.place(relwidth=min(progress, 1.0))
        self._update_grid()
        self._stats_panel.update_stats(data)
        self._chart.draw(
            data.get("plant_history", []),
            data.get("herbivore_history", []),
            data.get("carnivore_history", []),
        )
        self._update_perf(data)

    def set_status(self, text: str) -> None:
        try:
            self._header_status.config(text=text)
        except tk.TclError:
            pass

    def set_complete(self) -> None:
        try:
            self._header_status.config(text="✅  Simulation complete — loading results…")
        except tk.TclError:
            pass

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        label = "▶  Resume" if paused else "⏸  Pause"
        try:
            self._pause_btn.config(text=label)
        except tk.TclError:
            pass

    @property
    def speed_var(self) -> tk.DoubleVar:
        return self._speed_var

    # ── Build ───────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = self._theme
        self.config(bg=t["bg"])

        self._build_header()

        main = tk.Frame(self, bg=t["bg"])
        main.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._build_grid_area(main)
        self._build_sidebar(main)
        self._build_chart_area()
        self._build_controls()

    # ── Header ──────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        t = self._theme
        hdr = tk.Frame(self, bg=t.get("header_bg", t["bg"]))
        hdr.pack(fill="x")

        tk.Label(
            hdr,
            text="🌍  ECOSYSTEM SIMULATOR",
            font=(_UI_FONT, 14, "bold"),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_accent", t["fg"]),
            padx=12, pady=6,
        ).pack(side="left")

        self._header_status = tk.Label(
            hdr,
            text="Initialising…",
            font=(_UI_FONT, 11),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_secondary", t["fg"]),
            padx=12,
        )
        self._header_status.pack(side="right")

        tk.Frame(self, bg=t.get("border_glow", t["border"]), height=2).pack(fill="x")

        # Progress bar
        bar_bg = tk.Frame(self, bg=t.get("accent_bg", t["panel_bg"]), height=4)
        bar_bg.pack(fill="x")
        self._progress_bar_fill = tk.Frame(
            bar_bg, bg=t.get("fg_highlight", "#00ff88"), height=4
        )
        self._progress_bar_fill.place(relx=0, rely=0, relwidth=0.0, relheight=1.0)

    # ── Grid area ───────────────────────────────────────────────────────────────

    def _build_grid_area(self, parent: tk.Widget) -> None:
        t = self._theme
        eco = self._eco
        cs = eco.cell_size
        canvas_w = eco.grid_size * cs
        canvas_h = eco.grid_size * cs
        vis_w = min(canvas_w, 580)
        vis_h = min(canvas_h, 580)

        left = tk.Frame(parent, bg=t["bg"])
        left.pack(side="left", fill="both")
        self._grid_outer = left

        border = tk.Frame(left, bg=t.get("border_glow", t["border"]), padx=1, pady=1)
        border.pack(padx=6, pady=6)
        self._grid_border = border

        scroll_f = tk.Frame(border, bg=t["grid_bg"])
        scroll_f.pack()

        h_bar = tk.Scrollbar(scroll_f, orient="horizontal")
        v_bar = tk.Scrollbar(scroll_f, orient="vertical")

        self._grid_canvas = tk.Canvas(
            scroll_f,
            width=vis_w, height=vis_h,
            scrollregion=(0, 0, canvas_w, canvas_h),
            xscrollcommand=h_bar.set,
            yscrollcommand=v_bar.set,
            bg=t["grid_bg"],
            highlightthickness=0,
        )
        if canvas_w > vis_w:
            h_bar.config(command=self._grid_canvas.xview)
            h_bar.pack(side="bottom", fill="x")
        if canvas_h > vis_h:
            v_bar.config(command=self._grid_canvas.yview)
            v_bar.pack(side="right", fill="y")
        self._grid_canvas.pack(side="left")

        self._tooltip = TooltipManager(self.winfo_toplevel())
        self._grid_canvas.bind("<Motion>", self._on_grid_motion)
        self._grid_canvas.bind("<Leave>",  self._on_grid_leave)

    def _update_grid(self) -> None:
        eco = self._eco
        t = self._theme
        canvas = self._grid_canvas
        canvas.config(bg=t["grid_bg"])
        canvas.delete("all")
        cs = eco.cell_size

        for y in range(eco.grid_size):
            for x in range(eco.grid_size):
                x1, y1 = x * cs, y * cs
                x2, y2 = x1 + cs, y1 + cs
                occupant = eco.grid.get((x, y))
                if occupant and occupant.alive:
                    if isinstance(occupant, Plant):
                        fill, symbol = t["plant_fill"], "🌿"
                    elif isinstance(occupant, Herbivore):
                        fill, symbol = t["herbivore_fill"], "🐇"
                    elif isinstance(occupant, Carnivore):
                        fill, symbol = t["carnivore_fill"], "🐺"
                    else:
                        fill, symbol = t.get("accent_bg", "#444"), "?"
                else:
                    fill, symbol = t["empty_fill"], ""

                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=t["grid_line"])
                if symbol:
                    canvas.create_text(
                        x1 + cs / 2, y1 + cs / 2,
                        text=symbol,
                        font=("Segoe UI Emoji", max(8, int(cs * 0.55))),
                    )

    def _on_grid_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        eco = self._eco
        cs = eco.cell_size
        gx = (event.x + int(self._grid_canvas.xview()[0] * eco.grid_size * cs)) // cs
        gy = (event.y + int(self._grid_canvas.yview()[0] * eco.grid_size * cs)) // cs
        if not (0 <= gx < eco.grid_size and 0 <= gy < eco.grid_size):
            self._tooltip.hide()
            return
        occupant = eco.grid.get((gx, gy))
        t = self._theme
        if occupant and occupant.alive:
            kind = type(occupant).__name__
            if isinstance(occupant, Plant):
                icon, color = "🌿", t["text_plant"]
                lines = [f"{icon}  {kind}  ({gx}, {gy})", f"Age: {occupant.age}", "Energy: N/A"]
                colors = [color, t.get("fg_secondary", t["fg"]), t.get("fg_secondary", t["fg"])]
            else:
                icon = "🐇" if kind == "Herbivore" else "🐺"
                color = t["text_herbivore"] if kind == "Herbivore" else t["text_carnivore"]
                lines = [
                    f"{icon}  {kind}  ({gx}, {gy})",
                    f"Age: {occupant.age}",
                    f"Energy: {occupant.energy}",  # type: ignore[attr-defined]
                ]
                colors = [color, t.get("fg_secondary", t["fg"]), t.get("fg_accent", t["fg"])]
        else:
            lines  = [f"Empty  ({gx}, {gy})"]
            colors = [t["label_fg"]]
        self._tooltip.show(lines, colors, event.x_root, event.y_root)

    def _on_grid_leave(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._tooltip.hide()

    # ── Stats sidebar ───────────────────────────────────────────────────────────

    def _build_sidebar(self, parent: tk.Widget) -> None:
        t = self._theme
        sidebar = tk.Frame(parent, bg=t["panel_bg"], width=_SIDEBAR_W)
        sidebar.pack(side="right", fill="y", padx=(0, 6), pady=6)
        sidebar.pack_propagate(False)
        self._stats_panel = StatisticsPanel(sidebar, self._theme)
        self._stats_panel.pack(fill="both", expand=True)

    # ── Chart ────────────────────────────────────────────────────────────────────

    def _build_chart_area(self) -> None:
        t = self._theme
        eco = self._eco
        outer = tk.Frame(self, bg=t["bg"])
        outer.pack(fill="x", padx=6, pady=(0, 2))

        hdr = tk.Frame(outer, bg=t["bg"])
        hdr.pack(fill="x", pady=(2, 0))
        tk.Label(
            hdr, text="📈  Population History",
            font=(_UI_FONT, 11, "bold"),
            bg=t["bg"], fg=t.get("fg_accent", t["fg"]),
        ).pack(side="left", padx=8)

        chart_w = eco.grid_size * eco.cell_size + _SIDEBAR_W + 8
        chart_w = max(chart_w, 600)
        self._chart = EnhancedChart(
            outer, self._theme,
            width=chart_w, height=160,
            bg=t["chart_bg"],
        )
        self._chart.pack(padx=8, pady=(2, 4))

    # ── Controls ─────────────────────────────────────────────────────────────────

    def _build_controls(self) -> None:
        t = self._theme
        tk.Frame(self, bg=t.get("border_glow", t["border"]), height=2).pack(fill="x")

        ctrl = tk.Frame(self, bg=t["bg"])
        ctrl.pack(fill="x", padx=8, pady=(4, 8))

        btn_row = tk.Frame(ctrl, bg=t["bg"])
        btn_row.pack(fill="x")

        def _btn(text: str, cmd: Any, width: int = 12) -> tk.Button:
            b = tk.Button(
                btn_row, text=text, width=width,
                font=(_UI_FONT, 10, "bold"),
                bg=t["button_bg"], fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=6, pady=4,
                cursor="hand2",
                command=cmd,
            )
            b.pack(side="left", padx=4, pady=2)
            return b

        self._pause_btn = _btn("⏸  Pause",  self._on_pause_clicked, width=12)
        _btn("⏹  Stop",   self._on_stop, width=10)

        # Performance labels on the right
        self._perf_fps      = tk.Label(btn_row, text="FPS: --",       font=(_UI_FONT, 9),
                                       bg=t["bg"], fg=t.get("perf_fg", t["fg"]))
        self._perf_tick_ms  = tk.Label(btn_row, text="Tick: -- ms",   font=(_UI_FONT, 9),
                                       bg=t["bg"], fg=t.get("perf_fg", t["fg"]))
        self._perf_organisms = tk.Label(btn_row, text="Organisms: --", font=(_UI_FONT, 9),
                                        bg=t["bg"], fg=t.get("perf_fg", t["fg"]))
        for lbl in (self._perf_fps, self._perf_tick_ms, self._perf_organisms):
            lbl.pack(side="right", padx=6)

        # Speed row
        speed_row = tk.Frame(ctrl, bg=t["bg"])
        speed_row.pack(fill="x", pady=(2, 0))

        tk.Label(
            speed_row, text="Speed (delay):",
            font=(_UI_FONT, 10), bg=t["bg"], fg=t["fg"],
        ).pack(side="left", padx=4)

        self._speed_var = tk.DoubleVar(value=self._eco.tick_delay)
        self._speed_var.trace_add("write", self._on_speed_change_internal)

        tk.Scale(
            speed_row,
            from_=0.0, to=1.0, resolution=0.05,
            orient="horizontal", length=200,
            variable=self._speed_var,
            bg=t["bg"], fg=t["fg"],
            highlightthickness=0,
            troughcolor=t["panel_bg"],
            font=(_UI_FONT, 9),
        ).pack(side="left", padx=4)

        self._speed_display = tk.Label(
            speed_row,
            text=f"{self._eco.tick_delay:.2f}s",
            font=(_MONO_FONT, 10),
            bg=t["bg"], fg=t["fg"], width=6,
        )
        self._speed_display.pack(side="left")

    # ── Event handlers ────────────────────────────────────────────────────────────

    def _on_pause_clicked(self) -> None:
        self._on_pause_toggle()

    def _on_speed_change_internal(self, *_: Any) -> None:
        val = self._speed_var.get()
        try:
            self._speed_display.config(text=f"{val:.2f}s")
        except tk.TclError:
            pass
        self._on_speed_change(val)

    # ── Performance display ────────────────────────────────────────────────────────

    def _update_perf(self, data: Dict[str, Any]) -> None:
        tick_ms   = data.get("tick_time_ms", 0.0)
        fps       = 1000.0 / tick_ms if tick_ms > 0 else 0.0
        organisms = data.get("organism_count", 0)
        try:
            self._perf_fps.config(text=f"FPS: {fps:.1f}")
            self._perf_tick_ms.config(text=f"Tick: {tick_ms:.1f} ms")
            self._perf_organisms.config(text=f"Organisms: {organisms}")
        except tk.TclError:
            pass
