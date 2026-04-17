from __future__ import annotations

from typing import Dict

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


class Theme:
    """Manages the active colour scheme and supports light/dark toggling."""

    def __init__(self, is_dark: bool = False) -> None:
        self._is_dark = is_dark
        self._colors: Dict[str, str] = DARK.copy() if is_dark else LIGHT.copy()

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def toggle(self) -> None:
        """Switch between light and dark mode."""
        self._is_dark = not self._is_dark
        self._colors = DARK.copy() if self._is_dark else LIGHT.copy()

    def get(self, key: str, fallback: str = "#000000") -> str:
        return self._colors.get(key, fallback)

    def __getitem__(self, key: str) -> str:
        return self.get(key)
