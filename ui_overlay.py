from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme

_UI_FONT   = "Arial"
_MONO_FONT = "Courier New"


# ── Shared helper ─────────────────────────────────────────────────────────────

def _calc_balance(p: int, h: int, c: int) -> int:
    """Shannon diversity index mapped to 0–100."""
    counts = [x for x in (p, h, c) if x > 0]
    if not counts:
        return 0
    if len(counts) == 1:
        return 15
    total = sum(counts)
    proportions = [x / total for x in counts]
    diversity = -sum(pr * math.log(pr) for pr in proportions)
    max_diversity = math.log(len(counts))
    return int(diversity / max_diversity * 100) if max_diversity > 0 else 100


# ── StatsOverlay ──────────────────────────────────────────────────────────────

class StatsOverlay(tk.Frame):
    """Compact top-left overlay showing key simulation metrics in real time.

    Placed on the canvas with ``place(x=8, y=8)``.  Semi-transparent look is
    achieved by using the theme ``panel_bg`` colour against the grid canvas.
    """

    def __init__(self, parent: tk.Widget, theme: "Theme") -> None:
        t = theme
        super().__init__(
            parent,
            bg=t["panel_bg"],
            padx=10, pady=8,
            relief="flat", bd=0,
        )
        self._theme = theme
        self._build()

    def _build(self) -> None:
        t = self._theme
        bg = t["panel_bg"]

        # Title
        tk.Label(
            self, text="🌍 ECOSYSTEM",
            font=(_UI_FONT, 11, "bold"),
            bg=bg, fg=t.get("fg_accent", t["fg"]),
        ).pack(anchor="w")

        # Tick / season
        self._tick_lbl = tk.Label(
            self, text="Tick: —",
            font=(_UI_FONT, 10),
            bg=bg, fg=t.get("fg_secondary", t["fg"]),
        )
        self._tick_lbl.pack(anchor="w")

        # Status (shown on completion / pause)
        self._status_lbl = tk.Label(
            self, text="",
            font=(_UI_FONT, 9),
            bg=bg, fg=t.get("fg_accent", t["fg"]),
        )
        self._status_lbl.pack(anchor="w")

        # Species counts
        counts_row = tk.Frame(self, bg=bg)
        counts_row.pack(anchor="w", pady=(4, 0))

        self._plant_lbl = tk.Label(
            counts_row, text="🌿  —",
            font=(_UI_FONT, 10, "bold"),
            bg=bg, fg=t.get("text_plant", "#2ecc71"),
        )
        self._plant_lbl.pack(side="left", padx=(0, 6))

        self._herb_lbl = tk.Label(
            counts_row, text="🐇  —",
            font=(_UI_FONT, 10, "bold"),
            bg=bg, fg=t.get("text_herbivore", "#f39c12"),
        )
        self._herb_lbl.pack(side="left", padx=(0, 6))

        self._carn_lbl = tk.Label(
            counts_row, text="🐺  —",
            font=(_UI_FONT, 10, "bold"),
            bg=bg, fg=t.get("text_carnivore", "#e74c3c"),
        )
        self._carn_lbl.pack(side="left")

        # Balance bar
        bal_row = tk.Frame(self, bg=bg)
        bal_row.pack(anchor="w", fill="x", pady=(4, 0))

        tk.Label(
            bal_row, text="Balance:",
            font=(_UI_FONT, 9), bg=bg, fg=t.get("label_fg", t["fg"]),
        ).pack(side="left")

        self._balance_lbl = tk.Label(
            bal_row, text="—%",
            font=(_UI_FONT, 9, "bold"),
            bg=bg, fg=t.get("fg_highlight", "#00ff88"),
        )
        self._balance_lbl.pack(side="right")

        bar_bg = tk.Frame(self, bg=t.get("accent_bg", t["border"]), height=6)
        bar_bg.pack(fill="x", pady=(1, 0))
        self._bar_fill = tk.Frame(bar_bg, bg=t.get("fg_highlight", "#00ff88"), height=6)
        self._bar_fill.place(relx=0, rely=0, relwidth=0.0, relheight=1.0)

        # FPS
        self._fps_lbl = tk.Label(
            self, text="FPS: —",
            font=(_UI_FONT, 9),
            bg=bg, fg=t.get("perf_fg", t["fg"]),
        )
        self._fps_lbl.pack(anchor="w", pady=(4, 0))

        # Hint
        tk.Label(
            self,
            text="Scroll: zoom  |  RMB/MMB drag: pan  |  Dbl-click: reset",
            font=(_UI_FONT, 8),
            bg=bg, fg=t.get("label_fg", t["fg"]),
        ).pack(anchor="w", pady=(4, 0))

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, data: Dict[str, Any]) -> None:
        """Refresh all labels from a simulation data dict."""
        tick    = data.get("tick", 0)
        season  = data.get("season_emoji", "")
        plants  = data.get("plant_count", 0)
        herbs   = data.get("herbivore_count", 0)
        carns   = data.get("carnivore_count", 0)
        tick_ms = data.get("tick_time_ms", 0.0)
        fps     = 1000.0 / tick_ms if tick_ms > 0 else 0.0

        season_str = f"  {season}" if season else ""
        self._tick_lbl.config(text=f"Tick {tick}{season_str}")
        self._plant_lbl.config(text=f"🌿  {plants}")
        self._herb_lbl.config( text=f"🐇  {herbs}")
        self._carn_lbl.config( text=f"🐺  {carns}")

        balance = _calc_balance(plants, herbs, carns)
        self._balance_lbl.config(text=f"{balance}%")
        self._bar_fill.place(relwidth=balance / 100)
        self._fps_lbl.config(text=f"FPS: {fps:.0f}")

        # Clear any status message once new data arrives
        self._status_lbl.config(text="")

    def set_status(self, text: str) -> None:
        """Show a status message (e.g. 'Paused', '✅ Complete')."""
        try:
            self._status_lbl.config(text=text)
        except tk.TclError:
            pass


