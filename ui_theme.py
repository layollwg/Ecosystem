from __future__ import annotations

from typing import Dict

# Light theme colour palette
LIGHT: Dict[str, str] = {
    "bg": "#ffffff",
    "fg": "#000000",
    "grid_bg": "#f7f7f7",
    "grid_line": "#cccccc",
    "plant_fill": "#82c784",
    "herbivore_fill": "#ffd54f",
    "carnivore_fill": "#e57373",
    "empty_fill": "#ffffff",
    "panel_bg": "#f0f0f0",
    "button_bg": "#e3f2fd",
    "button_fg": "#000000",
    "button_active_bg": "#bbdefb",
    "chart_bg": "#f7f7f7",
    "chart_axis": "#444444",
    "chart_plant": "#388e3c",
    "chart_herbivore": "#f9a825",
    "chart_carnivore": "#c62828",
    "text_plant": "#2e7d32",
    "text_herbivore": "#e65100",
    "text_carnivore": "#b71c1c",
    "label_fg": "#333333",
    "legend_bg": "#ffffff",
    "legend_outline": "#cccccc",
    "stat_positive": "#2e7d32",
    "stat_negative": "#c62828",
    "stat_neutral": "#555555",
    "perf_fg": "#1565c0",
}

# Dark theme colour palette
DARK: Dict[str, str] = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "grid_bg": "#2d2d2d",
    "grid_line": "#444444",
    "plant_fill": "#66bb6a",
    "herbivore_fill": "#ffb74d",
    "carnivore_fill": "#ef5350",
    "empty_fill": "#2d2d2d",
    "panel_bg": "#252526",
    "button_bg": "#1565c0",
    "button_fg": "#ffffff",
    "button_active_bg": "#0d47a1",
    "chart_bg": "#2d2d2d",
    "chart_axis": "#888888",
    "chart_plant": "#81c784",
    "chart_herbivore": "#ffb74d",
    "chart_carnivore": "#ef9a9a",
    "text_plant": "#a5d6a7",
    "text_herbivore": "#ffe082",
    "text_carnivore": "#ef9a9a",
    "label_fg": "#aaaaaa",
    "legend_bg": "#333333",
    "legend_outline": "#555555",
    "stat_positive": "#a5d6a7",
    "stat_negative": "#ef9a9a",
    "stat_neutral": "#aaaaaa",
    "perf_fg": "#90caf9",
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
