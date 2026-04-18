from __future__ import annotations

from typing import Dict, Optional

# ── Sunlit Nature Palette (向阳生态) ──────────────────────────────────────────
NATURE_LIGHT: Dict[str, str] = {
    # Backgrounds
    "bg":              "#FDFBF7",   # warm sandy white — main window & empty grid
    "card_bg":         "#FFFFFF",   # pure white cards
    "panel_bg":        "#F8FAFC",   # very light gray-white panels
    "accent_bg":       "#ECFDF5",   # pale mint — accent background
    "header_bg":       "#166534",   # deep forest green header
    # Text
    "fg":              "#166534",   # deep forest green — primary text
    "fg_secondary":    "#64748B",   # slate gray — secondary text
    "fg_accent":       "#10B981",   # emerald green — accents / links
    "fg_highlight":    "#22C55E",   # spring green — highlights
    # Grid
    "grid_bg":         "#FDFBF7",   # warm white grid background
    "grid_line":       "#ECFDF5",   # barely-visible pale-green grid lines
    "empty_fill":      "#FDFBF7",   # same as grid_bg — empty cells
    # Organisms
    "plant_fill":      "#DCFCE7",   # pale spring-green plant cells
    "herbivore_fill":  "#FEF3C7",   # pale amber herbivore cells
    "carnivore_fill":  "#FEE2E2",   # pale rose carnivore cells
    "text_plant":      "#22C55E",   # vivid spring green
    "text_herbivore":  "#F59E0B",   # warm amber
    "text_carnivore":  "#EF4444",   # berry red
    # Buttons
    "button_bg":       "#10B981",   # emerald green buttons
    "button_fg":       "#FFFFFF",
    "button_active_bg": "#059669",  # darker emerald on hover
    "button_border":   "#10B981",
    # Chart
    "chart_bg":        "#F8FAFC",
    "chart_axis":      "#94A3B8",   # cool slate
    "chart_grid":      "#E2E8F0",
    "chart_plant":     "#22C55E",
    "chart_herbivore": "#F59E0B",
    "chart_carnivore": "#EF4444",
    # Stats / labels
    "label_fg":        "#64748B",
    "legend_bg":       "#FFFFFF",
    "legend_outline":  "#E2E8F0",
    "stat_positive":   "#22C55E",
    "stat_negative":   "#EF4444",
    "stat_neutral":    "#94A3B8",
    "perf_fg":         "#10B981",
    # Borders
    "border":          "#E2E8F0",   # light gray border
    "border_glow":     "#A7F3D0",   # pale leaf-green glow
    "separator":       "#E2E8F0",
}

# ── Modern light theme ────────────────────────────────────────────────────────
LIGHT: Dict[str, str] = {
    # Backgrounds
    "bg":              "#f5f7fa",
    "card_bg":         "#ffffff",
    "panel_bg":        "#eef1f6",
    "accent_bg":       "#e3f2fd",
    "header_bg":       "#1a237e",
    # Text
    "fg":              "#1a1a2e",
    "fg_secondary":    "#555577",
    "fg_accent":       "#1565c0",
    "fg_highlight":    "#2e7d32",
    # Grid
    "grid_bg":         "#fafafa",
    "grid_line":       "#dde1e7",
    "empty_fill":      "#f5f5f5",
    # Organisms
    "plant_fill":      "#c8e6c9",
    "herbivore_fill":  "#fff9c4",
    "carnivore_fill":  "#ffcdd2",
    "text_plant":      "#2e7d32",
    "text_herbivore":  "#e65100",
    "text_carnivore":  "#b71c1c",
    # Buttons
    "button_bg":       "#1565c0",
    "button_fg":       "#ffffff",
    "button_active_bg": "#0d47a1",
    "button_border":   "#1565c0",
    # Chart
    "chart_bg":        "#fafafa",
    "chart_axis":      "#888888",
    "chart_grid":      "#eeeeee",
    "chart_plant":     "#388e3c",
    "chart_herbivore": "#f9a825",
    "chart_carnivore": "#c62828",
    # Stats / labels
    "label_fg":        "#555577",
    "legend_bg":       "#ffffff",
    "legend_outline":  "#cccccc",
    "stat_positive":   "#2e7d32",
    "stat_negative":   "#c62828",
    "stat_neutral":    "#777777",
    "perf_fg":         "#1565c0",
    # Borders
    "border":          "#dde1e7",
    "border_glow":     "#1565c0",
    "separator":       "#e0e0e0",
}