# ── PlaybackOverlay ───────────────────────────────────────────────────────────

class PlaybackOverlay(tk.Frame):
    """Bottom-centre floating playback control bar.

    Contains Pause / Resume, Step (single tick), Stop buttons and a speed
    (delay) slider.  Placed with ``place(relx=0.5, rely=1.0, y=-8, anchor='s')``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: "Theme",
        on_pause_toggle: Callable[[], None],
        on_step: Callable[[], None],
        on_stop: Callable[[], None],
        on_speed_change: Callable[[float], None],
        initial_delay: float = 0.1,
    ) -> None:
        t = theme
        super().__init__(
            parent,
            bg=t["panel_bg"],
            padx=12, pady=8,
            relief="flat", bd=0,
        )
        self._theme = theme
        self._on_pause_toggle = on_pause_toggle
        self._on_step = on_step
        self._on_stop = on_stop
        self._on_speed_change = on_speed_change
        self._paused = False
        self._build(initial_delay)

    def _build(self, initial_delay: float) -> None:
        t = self._theme
        bg = t["panel_bg"]
        font_btn = (_UI_FONT, 10, "bold")
        font_lbl = (_UI_FONT, 9)

        btn_row = tk.Frame(self, bg=bg)
        btn_row.pack()

        def _btn(text: str, cmd: Callable, width: int = 10) -> tk.Button:
            b = tk.Button(
                btn_row, text=text, width=width,
                font=font_btn,
                bg=t["button_bg"], fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=4, pady=3,
                cursor="hand2",
                command=cmd,
            )
            b.pack(side="left", padx=3)
            return b

        self._pause_btn = _btn("⏸  Pause",  self._on_pause_toggle, width=11)
        self._step_btn  = _btn("⏵  Step",   self._on_step,          width=10)
        _btn("⏹  Stop",   self._on_stop,          width=10)

        # Speed row
        speed_row = tk.Frame(self, bg=bg)
        speed_row.pack(pady=(4, 0))

        tk.Label(
            speed_row, text="Speed:",
            font=font_lbl, bg=bg, fg=t["fg"],
        ).pack(side="left", padx=4)

        self._speed_var = tk.DoubleVar(value=initial_delay)
        self._speed_var.trace_add("write", self._on_speed_internal)

        tk.Scale(
            speed_row,
            from_=0.0, to=1.0, resolution=0.05,
            orient="horizontal", length=160,
            variable=self._speed_var,
            bg=bg, fg=t["fg"],
            highlightthickness=0,
            troughcolor=t.get("bg", "#1a1a2e"),
            font=font_lbl,
        ).pack(side="left", padx=4)

        self._speed_lbl = tk.Label(
            speed_row,
            text=f"{initial_delay:.2f}s",
            font=(_MONO_FONT, 9),
            bg=bg, fg=t["fg"], width=5,
        )
        self._speed_lbl.pack(side="left")

    def _on_speed_internal(self, *_: Any) -> None:
        val = self._speed_var.get()
        try:
            self._speed_lbl.config(text=f"{val:.2f}s")
        except tk.TclError:
            pass
        self._on_speed_change(val)

    # ── Public API ────────────────────────────────────────────────────────────

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


# ── PopulationChartModal ──────────────────────────────────────────────────────

class PopulationChartModal:
    """Full-screen population-history chart shown in a separate Toplevel window.

    Opens a Toplevel dialog sized to 80 % of the parent window.  Displays a
    large :class:`~ui_widgets.EnhancedChart` so long-term trends are clearly
    visible.

    Usage::

        modal = PopulationChartModal(root_window, theme)
        modal.open(plant_history, herb_history, carn_history)
    """

    def __init__(self, parent: tk.Tk, theme: "Theme") -> None:
        self._parent = parent
        self._theme = theme
        self._window: Optional[tk.Toplevel] = None

    def open(
        self,
        plant_history: List[int],
        herbivore_history: List[int],
        carnivore_history: List[int],
    ) -> None:
        """Open (or bring to front) the chart modal with the given histories."""
        if self._window is not None:
            try:
                self._window.lift()
                self._window.focus_set()
                return
            except tk.TclError:
                self._window = None

        t = self._theme
        win = tk.Toplevel(self._parent)
        self._window = win
        win.title("📈 Population History")
        win.configure(bg=t["bg"])
        win.transient(self._parent)

        # Size: 80 % of the parent window, centred over it
        pw = max(self._parent.winfo_width(),  400)
        ph = max(self._parent.winfo_height(), 300)
        w  = int(pw * 0.82)
        h  = int(ph * 0.82)
        x  = self._parent.winfo_rootx() + (pw - w) // 2
        y  = self._parent.winfo_rooty() + (ph - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.minsize(560, 360)

        # Header bar
        hdr = tk.Frame(win, bg=t["panel_bg"], pady=8)
        hdr.pack(fill="x", padx=12, pady=(8, 0))

        tk.Label(
            hdr, text="📈  Population History",
            font=(_UI_FONT, 14, "bold"),
            bg=t["panel_bg"], fg=t.get("fg_accent", t["fg"]),
        ).pack(side="left", padx=4)

        tk.Button(
            hdr, text="✕  Close",
            font=(_UI_FONT, 10, "bold"),
            bg=t["button_bg"], fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            relief="flat", padx=8, pady=4,
            cursor="hand2",
            command=win.destroy,
        ).pack(side="right")

        # Thin separator
        tk.Frame(win, bg=t.get("border_glow", t["border"]), height=1).pack(
            fill="x", padx=12, pady=(4, 0)
        )

        # Large chart
        from ui_widgets import EnhancedChart

        chart = EnhancedChart(win, t, bg=t["chart_bg"])
        chart.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        # Draw once the widget has been sized
        win.update_idletasks()
        chart.draw(plant_history, herbivore_history, carnivore_history)

        # Keep chart up-to-date if the window is resized
        def _on_resize(event: tk.Event) -> None:  # type: ignore[type-arg]
            chart.draw(plant_history, herbivore_history, carnivore_history)

        chart.bind("<Configure>", _on_resize)

        # Clean up reference when the window is closed
        win.protocol("WM_DELETE_WINDOW", self._on_close)
        win.bind("<Escape>", lambda _e: win.destroy())

    def _on_close(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
        self._window = None


# ── DrawerPanel ───────────────────────────────────────────────────────────────

class DrawerPanel(tk.Frame):
    """Right-side collapsible panel showing detailed stats and population chart.

    When **open** the panel is ``OPEN_W`` pixels wide.  Clicking the toggle
    button collapses it to ``CLOSED_W`` pixels (just the button strip).

    Placed by ``SimulationPanel`` using
    ``place(relx=1.0, y=0, anchor='ne', relheight=1.0, width=OPEN_W)``.
    On toggle, ``place_configure(width=...)`` is called to change the width.
    """

    CLOSED_W: int = 40
    OPEN_W:   int = 290

    def __init__(self, parent: tk.Widget, theme: "Theme") -> None:
        t = theme
        super().__init__(
            parent,
            bg=t["panel_bg"],
            relief="flat", bd=0,
        )
        self._theme = theme
        self._is_open = True
        self._stats_panel: Optional[Any] = None
        self._chart: Optional[Any] = None
        # Cached history so the full-chart modal can display it
        self._plant_history:     List[int] = []
        self._herbivore_history: List[int] = []
        self._carnivore_history: List[int] = []
        self._chart_modal: Optional[PopulationChartModal] = None
        self._build()

    def _build(self) -> None:
        t = self._theme
        bg = t["panel_bg"]

        # Header row — always visible
        hdr = tk.Frame(self, bg=bg)
        hdr.pack(fill="x", padx=4, pady=4)

        self._toggle_btn = tk.Button(
            hdr,
            text="✕",
            font=(_UI_FONT, 12, "bold"),
            bg=t["button_bg"], fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            relief="flat", padx=4, pady=2,
            cursor="hand2",
            command=self.toggle,
        )
        self._toggle_btn.pack(side="right")

        self._title_lbl = tk.Label(
            hdr, text="📊 Data",
            font=(_UI_FONT, 10, "bold"),
            bg=bg, fg=t.get("fg_accent", t["fg"]),
        )
        self._title_lbl.pack(side="left", padx=4)

        # Separator
        tk.Frame(self, bg=t.get("border_glow", t["border"]), height=1).pack(fill="x")

        # Content frame (hidden when closed)
        self._content = tk.Frame(self, bg=bg)
        self._content.pack(fill="both", expand=True, padx=2, pady=2)

        # Import here to avoid circular imports at module load time
        from ui_widgets import StatisticsPanel, EnhancedChart

        self._stats_panel = StatisticsPanel(self._content, self._theme)
        self._stats_panel.pack(fill="x")

        # Chart section
        chart_hdr = tk.Frame(self._content, bg=bg)
        chart_hdr.pack(fill="x", pady=(4, 0))
        tk.Frame(chart_hdr, bg=t.get("border_glow", t["border"]), height=1).pack(
            fill="x"
        )
        chart_title_row = tk.Frame(chart_hdr, bg=bg)
        chart_title_row.pack(fill="x")
        tk.Label(
            chart_title_row, text="📈 Population History",
            font=(_UI_FONT, 10, "bold"),
            bg=bg, fg=t.get("fg_accent", t["fg"]),
        ).pack(side="left", padx=8, pady=(4, 2))

        # "View Full Chart" button sits on the same row as the section title
        # so it is always visible regardless of window height.
        tk.Button(
            chart_title_row,
            text="⛶ Full",
            font=(_UI_FONT, 8),
            bg=t["button_bg"], fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            relief="flat", padx=4, pady=1,
            cursor="hand2",
            command=self._open_chart_modal,
        ).pack(side="right", padx=(0, 8), pady=(4, 2))

        self._chart = EnhancedChart(
            self._content, self._theme,
            width=self.OPEN_W - 16, height=140,
            bg=t["chart_bg"],
        )
        self._chart.pack(padx=4, pady=(0, 4))

    # ── Public API ────────────────────────────────────────────────────────────

    def toggle(self) -> None:
        """Open or close the drawer panel."""
        self._is_open = not self._is_open
        if self._is_open:
            self._content.pack(fill="both", expand=True, padx=2, pady=2)
            self._toggle_btn.config(text="✕")
            self._title_lbl.config(text="📊 Data")
            self.place_configure(width=self.OPEN_W)
        else:
            self._content.pack_forget()
            self._toggle_btn.config(text="≡")
            self._title_lbl.config(text="")
            self.place_configure(width=self.CLOSED_W)

    def update_data(self, data: Dict[str, Any]) -> None:
        """Update internal stats panel and chart from a simulation data dict."""
        self._plant_history     = data.get("plant_history",      [])
        self._herbivore_history = data.get("herbivore_history",  [])
        self._carnivore_history = data.get("carnivore_history",  [])
        if self._stats_panel is not None:
            try:
                self._stats_panel.update_stats(data)
            except tk.TclError:
                pass
        if self._chart is not None:
            try:
                self._chart.draw(
                    self._plant_history,
                    self._herbivore_history,
                    self._carnivore_history,
                )
            except tk.TclError:
                pass

    def _open_chart_modal(self) -> None:
        """Open (or raise) the full-screen population-history chart."""
        root = self.winfo_toplevel()
        if self._chart_modal is None:
            self._chart_modal = PopulationChartModal(root, self._theme)
        self._chart_modal.open(
            self._plant_history,
            self._herbivore_history,
            self._carnivore_history,
        )
