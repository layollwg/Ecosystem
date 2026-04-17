from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

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
        tk.Frame(self._content, bg=t.get("border_glow", t["border"]), height=1).pack(
            fill="x", pady=(4, 0)
        )
        tk.Label(
            self._content, text="📈 Population History",
            font=(_UI_FONT, 10, "bold"),
            bg=bg, fg=t.get("fg_accent", t["fg"]),
        ).pack(anchor="w", padx=8, pady=(4, 2))

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
        if self._stats_panel is not None:
            try:
                self._stats_panel.update_stats(data)
            except tk.TclError:
                pass
        if self._chart is not None:
            try:
                self._chart.draw(
                    data.get("plant_history", []),
                    data.get("herbivore_history", []),
                    data.get("carnivore_history", []),
                )
            except tk.TclError:
                pass
