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


class UIManager:
    """Creates and manages the full professional UI for the Ecosystem simulator.

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
        state_text = "Running" if self._eco.is_auto else "Paused"
        self._status_label.config(text=f"Tick {data.get('tick', 0)} — {state_text}")
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
        """Update the status label text."""
        try:
            self._status_label.config(text=text)
        except tk.TclError:
            pass

    def set_simulation_complete(self) -> None:
        try:
            self._status_label.config(text="Simulation complete.")
        except tk.TclError:
            pass

    # ── Window construction ───────────────────────────────────────────────────

    def _build(self) -> None:
        t = self.theme
        self._root = tk.Tk()
        self._root.title("Ecosystem Simulator")
        self._root.config(bg=t["bg"])
        self._root.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._advance_var = tk.IntVar(master=self._root, value=0)
        self._speed_var = tk.DoubleVar(master=self._root, value=self._eco.tick_delay)
        self._speed_var.trace_add("write", self._on_speed_change)

        self._tooltip = TooltipManager(self._root)

        # Status bar (top)
        self._status_label = tk.Label(
            self._root,
            text="Initializing…",
            font=("Consolas", 11),
            bg=t["bg"],
            fg=t["fg"],
        )
        self._status_label.pack(pady=(6, 2))

        # Notebook
        self._apply_notebook_style()
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=4)

        self._build_grid_tab()
        self._build_stats_tab()
        self._build_chart_tab()
        self._build_params_tab()

        # Bottom control bar
        self._build_controls()

    def _apply_notebook_style(self) -> None:
        t = self.theme
        style = ttk.Style(self._root)
        style.theme_use("default")
        style.configure("TNotebook", background=t["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=t["panel_bg"],
            foreground=t["fg"],
            padding=[8, 4],
            font=("Consolas", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", t["button_bg"])],
            foreground=[("selected", t["fg"])],
        )

    # ── Tab 1: Grid ────────────────────────────────────────────────────────

    def _build_grid_tab(self) -> None:
        t = self.theme
        eco = self._eco
        frame = tk.Frame(self._notebook, bg=t["panel_bg"])
        self._notebook.add(frame, text="  🌍 Grid  ")
        self._grid_tab_frame = frame

        cs = eco.cell_size
        canvas_w = eco.grid_size * cs + 2
        canvas_h = eco.grid_size * cs + 2

        self._grid_canvas = tk.Canvas(
            frame,
            width=canvas_w,
            height=canvas_h,
            bg=t["grid_bg"],
            highlightthickness=1,
            highlightbackground=t["grid_line"],
        )
        self._grid_canvas.pack(padx=8, pady=8)
        self._grid_canvas.bind("<Motion>", self._on_grid_motion)
        self._grid_canvas.bind("<Leave>", self._on_grid_leave)

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
                        fill = t["plant_fill"]
                        symbol = "🌿"
                    elif isinstance(occupant, Herbivore):
                        fill = t["herbivore_fill"]
                        symbol = "🐇"
                    elif isinstance(occupant, Carnivore):
                        fill = t["carnivore_fill"]
                        symbol = "🐺"
                    else:
                        fill = "#bdbdbd"
                        symbol = "?"
                else:
                    fill = t["empty_fill"]
                    symbol = ""

                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=t["grid_line"])
                if symbol:
                    canvas.create_text(
                        x1 + cs / 2,
                        y1 + cs / 2,
                        text=symbol,
                        font=("Segoe UI Emoji", int(cs * 0.6)),
                    )

    def _on_grid_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        eco = self._eco
        cs = eco.cell_size
        gx = event.x // cs
        gy = event.y // cs
        if not (0 <= gx < eco.grid_size and 0 <= gy < eco.grid_size):
            self._tooltip.hide()
            return
        occupant = eco.grid.get((gx, gy))
        from organisms import Animal, Plant
        if occupant and occupant.alive:
            kind = type(occupant).__name__
            age_str = str(occupant.age)
            energy_str = str(occupant.energy) if isinstance(occupant, Animal) else "N/A"  # type: ignore[attr-defined]
            text = f"{kind}  |  Age: {age_str}  |  Energy: {energy_str}"
        else:
            text = f"Empty ({gx}, {gy})"
        self._tooltip.show(text, event.x_root, event.y_root)

    def _on_grid_leave(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._tooltip.hide()

    # ── Tab 2: Statistics ──────────────────────────────────────────────────

    def _build_stats_tab(self) -> None:
        t = self.theme
        frame = tk.Frame(self._notebook, bg=t["panel_bg"])
        self._notebook.add(frame, text="  📊 Statistics  ")
        self._stats_tab_frame = frame

        self._stats_panel = StatisticsPanel(frame, self.theme)
        self._stats_panel.pack(fill="both", expand=True, padx=8, pady=8)

    # ── Tab 3: Chart ────────────────────────────────────────────────────────

    def _build_chart_tab(self) -> None:
        t = self.theme
        frame = tk.Frame(self._notebook, bg=t["panel_bg"])
        self._notebook.add(frame, text="  📈 Chart  ")
        self._chart_tab_frame = frame
        self._chart_tab_widgets: List[tk.Widget] = []

        eco = self._eco
        chart_w = max(eco.grid_size * eco.cell_size + 10, 480)

        lbl = tk.Label(
            frame,
            text="Population History",
            font=("Consolas", 11, "bold"),
            bg=t["panel_bg"],
            fg=t["fg"],
        )
        lbl.pack(pady=(8, 2))
        self._chart_tab_widgets.append(lbl)

        self._chart = EnhancedChart(
            frame, self.theme, width=chart_w, height=220, bg=t["chart_bg"]
        )
        self._chart.pack(padx=8, pady=4)
        self._chart_tab_widgets.append(self._chart)

        btn_frame = tk.Frame(frame, bg=t["panel_bg"])
        btn_frame.pack(pady=4)
        self._chart_tab_widgets.append(btn_frame)

        self._csv_btn = tk.Button(
            btn_frame,
            text="📥 Export CSV",
            font=("Consolas", 10),
            bg=t["button_bg"],
            fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            relief="flat",
            padx=8,
            command=self._on_export_csv,
        )
        self._csv_btn.pack(side="left", padx=6)
        self._chart_tab_widgets.append(self._csv_btn)

        self._json_btn = tk.Button(
            btn_frame,
            text="📋 Export JSON",
            font=("Consolas", 10),
            bg=t["button_bg"],
            fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            relief="flat",
            padx=8,
            command=self._on_export_json,
        )
        self._json_btn.pack(side="left", padx=6)
        self._chart_tab_widgets.append(self._json_btn)

    # ── Tab 4: Parameters ──────────────────────────────────────────────────

    def _build_params_tab(self) -> None:
        t = self.theme
        frame = tk.Frame(self._notebook, bg=t["panel_bg"])
        self._notebook.add(frame, text="  ⚙️ Parameters  ")
        self._params_frame = frame
        self._params_labels: List[tk.Label] = []

        from organisms import (
            CARNIVORE_ENERGY_GAIN, CARNIVORE_MAX_AGE,
            CARNIVORE_REPRODUCTION_CHANCE, CARNIVORE_REPRODUCTION_COST,
            CARNIVORE_REPRODUCTION_THRESHOLD,
            HERBIVORE_ENERGY_GAIN, HERBIVORE_MAX_AGE,
            HERBIVORE_REPRODUCTION_CHANCE, HERBIVORE_REPRODUCTION_COST,
            HERBIVORE_REPRODUCTION_THRESHOLD,
            PLANT_MAX_AGE, PLANT_REPRODUCTION_CHANCE,
        )

        eco = self._eco
        sections = [
            ("Simulation Config", [
                ("Grid Size", f"{eco.grid_size} × {eco.grid_size}"),
                ("Initial Plants", str(eco._init_plants)),
                ("Initial Herbivores", str(eco._init_herbivores)),
                ("Initial Carnivores", str(eco._init_carnivores)),
            ]),
            ("Plant Constants", [
                ("Reproduction Chance", f"{PLANT_REPRODUCTION_CHANCE:.0%}"),
                ("Max Age", str(PLANT_MAX_AGE)),
            ]),
            ("Herbivore Constants", [
                ("Energy Gain", str(HERBIVORE_ENERGY_GAIN)),
                ("Repro Threshold", str(HERBIVORE_REPRODUCTION_THRESHOLD)),
                ("Repro Chance", f"{HERBIVORE_REPRODUCTION_CHANCE:.0%}"),
                ("Repro Cost", str(HERBIVORE_REPRODUCTION_COST)),
                ("Max Age", str(HERBIVORE_MAX_AGE)),
            ]),
            ("Carnivore Constants", [
                ("Energy Gain", str(CARNIVORE_ENERGY_GAIN)),
                ("Repro Threshold", str(CARNIVORE_REPRODUCTION_THRESHOLD)),
                ("Repro Chance", f"{CARNIVORE_REPRODUCTION_CHANCE:.0%}"),
                ("Repro Cost", str(CARNIVORE_REPRODUCTION_COST)),
                ("Max Age", str(CARNIVORE_MAX_AGE)),
            ]),
        ]

        row = 0
        for section_title, items in sections:
            sec_lbl = tk.Label(
                frame, text=section_title,
                font=("Consolas", 10, "bold"),
                bg=t["panel_bg"], fg=t["fg"], anchor="w",
            )
            sec_lbl.grid(row=row, column=0, columnspan=2, padx=16, pady=(10, 2), sticky="w")
            self._params_labels.append(sec_lbl)
            row += 1
            for key, val in items:
                k_lbl = tk.Label(
                    frame, text=f"  {key}:", font=("Consolas", 10),
                    bg=t["panel_bg"], fg=t["label_fg"], anchor="w",
                )
                k_lbl.grid(row=row, column=0, padx=16, sticky="w")
                v_lbl = tk.Label(
                    frame, text=val, font=("Consolas", 10, "bold"),
                    bg=t["panel_bg"], fg=t["fg"], anchor="w",
                )
                v_lbl.grid(row=row, column=1, padx=8, sticky="w")
                self._params_labels += [k_lbl, v_lbl]
                row += 1

        # Speed presets
        preset_lbl = tk.Label(
            frame, text="Speed Presets", font=("Consolas", 10, "bold"),
            bg=t["panel_bg"], fg=t["fg"], anchor="w",
        )
        preset_lbl.grid(row=row, column=0, columnspan=2, padx=16, pady=(10, 2), sticky="w")
        self._params_labels.append(preset_lbl)
        row += 1

        preset_frame = tk.Frame(frame, bg=t["panel_bg"])
        preset_frame.grid(row=row, column=0, columnspan=2, padx=16, pady=4, sticky="w")
        row += 1
        self._preset_buttons: List[tk.Button] = []
        for label, delay in [
            ("🐢 Slow (1.0s)", 1.0),
            ("🚶 Medium (0.3s)", 0.3),
            ("🏃 Fast (0.1s)", 0.1),
            ("⚡ Max (0s)", 0.0),
        ]:
            btn = tk.Button(
                preset_frame,
                text=label,
                font=("Consolas", 9),
                bg=t["button_bg"],
                fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat",
                padx=4,
                command=lambda d=delay: self._speed_var.set(d),
            )
            btn.pack(side="left", padx=4)
            self._preset_buttons.append(btn)

        # Performance monitor
        perf_lbl = tk.Label(
            frame, text="Performance Monitor", font=("Consolas", 10, "bold"),
            bg=t["panel_bg"], fg=t["fg"], anchor="w",
        )
        perf_lbl.grid(row=row, column=0, columnspan=2, padx=16, pady=(10, 2), sticky="w")
        self._params_labels.append(perf_lbl)
        row += 1

        self._perf_fps = tk.Label(
            frame, text="FPS: --", font=("Consolas", 10),
            bg=t["panel_bg"], fg=t["perf_fg"], anchor="w",
        )
        self._perf_fps.grid(row=row, column=0, padx=16, pady=2, sticky="w")
        row += 1

        self._perf_tick_ms = tk.Label(
            frame, text="Tick Time: -- ms", font=("Consolas", 10),
            bg=t["panel_bg"], fg=t["perf_fg"], anchor="w",
        )
        self._perf_tick_ms.grid(row=row, column=0, padx=16, pady=2, sticky="w")
        row += 1

        self._perf_organisms = tk.Label(
            frame, text="Organisms: --", font=("Consolas", 10),
            bg=t["panel_bg"], fg=t["perf_fg"], anchor="w",
        )
        self._perf_organisms.grid(row=row, column=0, padx=16, pady=2, sticky="w")
        row += 1

        self._perf_last_update = tk.Label(
            frame, text="Last Update: --", font=("Consolas", 10),
            bg=t["panel_bg"], fg=t["perf_fg"], anchor="w",
        )
        self._perf_last_update.grid(row=row, column=0, columnspan=2, padx=16, pady=2, sticky="w")

    def _update_perf(self, data: Dict[str, Any]) -> None:
        tick_ms = data.get("tick_time_ms", 0.0)
        fps = 1000.0 / tick_ms if tick_ms > 0 else 0.0
        organisms = data.get("organism_count", 0)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._perf_fps.config(text=f"FPS: {fps:.1f}")
        self._perf_tick_ms.config(text=f"Tick Time: {tick_ms:.1f} ms")
        self._perf_organisms.config(text=f"Organisms: {organisms}")
        self._perf_last_update.config(text=f"Last Update: {ts}")

    # ── Bottom control bar ─────────────────────────────────────────────────

    def _build_controls(self) -> None:
        t = self.theme
        ctrl = tk.Frame(self._root, bg=t["bg"])
        ctrl.pack(fill="x", padx=8, pady=(2, 6))
        self._ctrl_frame = ctrl

        btn_row = tk.Frame(ctrl, bg=t["bg"])
        btn_row.pack(fill="x")
        self._btn_row = btn_row

        def _btn(text: str, cmd: Any, width: int = 12) -> tk.Button:
            b = tk.Button(
                btn_row,
                text=text,
                width=width,
                font=("Consolas", 10),
                bg=t["button_bg"],
                fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat",
                padx=4,
                command=cmd,
            )
            b.pack(side="left", padx=4, pady=2)
            return b

        self._next_btn = _btn("Next Tick", self._on_next_tick)
        auto_label = "⏸ Pause" if self._eco.is_auto else "▶ Auto Run"
        self._auto_btn = _btn(auto_label, self._on_toggle_auto)
        self._quit_btn = _btn("⏹ Quit", self._on_quit)
        theme_label = "☀️ Light" if self.theme.is_dark else "🌙 Dark"
        self._theme_btn = _btn(theme_label, self._on_toggle_theme, width=10)
        self._ctrl_buttons = [self._next_btn, self._auto_btn, self._quit_btn, self._theme_btn]

        # Speed slider row
        speed_row = tk.Frame(ctrl, bg=t["bg"])
        speed_row.pack(fill="x", pady=(2, 0))
        self._speed_row = speed_row

        tk.Label(
            speed_row, text="Speed (delay):", font=("Consolas", 10),
            bg=t["bg"], fg=t["fg"],
        ).pack(side="left", padx=4)

        self._speed_slider = tk.Scale(
            speed_row,
            from_=0.0, to=1.0, resolution=0.05,
            orient="horizontal", length=220,
            variable=self._speed_var,
            bg=t["bg"], fg=t["fg"],
            highlightthickness=0,
            troughcolor=t["panel_bg"],
            font=("Consolas", 9),
        )
        self._speed_slider.pack(side="left", padx=4)

        self._speed_display = tk.Label(
            speed_row,
            text=f"{self._speed_var.get():.2f}s",
            font=("Consolas", 10),
            bg=t["bg"], fg=t["fg"], width=6,
        )
        self._speed_display.pack(side="left")

    # ── Event handlers ────────────────────────────────────────────────────

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
            text = "⏸ Pause" if self._eco.is_auto else "▶ Auto Run"
            self._auto_btn.config(text=text)
        except tk.TclError:
            pass

    def _on_quit(self) -> None:
        self._eco.stop_requested = True
        self._eco.window_closed = True
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

    # ── Theme ─────────────────────────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        self.theme.toggle()
        label = "☀️ Light" if self.theme.is_dark else "🌙 Dark"
        try:
            self._theme_btn.config(text=label)
        except tk.TclError:
            pass
        self._apply_theme_to_all()

    def _apply_theme_to_all(self) -> None:
        t = self.theme
        self._apply_notebook_style()

        # Root and status
        self._root.config(bg=t["bg"])
        self._status_label.config(bg=t["bg"], fg=t["fg"])

        # Control bar
        self._ctrl_frame.config(bg=t["bg"])
        self._btn_row.config(bg=t["bg"])
        self._speed_row.config(bg=t["bg"])
        for child in self._speed_row.winfo_children():
            try:
                child.config(bg=t["bg"], fg=t["fg"])  # type: ignore[call-arg]
            except tk.TclError:
                pass
        for btn in self._ctrl_buttons:
            btn.config(bg=t["button_bg"], fg=t["button_fg"], activebackground=t["button_active_bg"])
        self._speed_slider.config(bg=t["bg"], fg=t["fg"], troughcolor=t["panel_bg"])
        self._speed_display.config(bg=t["bg"], fg=t["fg"])

        # Grid tab
        self._grid_tab_frame.config(bg=t["panel_bg"])
        self._grid_canvas.config(bg=t["grid_bg"], highlightbackground=t["grid_line"])

        # Stats tab
        self._stats_tab_frame.config(bg=t["panel_bg"])
        self._stats_panel.apply_theme(t)

        # Chart tab
        self._chart_tab_frame.config(bg=t["panel_bg"])
        self._chart.apply_theme(t)
        for w in self._chart_tab_widgets:
            try:
                if isinstance(w, tk.Label):
                    w.config(bg=t["panel_bg"], fg=t["fg"])
                elif isinstance(w, tk.Frame):
                    w.config(bg=t["panel_bg"])
                elif isinstance(w, tk.Button):
                    w.config(bg=t["button_bg"], fg=t["button_fg"],
                             activebackground=t["button_active_bg"])
            except tk.TclError:
                pass

        # Params tab
        self._params_frame.config(bg=t["panel_bg"])
        for lbl in self._params_labels:
            try:
                lbl.config(bg=t["panel_bg"], fg=t["fg"])
            except tk.TclError:
                pass
        for btn in self._preset_buttons:
            btn.config(bg=t["button_bg"], fg=t["button_fg"],
                       activebackground=t["button_active_bg"])
        for perf_lbl in (
            self._perf_fps, self._perf_tick_ms,
            self._perf_organisms, self._perf_last_update,
        ):
            perf_lbl.config(bg=t["panel_bg"], fg=t["perf_fg"])

    # ── Export helpers ─────────────────────────────────────────────────────

    def _history_dict(self) -> Dict[str, List[int]]:
        eco = self._eco
        return {
            "plants": list(eco.plant_history),
            "herbivores": list(eco.herbivore_history),
            "carnivores": list(eco.carnivore_history),
        }

    def _metadata_dict(self) -> Dict[str, Any]:
        eco = self._eco
        return {
            "grid_size": eco.grid_size,
            "initial_plants": eco._init_plants,
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
