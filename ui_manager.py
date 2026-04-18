from __future__ import annotations

import datetime
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from data_exporter import export_to_csv, export_to_json
from ui_theme import Theme
from ui_widgets import EnhancedChart, StatisticsPanel, TooltipManager

if TYPE_CHECKING:
    from ecosystem import Ecosystem

# Preferred UI font — falls back gracefully on platforms that lack it
_UI_FONT = "Arial"
_MONO_FONT = "Courier New"

# Fixed width of the right-hand stats sidebar (pixels)
_SIDEBAR_W = 270


class UIManager:
    """Creates and manages the full professional UI for the Ecosystem simulator.

    Layout:
        ┌─────────────────────────────────────────┐
        │  HEADER  (title + tick/season/state)    │
        ├────────────────────────┬────────────────┤
        │  GRID CANVAS           │  STATS SIDEBAR │
        │  (left, scrollable)    │  (right, fixed)│
        ├────────────────────────┴────────────────┤
        │  CHART  (population history)            │
        ├─────────────────────────────────────────┤
        │  CONTROLS  (buttons + speed slider)     │
        └─────────────────────────────────────────┘

    The Ecosystem object is the single source of truth for simulation state
    (is_auto, window_closed, stop_requested).  UIManager button callbacks
    mutate those attributes directly.
    """

    def __init__(self, ecosystem: "Ecosystem", is_dark: bool = False) -> None:
        self._eco = ecosystem
        self.theme = Theme(is_dark=is_dark)
        self._build()

    # ── Public API used by Ecosystem ─────────────────────────────────────────

    @property
    def window(self) -> tk.Tk:
        return self._root

    @property
    def advance_var(self) -> tk.IntVar:
        return self._advance_var

    @property
    def tick_delay(self) -> float:
        return self._speed_var.get()

    def update(self, data: Dict[str, Any]) -> None:
        """Redraw all UI elements with the latest simulation data."""
        if self._eco.window_closed:
            return
        state_text = "▶ Running" if self._eco.is_auto else "⏸ Paused"
        season = data.get("season", "")
        season_emoji = data.get("season_emoji", "")
        season_str = f"  {season_emoji} {season}" if season else ""
        self._header_status.config(
            text=f"Tick {data.get('tick', 0)}{season_str}  —  {state_text}"
        )
        self._update_grid(data)
        self._stats_panel.update_stats(data)
        self._chart.draw(
            data.get("plant_history", []),
            data.get("herbivore_history", []),
            data.get("carnivore_history", []),
        )
        self._update_perf(data)
        try:
            self._root.update_idletasks()
            self._root.update()
        except tk.TclError:
            self._eco.window_closed = True

    def set_status(self, text: str) -> None:
        """Update the header status label text."""
        try:
            self._header_status.config(text=text)
        except tk.TclError:
            pass

    def set_simulation_complete(self) -> None:
        try:
            self._header_status.config(text="✅ Simulation complete.")
        except tk.TclError:
            pass

    # ── Window construction ───────────────────────────────────────────────────

    def _build(self) -> None:
        t = self.theme
        eco = self._eco

        self._root = tk.Tk()
        self._root.title("🌍 Ecosystem Simulator")
        self._root.config(bg=t["bg"])
        self._root.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._advance_var = tk.IntVar(master=self._root, value=0)
        self._speed_var = tk.DoubleVar(master=self._root, value=eco.tick_delay)
        self._speed_var.trace_add("write", self._on_speed_change)

        self._tooltip = TooltipManager(self._root)

        # 1. Header
        self._build_header()

        # 2. Main area — grid (left) + sidebar (right)
        main_frame = tk.Frame(self._root, bg=t["bg"])
        main_frame.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        self._main_frame = main_frame

        self._build_grid_area(main_frame)
        self._build_sidebar(main_frame)

        # 3. Chart
        self._build_chart_area()

        # 4. Controls
        self._build_controls()

    # ── 1. Header ─────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        t = self.theme
        hdr = tk.Frame(self._root, bg=t.get("header_bg", t["bg"]))
        hdr.pack(fill="x")
        self._header_frame = hdr

        title = tk.Label(
            hdr,
            text="🌍  ECOSYSTEM SIMULATOR",
            font=(_UI_FONT, 16, "bold"),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_accent", t["fg"]),
            padx=12, pady=8,
        )
        title.pack(side="left")
        self._header_title = title

        self._header_status = tk.Label(
            hdr,
            text="Initializing…",
            font=(_UI_FONT, 12),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_secondary", t["fg"]),
            padx=12,
        )
        self._header_status.pack(side="right")

        # Thin separator line
        sep = tk.Frame(self._root, bg=t.get("border_glow", t["border"]), height=2)
        sep.pack(fill="x")
        self._header_sep = sep

    # ── 2a. Grid area (left panel) ────────────────────────────────────────────

    def _build_grid_area(self, parent: tk.Widget) -> None:
        t = self.theme
        eco = self._eco

        cs = eco.cell_size
        canvas_w = eco.grid_size * cs
        canvas_h = eco.grid_size * cs

        # Cap the visible size at 620 px so large grids don't overflow the screen
        vis_w = min(canvas_w, 620)
        vis_h = min(canvas_h, 620)

        left_frame = tk.Frame(parent, bg=t["bg"])
        left_frame.pack(side="left", fill="both")
        self._grid_outer_frame = left_frame

        # Thin glow-border wrapper
        border_frame = tk.Frame(left_frame,
                                bg=t.get("border_glow", t["border"]),
                                padx=1, pady=1)
        border_frame.pack(padx=6, pady=6)

        scroll_frame = tk.Frame(border_frame, bg=t["grid_bg"])
        scroll_frame.pack()

        h_bar = tk.Scrollbar(scroll_frame, orient="horizontal")
        v_bar = tk.Scrollbar(scroll_frame, orient="vertical")

        self._grid_canvas = tk.Canvas(
            scroll_frame,
            width=vis_w,
            height=vis_h,
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
        self._grid_canvas.bind("<Motion>", self._on_grid_motion)
        self._grid_canvas.bind("<Leave>",  self._on_grid_leave)
        self._grid_border_frame = border_frame

    def _update_grid(self, data: Dict[str, Any]) -> None:
        eco = self._eco
        t = self.theme
        canvas = self._grid_canvas
        canvas.config(bg=t["grid_bg"])
        canvas.delete("all")
        cs = eco.cell_size

        from organisms import Carnivore, Herbivore, Plant

        for y in range(eco.grid_size):
            for x in range(eco.grid_size):
                x1, y1 = x * cs, y * cs
                x2, y2 = x1 + cs, y1 + cs
                occupant = eco.grid.get((x, y))
                if occupant and occupant.alive:
                    if isinstance(occupant, Plant):
                        fill   = t["plant_fill"]
                        symbol = "🌿"
                    elif isinstance(occupant, Herbivore):
                        fill   = t["herbivore_fill"]
                        symbol = "🦌"
                    elif isinstance(occupant, Carnivore):
                        fill   = t["carnivore_fill"]
                        symbol = "🦁"
                    else:
                        fill   = t.get("accent_bg", "#444")
                        symbol = "?"
                else:
                    fill   = t["empty_fill"]
                    symbol = ""

                canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill, outline=t["grid_line"],
                )
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
        from organisms import Animal, Plant
        t = self.theme
        if occupant and occupant.alive:
            kind = type(occupant).__name__
            if isinstance(occupant, Plant):
                icon  = "🌿"
                color = t["text_plant"]
                lines = [
                    f"{icon}  {kind}  ({gx}, {gy})",
                    f"Age: {occupant.age}",
                    "Energy: N/A",
                ]
                colors = [color, t.get("fg_secondary", t["fg"]), t.get("fg_secondary", t["fg"])]
            elif isinstance(occupant, Animal):  # type: ignore[attr-defined]
                icon = "🦌" if kind == "Herbivore" else "🦁"
                color = t["text_herbivore"] if kind == "Herbivore" else t["text_carnivore"]
                energy = occupant.energy  # type: ignore[attr-defined]
                lines = [
                    f"{icon}  {kind}  ({gx}, {gy})",
                    f"Age: {occupant.age}",
                    f"Energy: {energy}",
                ]
                colors = [color, t.get("fg_secondary", t["fg"]), t.get("fg_accent", t["fg"])]
            else:
                lines  = [f"({gx}, {gy})"]
                colors = [t["fg"]]
        else:
            lines  = [f"Empty  ({gx}, {gy})"]
            colors = [t["label_fg"]]
        self._tooltip.show(lines, colors, event.x_root, event.y_root)

    def _on_grid_leave(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._tooltip.hide()

    # ── 2b. Stats sidebar (right panel) ──────────────────────────────────────

    def _build_sidebar(self, parent: tk.Widget) -> None:
        t = self.theme

        sidebar = tk.Frame(parent, bg=t["panel_bg"], width=_SIDEBAR_W)
        sidebar.pack(side="right", fill="y", padx=(0, 6), pady=6)
        sidebar.pack_propagate(False)
        self._sidebar_frame = sidebar

        self._apply_sidebar_notebook_style()
        nb = ttk.Notebook(sidebar)
        nb.pack(fill="both", expand=True)
        self._sidebar_nb = nb

        # Stats tab
        stats_frame = tk.Frame(nb, bg=t["panel_bg"])
        nb.add(stats_frame, text="  📊 Stats  ")
        self._stats_panel = StatisticsPanel(stats_frame, self.theme)
        self._stats_panel.pack(fill="both", expand=True)

        # Config / Parameters tab
        cfg_frame = tk.Frame(nb, bg=t["panel_bg"])
        nb.add(cfg_frame, text="  ⚙️ Config  ")
        self._build_params_in(cfg_frame)

    def _apply_sidebar_notebook_style(self) -> None:
        t = self.theme
        style = ttk.Style(self._root)
        style.theme_use("default")
        style.configure("TNotebook", background=t["panel_bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=t["panel_bg"],
            foreground=t["fg"],
            padding=[8, 4],
            font=(_UI_FONT, 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", t.get("accent_bg", t["button_bg"]))],
            foreground=[("selected", t.get("fg_accent", t["fg"]))],
        )

    def _build_params_in(self, parent: tk.Widget) -> None:
        t = self.theme
        import config as _cfg
        eco = self._eco

        canvas = tk.Canvas(parent, bg=t["panel_bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=t["panel_bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(_evt: Any) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)

        self._params_labels: List[tk.Label] = []

        def _section(text: str) -> None:
            lbl = tk.Label(
                inner, text=text,
                font=(_UI_FONT, 10, "bold"),
                bg=t["panel_bg"], fg=t.get("fg_accent", t["fg"]),
                anchor="w",
            )
            lbl.pack(fill="x", padx=10, pady=(10, 1))
            self._params_labels.append(lbl)
            sep = tk.Frame(inner, bg=t.get("border_glow", t["border"]), height=1)
            sep.pack(fill="x", padx=10, pady=(0, 4))

        def _row(key: str, val: str) -> None:
            row = tk.Frame(inner, bg=t["panel_bg"])
            row.pack(fill="x", padx=10, pady=1)
            k = tk.Label(row, text=f"{key}:", font=(_UI_FONT, 9),
                         bg=t["panel_bg"], fg=t["label_fg"], anchor="w")
            k.pack(side="left")
            v = tk.Label(row, text=val, font=(_UI_FONT, 9, "bold"),
                         bg=t["panel_bg"], fg=t["fg"], anchor="e")
            v.pack(side="right")
            self._params_labels += [k, v]

        _section("Simulation")
        _row("Grid Size", f"{eco.grid_size} × {eco.grid_size}")
        _row("Initial Plants", str(eco._init_plants))
        _row("Initial Herbivores", str(eco._init_herbivores))
        _row("Initial Carnivores", str(eco._init_carnivores))
        _row("Active Preset", _cfg.active_preset_name())

        _section("Plants")
        _row("Repro Chance", f"{_cfg.get('PLANT_REPRODUCTION_CHANCE'):.0%}")
        _row("Max Age", str(_cfg.get("PLANT_MAX_AGE")))

        _section("Herbivores")
        _row("Energy Gain", str(_cfg.get("HERBIVORE_ENERGY_GAIN")))
        _row("Repro Threshold", str(_cfg.get("HERBIVORE_REPRODUCTION_THRESHOLD")))
        _row("Repro Chance", f"{_cfg.get('HERBIVORE_REPRODUCTION_CHANCE'):.0%}")
        _row("Max Age", str(_cfg.get("HERBIVORE_MAX_AGE")))

        _section("Carnivores")
        _row("Energy Gain", str(_cfg.get("CARNIVORE_ENERGY_GAIN")))
        _row("Repro Threshold", str(_cfg.get("CARNIVORE_REPRODUCTION_THRESHOLD")))
        _row("Repro Chance", f"{_cfg.get('CARNIVORE_REPRODUCTION_CHANCE'):.0%}")
        _row("Max Age", str(_cfg.get("CARNIVORE_MAX_AGE")))

        # Speed presets
        _section("Speed Presets")
        preset_frame = tk.Frame(inner, bg=t["panel_bg"])
        preset_frame.pack(fill="x", padx=10, pady=4)
        self._preset_buttons: List[tk.Button] = []
        for label, delay in [
            ("🐢 1.0s", 1.0),
            ("🚶 0.3s", 0.3),
            ("🏃 0.1s", 0.1),
            ("⚡ Max",  0.0),
        ]:
            btn = tk.Button(
                preset_frame, text=label,
                font=(_UI_FONT, 9),
                bg=t["button_bg"], fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=4,
                command=lambda d=delay: self._speed_var.set(d),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._preset_buttons.append(btn)

        # Performance
        _section("Performance")
        self._perf_fps = tk.Label(inner, text="FPS: --", font=(_UI_FONT, 9),
                                   bg=t["panel_bg"], fg=t.get("perf_fg", t["fg"]),
                                   anchor="w")
        self._perf_fps.pack(fill="x", padx=10, pady=1)

        self._perf_tick_ms = tk.Label(inner, text="Tick: -- ms", font=(_UI_FONT, 9),
                                       bg=t["panel_bg"], fg=t.get("perf_fg", t["fg"]),
                                       anchor="w")
        self._perf_tick_ms.pack(fill="x", padx=10, pady=1)

        self._perf_organisms = tk.Label(inner, text="Organisms: --", font=(_UI_FONT, 9),
                                         bg=t["panel_bg"], fg=t.get("perf_fg", t["fg"]),
                                         anchor="w")
        self._perf_organisms.pack(fill="x", padx=10, pady=1)

        self._perf_last_update = tk.Label(inner, text="Updated: --", font=(_UI_FONT, 9),
                                           bg=t["panel_bg"], fg=t.get("perf_fg", t["fg"]),
                                           anchor="w")
        self._perf_last_update.pack(fill="x", padx=10, pady=(1, 8))

    # ── 3. Chart area ─────────────────────────────────────────────────────────

    def _build_chart_area(self) -> None:
        t = self.theme
        eco = self._eco

        outer = tk.Frame(self._root, bg=t["bg"])
        outer.pack(fill="x", padx=6, pady=(0, 2))
        self._chart_outer = outer

        # Header row for the chart
        hdr = tk.Frame(outer, bg=t["bg"])
        hdr.pack(fill="x", pady=(2, 0))
        self._chart_header_frame = hdr

        chart_title = tk.Label(
            hdr, text="📈  Population History",
            font=(_UI_FONT, 11, "bold"),
            bg=t["bg"], fg=t.get("fg_accent", t["fg"]),
        )
        chart_title.pack(side="left", padx=8)
        self._chart_title_lbl = chart_title

        # Export buttons in the chart header
        self._chart_btns: List[tk.Button] = []
        for text, cmd in [
            ("📥 CSV",  self._on_export_csv),
            ("📋 JSON", self._on_export_json),
        ]:
            btn = tk.Button(
                hdr, text=text, font=(_UI_FONT, 9),
                bg=t["button_bg"], fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=6,
                command=cmd,
            )
            btn.pack(side="right", padx=4, pady=2)
            self._chart_btns.append(btn)

        chart_w = eco.grid_size * eco.cell_size + _SIDEBAR_W + 8
        chart_w = max(chart_w, 600)

        self._chart = EnhancedChart(
            outer, self.theme,
            width=chart_w, height=190,
            bg=t["chart_bg"],
        )
        self._chart.pack(padx=8, pady=(2, 4))

    # ── 4. Control bar ────────────────────────────────────────────────────────

    def _build_controls(self) -> None:
        t = self.theme
        sep = tk.Frame(self._root, bg=t.get("border_glow", t["border"]), height=2)
        sep.pack(fill="x")
        self._ctrl_sep = sep

        ctrl = tk.Frame(self._root, bg=t["bg"])
        ctrl.pack(fill="x", padx=8, pady=(4, 8))
        self._ctrl_frame = ctrl

        btn_row = tk.Frame(ctrl, bg=t["bg"])
        btn_row.pack(fill="x")
        self._btn_row = btn_row

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

        self._next_btn  = _btn("⏭  Next Tick",  self._on_next_tick,    width=13)
        auto_label      = "⏸  Pause" if self._eco.is_auto else "▶  Auto Run"
        self._auto_btn  = _btn(auto_label,         self._on_toggle_auto, width=13)
        self._quit_btn  = _btn("⏹  Quit",          self._on_quit,        width=10)
        theme_label     = "☀️  Light" if self.theme.is_dark else "🌙  Dark"
        self._theme_btn = _btn(theme_label,         self._on_toggle_theme, width=11)
        self._ctrl_buttons = [
            self._next_btn, self._auto_btn,
            self._quit_btn, self._theme_btn,
        ]

        # Speed slider row
        speed_row = tk.Frame(ctrl, bg=t["bg"])
        speed_row.pack(fill="x", pady=(2, 0))
        self._speed_row = speed_row

        tk.Label(
            speed_row, text="Speed (delay):",
            font=(_UI_FONT, 10), bg=t["bg"], fg=t["fg"],
        ).pack(side="left", padx=4)

        self._speed_slider = tk.Scale(
            speed_row,
            from_=0.0, to=1.0, resolution=0.05,
            orient="horizontal", length=240,
            variable=self._speed_var,
            bg=t["bg"], fg=t["fg"],
            highlightthickness=0,
            troughcolor=t["panel_bg"],
            font=(_UI_FONT, 9),
        )
        self._speed_slider.pack(side="left", padx=4)

        self._speed_display = tk.Label(
            speed_row,
            text=f"{self._speed_var.get():.2f}s",
            font=(_MONO_FONT, 10),
            bg=t["bg"], fg=t["fg"], width=6,
        )
        self._speed_display.pack(side="left")

    # ── Performance display ───────────────────────────────────────────────────

    def _update_perf(self, data: Dict[str, Any]) -> None:
        tick_ms  = data.get("tick_time_ms", 0.0)
        fps      = 1000.0 / tick_ms if tick_ms > 0 else 0.0
        organisms = data.get("organism_count", 0)
        ts       = datetime.datetime.now().strftime("%H:%M:%S")
        self._perf_fps.config(text=f"FPS: {fps:.1f}")
        self._perf_tick_ms.config(text=f"Tick: {tick_ms:.1f} ms")
        self._perf_organisms.config(text=f"Organisms: {organisms}")
        self._perf_last_update.config(text=f"Updated: {ts}")

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_next_tick(self) -> None:
        if self._eco.window_closed:
            return
        self._advance_var.set(1)

    def _on_toggle_auto(self) -> None:
        if self._eco.window_closed:
            return
        self._eco.is_auto = not self._eco.is_auto
        self._sync_auto_button()
        if self._eco.is_auto:
            self._advance_var.set(1)

    def _sync_auto_button(self) -> None:
        try:
            text = "⏸  Pause" if self._eco.is_auto else "▶  Auto Run"
            self._auto_btn.config(text=text)
        except tk.TclError:
            pass

    def _on_quit(self) -> None:
        self._eco.stop_requested = True
        self._eco.window_closed  = True
        self._tooltip.destroy()
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    def _on_speed_change(self, *_: Any) -> None:
        val = self._speed_var.get()
        self._eco.tick_delay = val
        try:
            self._speed_display.config(text=f"{val:.2f}s")
        except tk.TclError:
            pass

    # ── Theme toggling ────────────────────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        self.theme.toggle()
        label = "☀️  Light" if self.theme.is_dark else "🌙  Dark"
        try:
            self._theme_btn.config(text=label)
        except tk.TclError:
            pass
        self._apply_theme_to_all()

    def _apply_theme_to_all(self) -> None:
        t = self.theme
        self._apply_sidebar_notebook_style()

        # Header
        hdr_bg = t.get("header_bg", t["bg"])
        self._header_frame.config(bg=hdr_bg)
        self._header_title.config(bg=hdr_bg, fg=t.get("fg_accent", t["fg"]))
        self._header_status.config(bg=hdr_bg, fg=t.get("fg_secondary", t["fg"]))
        self._header_sep.config(bg=t.get("border_glow", t["border"]))

        # Root
        self._root.config(bg=t["bg"])

        # Main frame + grid
        self._main_frame.config(bg=t["bg"])
        self._grid_outer_frame.config(bg=t["bg"])
        self._grid_border_frame.config(bg=t.get("border_glow", t["border"]))
        self._grid_canvas.config(bg=t["grid_bg"])

        # Sidebar
        self._sidebar_frame.config(bg=t["panel_bg"])
        self._stats_panel.apply_theme(t)

        # Config tab widgets
        for lbl in self._params_labels:
            try:
                lbl.config(bg=t["panel_bg"])  # type: ignore[call-arg]
            except tk.TclError:
                pass
        for btn in self._preset_buttons:
            btn.config(bg=t["button_bg"], fg=t["button_fg"],
                       activebackground=t["button_active_bg"])
        for perf_lbl in (
            self._perf_fps, self._perf_tick_ms,
            self._perf_organisms, self._perf_last_update,
        ):
            perf_lbl.config(bg=t["panel_bg"], fg=t.get("perf_fg", t["fg"]))

        # Chart area
        self._chart_outer.config(bg=t["bg"])
        self._chart_header_frame.config(bg=t["bg"])
        self._chart_title_lbl.config(bg=t["bg"], fg=t.get("fg_accent", t["fg"]))
        self._chart.apply_theme(t)
        for btn in self._chart_btns:
            btn.config(bg=t["button_bg"], fg=t["button_fg"],
                       activebackground=t["button_active_bg"])

        # Controls
        self._ctrl_sep.config(bg=t.get("border_glow", t["border"]))
        self._ctrl_frame.config(bg=t["bg"])
        self._btn_row.config(bg=t["bg"])
        for btn in self._ctrl_buttons:
            btn.config(bg=t["button_bg"], fg=t["button_fg"],
                       activebackground=t["button_active_bg"])
        self._speed_row.config(bg=t["bg"])
        for child in self._speed_row.winfo_children():
            try:
                child.config(bg=t["bg"], fg=t["fg"])  # type: ignore[call-arg]
            except tk.TclError:
                pass
        self._speed_slider.config(bg=t["bg"], fg=t["fg"], troughcolor=t["panel_bg"])
        self._speed_display.config(bg=t["bg"], fg=t["fg"])

    # ── Export helpers ────────────────────────────────────────────────────────

    def _history_dict(self) -> Dict[str, List[int]]:
        eco = self._eco
        return {
            "plants":      list(eco.plant_history),
            "herbivores":  list(eco.herbivore_history),
            "carnivores":  list(eco.carnivore_history),
        }

    def _metadata_dict(self) -> Dict[str, Any]:
        eco = self._eco
        return {
            "grid_size":          eco.grid_size,
            "initial_plants":     eco._init_plants,
            "initial_herbivores": eco._init_herbivores,
            "initial_carnivores": eco._init_carnivores,
        }

    def _on_export_csv(self) -> None:
        fname = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export population data as CSV",
        )
        if not fname:
            return
        try:
            export_to_csv(self._history_dict(), fname)
            messagebox.showinfo("Export", f"CSV saved to:\n{os.path.basename(fname)}")
        except OSError as exc:
            messagebox.showerror("Export Error", str(exc))

    def _on_export_json(self) -> None:
        fname = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export simulation data as JSON",
        )
        if not fname:
            return
        try:
            export_to_json(self._history_dict(), self._metadata_dict(), fname)
            messagebox.showinfo("Export", f"JSON saved to:\n{os.path.basename(fname)}")
        except OSError as exc:
            messagebox.showerror("Export Error", str(exc))
