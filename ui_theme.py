from __future__ import annotations

from typing import Dict, Optional

# ── Sunlit Nature Palette (向阳生态) ──────────────────────────────────────────
NATURE_LIGHT: Dict[str, str] = {
    # Backgrounds
    "bg":              "#F2EFE7",   # warm linen — softer than pure white
    "card_bg":         "#F7F4ED",   # light parchment cards
    "panel_bg":        "#ECE8DF",   # muted warm panel background
    "accent_bg":       "#E1E9DC",   # soft sage accent
    "header_bg":       "#2D5A4B",   # deep muted forest green header
    # Text
    "fg":              "#2D4A3F",   # muted forest green — primary text
    "fg_secondary":    "#6B7280",   # calm slate gray — secondary text
    "fg_accent":       "#4F8A72",   # softened emerald accent
    "fg_highlight":    "#5D9A72",   # gentle green highlight
    # Grid
    "grid_bg":         "#EFEAE1",   # soft warm grid background
    "grid_line":       "#D2CEC3",   # gentle neutral grid lines
    "empty_fill":      "#EEE9E0",   # subtle empty cells
    "terrain_water":   "#8AAFC9",
    "terrain_sand":    "#D8C39E",
    "terrain_dirt":    "#B8C89A",
    "terrain_mountain":"#8B9299",
    # Organisms
    "plant_fill":      "#C9DAB6",   # muted soft-green plant cells
    "herbivore_fill":  "#E4D4B3",   # muted amber herbivore cells
    "carnivore_fill":  "#DBBDBE",   # muted rose carnivore cells
    "text_plant":      "#4E7F4D",   # earthy green
    "text_herbivore":  "#936A33",   # subdued amber-brown
    "text_carnivore":  "#954A4F",   # muted red-brown
    # Buttons
    "button_bg":       "#4F8A72",   # muted emerald buttons
    "button_fg":       "#FFFFFF",
    "button_active_bg": "#3F735F",  # darker muted emerald on hover
    "button_border":   "#4F8A72",
    # Chart
    "chart_bg":        "#EDE8DE",
    "chart_axis":      "#7E8794",   # softened slate
    "chart_grid":      "#D4D0C6",
    "chart_plant":     "#4E7F4D",
    "chart_herbivore": "#936A33",
    "chart_carnivore": "#954A4F",
    # Stats / labels
    "label_fg":        "#6B7280",
    "legend_bg":       "#F7F4ED",
    "legend_outline":  "#D4D0C6",
    "stat_positive":   "#5D9A72",
    "stat_negative":   "#954A4F",
    "stat_neutral":    "#7E8794",
    "perf_fg":         "#4F8A72",
    # Borders
    "border":          "#CFCAC0",   # warm gray border
    "border_glow":     "#B8C8B6",   # subtle leaf glow
    "separator":       "#D4D0C6",
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
    "terrain_water":   "#90caf9",
    "terrain_sand":    "#ffe0b2",
    "terrain_dirt":    "#c5e1a5",
    "terrain_mountain":"#9e9e9e",
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
    "terrain_water":   "#1d4ed8",
    "terrain_sand":    "#8b6d3a",
    "terrain_dirt":    "#355e3b",
    "terrain_mountain":"#4b5563",
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
