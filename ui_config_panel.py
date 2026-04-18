from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme

import config as _cfg

_UI_FONT = "Arial"
_MONO_FONT = "Courier New"

# Default population counts per preset name
_PRESET_DEFAULTS: Dict[str, tuple] = {
    # (grid_size, plants, herbivores, carnivores, total_ticks, tick_delay)
    "stable":   (20, 80, 30, 5,  500, 0.10),
    "balanced": (25, 80, 30, 5,  500, 0.10),
    "intense":  (20, 80, 35, 8,  500, 0.10),
}
_FALLBACK_DEFAULTS = (20, 50, 30, 5, 500, 0.10)


class ConfigPanel(tk.Frame):
    """Pre-simulation configuration panel.

    Shows preset quick-select buttons and sliders for all key parameters.
    Calls ``on_start(params)`` when the user confirms the configuration.
    Optionally calls ``on_theme_change(mode)`` when a theme button is clicked.
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: "Theme",
        on_start: Callable[[Dict[str, Any]], None],
        on_theme_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._on_start = on_start
        self._on_theme_change = on_theme_change
        self._preset_var = tk.StringVar(value="stable")
        self._preset_btn_refs: List[tuple] = []
        self._theme_btn_refs: List[tuple] = []
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        t = self._theme
        self.config(bg=t["bg"])

        outer = tk.Frame(self, bg=t["bg"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=t["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=t["bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_cfg(_evt: Any) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_cfg(evt: Any) -> None:
            canvas.itemconfig(win_id, width=evt.width)

        inner.bind("<Configure>", _on_inner_cfg)
        canvas.bind("<Configure>", _on_canvas_cfg)

        def _on_mousewheel(evt: Any) -> None:
            canvas.yview_scroll(int(-1 * (evt.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_content(inner)

    def _build_content(self, parent: tk.Frame) -> None:
        t = self._theme

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(parent, bg=t.get("header_bg", t["bg"]))
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="🌍  ECOSYSTEM SIMULATOR",
            font=(_UI_FONT, 22, "bold"),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_accent", t["fg"]),
            pady=16,
        ).pack()
        tk.Label(
            hdr,
            text="Configure your simulation parameters then press Start",
            font=(_UI_FONT, 11),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_secondary", t["fg"]),
            pady=4,
        ).pack()
        tk.Frame(parent, bg=t.get("border_glow", t["border"]), height=2).pack(fill="x")

        # ── Two-column body ───────────────────────────────────────────────────
        body = tk.Frame(parent, bg=t["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=8)

        left = tk.Frame(body, bg=t["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(body, bg=t["bg"])
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # ── Theme selector ────────────────────────────────────────────────────
        if self._on_theme_change is not None:
            self._build_theme_selector(left)

        # ── Presets ───────────────────────────────────────────────────────────
        self._build_presets(left)

        # ── General ───────────────────────────────────────────────────────────
        self._grid_size_var = tk.IntVar(value=20)
        self._total_ticks_var = tk.IntVar(value=500)
        self._tick_delay_var = tk.DoubleVar(value=0.10)
        gen = self._card(left, "⚙️  General Settings")
        self._add_int_slider(gen, "Grid Size", self._grid_size_var, 10, 50)
        self._add_int_slider(gen, "Total Ticks", self._total_ticks_var, 100, 2000, step=50)
        self._add_float_slider(gen, "Tick Delay (s)", self._tick_delay_var, 0.0, 1.0, step=0.05)

        # ── Plants ────────────────────────────────────────────────────────────
        self._plants_var = tk.IntVar(value=80)
        plant_card = self._card(left, "🌿  Plants")
        self._add_int_slider(plant_card, "Initial Count", self._plants_var, 5, 300)

        # ── Herbivores ────────────────────────────────────────────────────────
        self._herbivores_var = tk.IntVar(value=30)
        herb_card = self._card(right, "🐇  Herbivores")
        self._add_int_slider(herb_card, "Initial Count", self._herbivores_var, 1, 150)

        # ── Carnivores ────────────────────────────────────────────────────────
        self._carnivores_var = tk.IntVar(value=5)
        carn_card = self._card(right, "🐺  Carnivores")
        self._add_int_slider(carn_card, "Initial Count", self._carnivores_var, 1, 50)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(parent, bg=t["bg"])
        btn_row.pack(fill="x", padx=24, pady=16)

        tk.Button(
            btn_row,
            text="🔄  Reset to Defaults",
            font=(_UI_FONT, 11),
            bg=t["panel_bg"],
            fg=t["fg"],
            activebackground=t["button_active_bg"],
            relief="flat", padx=12, pady=8,
            cursor="hand2",
            command=self._on_reset,
        ).pack(side="left", padx=4)

        tk.Button(
            btn_row,
            text="▶  Start Simulation",
            font=(_UI_FONT, 13, "bold"),
            bg=t["button_bg"],
            fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            relief="flat", padx=20, pady=8,
            cursor="hand2",
            command=self._on_start_clicked,
        ).pack(side="right", padx=4)

    # ── Preset section ────────────────────────────────────────────────────────

    def _build_theme_selector(self, parent: tk.Widget) -> None:
        t = self._theme
        card = self._card(parent, "🎨  Theme")

        btn_row = tk.Frame(card, bg=t["card_bg"])
        btn_row.pack(fill="x", pady=(0, 4))

        _theme_options: List[tuple] = [
            ("nature", "🌿 Nature"),
            ("dark",   "🌑 Dark"),
            ("light",  "☀️ Light"),
        ]

        self._theme_btn_refs = []
        for mode, label in _theme_options:
            is_active = mode == t.mode
            btn = tk.Button(
                btn_row,
                text=label,
                font=(_UI_FONT, 10, "bold"),
                bg=t["button_bg"] if is_active else t["panel_bg"],
                fg=t["button_fg"] if is_active else t["fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=8, pady=5,
                cursor="hand2",
                command=lambda m=mode: self._select_theme(m),
            )
            btn.pack(side="left", padx=4, pady=4, expand=True, fill="x")
            self._theme_btn_refs.append((mode, btn))

    def _select_theme(self, mode: str) -> None:
        if self._on_theme_change is not None:
            self._on_theme_change(mode)

    def _build_presets(self, parent: tk.Widget) -> None:
        t = self._theme
        card = self._card(parent, "⭐  Quick Presets")

        btn_row = tk.Frame(card, bg=t["card_bg"])
        btn_row.pack(fill="x", pady=(0, 4))

        _preset_styles: Dict[str, tuple] = {
            "stable":   ("⭐ Stable",   t.get("stat_positive", t["fg"])),
            "balanced": ("⚔️ Balanced", t.get("fg_accent",     t["fg"])),
            "intense":  ("🔥 Intense",  t.get("stat_negative", t["fg"])),
        }

        self._preset_btn_refs = []
        for name, (label, color) in _preset_styles.items():
            is_active = name == self._preset_var.get()
            btn = tk.Button(
                btn_row,
                text=label,
                font=(_UI_FONT, 11, "bold"),
                bg=t["button_bg"] if is_active else t["panel_bg"],
                fg=color,
                activebackground=t["button_active_bg"],
                relief="flat", padx=10, pady=6,
                cursor="hand2",
                command=lambda n=name: self._select_preset(n),
            )
            btn.pack(side="left", padx=4, pady=4, expand=True, fill="x")
            self._preset_btn_refs.append((name, btn))

        self._preset_desc = tk.Label(
            card,
            text=_cfg.PRESETS.get("stable", {}).get("description", ""),
            font=(_UI_FONT, 10),
            bg=t["card_bg"],
            fg=t.get("fg_secondary", t["fg"]),
            wraplength=280,
            justify="left",
        )
        self._preset_desc.pack(anchor="w", padx=4, pady=(0, 4))

    def _select_preset(self, name: str) -> None:
        self._preset_var.set(name)
        t = self._theme
        for pname, btn in self._preset_btn_refs:
            btn.config(bg=t["button_bg"] if pname == name else t["panel_bg"])
        desc = _cfg.PRESETS.get(name, {}).get("description", "")
        self._preset_desc.config(text=desc)
        self._apply_preset_defaults(name)

    def _apply_preset_defaults(self, name: str) -> None:
        _cfg.load_preset(name)
        gs, pl, hb, ca, tk_, dl = _PRESET_DEFAULTS.get(name, _FALLBACK_DEFAULTS)
        self._grid_size_var.set(gs)
        self._plants_var.set(pl)
        self._herbivores_var.set(hb)
        self._carnivores_var.set(ca)
        self._total_ticks_var.set(tk_)
        self._tick_delay_var.set(dl)

    def _on_reset(self) -> None:
        self._apply_preset_defaults(self._preset_var.get())

    # ── Card / slider helpers ─────────────────────────────────────────────────

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        t = self._theme
        outer = tk.Frame(parent, bg=t.get("border_glow", t["border"]), padx=1, pady=1)
        outer.pack(fill="x", pady=5)
        card = tk.Frame(outer, bg=t["card_bg"], padx=12, pady=8)
        card.pack(fill="x")
        tk.Label(
            card, text=title,
            font=(_UI_FONT, 11, "bold"),
            bg=t["card_bg"], fg=t.get("fg_accent", t["fg"]),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        tk.Frame(card, bg=t.get("border", "#333"), height=1).pack(fill="x", pady=(0, 6))
        return card

    def _add_int_slider(
        self,
        parent: tk.Widget,
        label: str,
        var: tk.IntVar,
        from_: int,
        to: int,
        step: int = 1,
    ) -> None:
        t = self._theme
        row = tk.Frame(parent, bg=t["card_bg"])
        row.pack(fill="x", pady=3)
        tk.Label(
            row, text=label,
            font=(_UI_FONT, 10),
            bg=t["card_bg"], fg=t["label_fg"],
            width=16, anchor="w",
        ).pack(side="left")
        val_lbl = tk.Label(
            row, text=str(var.get()),
            font=(_MONO_FONT, 10, "bold"),
            bg=t["card_bg"], fg=t["fg"],
            width=5, anchor="e",
        )
        val_lbl.pack(side="right")
        tk.Scale(
            row, from_=from_, to=to, resolution=step,
            orient="horizontal",
            variable=var,
            bg=t["card_bg"], fg=t["fg"],
            highlightthickness=0,
            troughcolor=t["panel_bg"],
            showvalue=False,
            command=lambda v: val_lbl.config(text=str(int(float(v)))),
        ).pack(side="left", fill="x", expand=True, padx=4)

    def _add_float_slider(
        self,
        parent: tk.Widget,
        label: str,
        var: tk.DoubleVar,
        from_: float,
        to: float,
        step: float = 0.05,
    ) -> None:
        t = self._theme
        row = tk.Frame(parent, bg=t["card_bg"])
        row.pack(fill="x", pady=3)
        tk.Label(
            row, text=label,
            font=(_UI_FONT, 10),
            bg=t["card_bg"], fg=t["label_fg"],
            width=16, anchor="w",
        ).pack(side="left")
        val_lbl = tk.Label(
            row, text=f"{var.get():.2f}",
            font=(_MONO_FONT, 10, "bold"),
            bg=t["card_bg"], fg=t["fg"],
            width=5, anchor="e",
        )
        val_lbl.pack(side="right")
        tk.Scale(
            row, from_=from_, to=to, resolution=step,
            orient="horizontal",
            variable=var,
            bg=t["card_bg"], fg=t["fg"],
            highlightthickness=0,
            troughcolor=t["panel_bg"],
            showvalue=False,
            command=lambda v: val_lbl.config(text=f"{float(v):.2f}"),
        ).pack(side="left", fill="x", expand=True, padx=4)

    # ── Start callback ────────────────────────────────────────────────────────

    def _on_start_clicked(self) -> None:
        params = self.get_params()
        total_orgs = params["plants"] + params["herbivores"] + params["carnivores"]
        capacity = params["grid_size"] ** 2
        if total_orgs > capacity:
            messagebox.showerror(
                "Invalid Configuration",
                f"Total organisms ({total_orgs}) exceeds grid capacity "
                f"({capacity} cells for a {params['grid_size']}×{params['grid_size']} grid).\n\n"
                "Reduce organism counts or increase the grid size.",
            )
            return
        self._on_start(params)

    def get_params(self) -> Dict[str, Any]:
        """Return the current parameter values as a dict."""
        return {
            "preset":       self._preset_var.get(),
            "grid_size":    self._grid_size_var.get(),
            "total_ticks":  self._total_ticks_var.get(),
            "tick_delay":   self._tick_delay_var.get(),
            "plants":       self._plants_var.get(),
            "herbivores":   self._herbivores_var.get(),
            "carnivores":   self._carnivores_var.get(),
        }