# ── Game-inspired dark theme (Slay the Spire / Hades style) ──────────────────
DARK: Dict[str, str] = {
    # Backgrounds
    "bg":              "#1a1a2e",
    "card_bg":         "#16213e",
    "panel_bg":        "#16213e",
    "accent_bg":       "#0f3460",
    "header_bg":       "#0d1117",
    # Text
    "fg":              "#e8e8e8",
    "fg_secondary":    "#a8a8a8",
    "fg_accent":       "#00d4ff",
    "fg_highlight":    "#00ff88",
    # Grid
    "grid_bg":         "#16213e",
    "grid_line":       "#0f3460",
    "empty_fill":      "#1e2d4d",
    # Organisms
    "plant_fill":      "#1a4a2e",
    "herbivore_fill":  "#4a3210",
    "carnivore_fill":  "#4a1a1a",
    "text_plant":      "#2ecc71",
    "text_herbivore":  "#f39c12",
    "text_carnivore":  "#e74c3c",
    # Buttons
    "button_bg":       "#0f3460",
    "button_fg":       "#00d4ff",
    "button_active_bg": "#1a4a80",
    "button_border":   "#00d4ff",
    # Chart
    "chart_bg":        "#0d1117",
    "chart_axis":      "#445566",
    "chart_grid":      "#1e2840",
    "chart_plant":     "#2ecc71",
    "chart_herbivore": "#f39c12",
    "chart_carnivore": "#e74c3c",
    # Stats / labels
    "label_fg":        "#a8a8a8",
    "legend_bg":       "#16213e",
    "legend_outline":  "#0f3460",
    "stat_positive":   "#00ff88",
    "stat_negative":   "#ff4444",
    "stat_neutral":    "#a8a8a8",
    "perf_fg":         "#00d4ff",
    # Borders
    "border":          "#0f3460",
    "border_glow":     "#00d4ff",
    "separator":       "#0f3460",
}


_PALETTES: Dict[str, Dict[str, str]] = {
    "dark":   DARK,
    "light":  LIGHT,
    "nature": NATURE_LIGHT,
}


class Theme:
    """Manages the active colour scheme.

    Supports three modes:
    * ``"dark"``   — game-inspired dark theme (default for backward compat)
    * ``"light"``  — modern light theme
    * ``"nature"`` — Sunlit Nature Palette (向阳生态)
    """

    def __init__(self, mode: str = "dark", *, is_dark: Optional[bool] = None) -> None:
        # Legacy is_dark kwarg kept for backward compatibility
        if is_dark is not None:
            mode = "dark" if is_dark else "light"
        self._mode = mode if mode in _PALETTES else "dark"
        self._colors: Dict[str, str] = _PALETTES[self._mode].copy()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_dark(self) -> bool:
        """True only for the dark theme (kept for backward compatibility)."""
        return self._mode == "dark"

    def set_mode(self, mode: str) -> None:
        """Switch to the given palette mode ("dark", "light", or "nature")."""
        if mode not in _PALETTES:
            return
        self._mode = mode
        self._colors = _PALETTES[mode].copy()

    def toggle(self) -> None:
        """Cycle through dark → light → nature → dark …"""
        modes = list(_PALETTES.keys())
        next_idx = (modes.index(self._mode) + 1) % len(modes)
        self.set_mode(modes[next_idx])

    def get(self, key: str, fallback: str = "#000000") -> str:
        return self._colors.get(key, fallback)

    def __getitem__(self, key: str) -> str:
        return self.get(key)
