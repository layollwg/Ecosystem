from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme

# Preferred UI font (falls back gracefully on platforms that lack it)
_UI_FONT = "Arial"
_MONO_FONT = "Courier New"


class TooltipManager:
    """Shows a styled popup tooltip near the mouse cursor (game hover-card style)."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._window: Optional[tk.Toplevel] = None
        self._frame: Optional[tk.Frame] = None
        self._labels: List[tk.Label] = []

    def show(self, lines: List[str], colors: List[str], x: int, y: int) -> None:
        """Display or update the tooltip at screen position (x, y).

        ``lines`` is a list of text strings; ``colors`` is a matching list of
        hex colour strings for each line's foreground.
        """
        if self._window is None:
            self._window = tk.Toplevel(self._root)
            self._window.wm_overrideredirect(True)
            self._window.attributes("-topmost", True)
            outer = tk.Frame(
                self._window,
                bg="#00d4ff",
                padx=1, pady=1,
            )
            outer.pack()
            self._frame = tk.Frame(
                outer,
                bg="#16213e",
                padx=8, pady=6,
            )
            self._frame.pack()

        assert self._frame is not None

        # Rebuild label list to match the number of lines
        while len(self._labels) < len(lines):
            lbl = tk.Label(
                self._frame,
                text="",
                justify="left",
                bg="#16213e",
                font=(_UI_FONT, 10),
                anchor="w",
            )
            lbl.pack(anchor="w")
            self._labels.append(lbl)

        # Hide any extra labels
        for i, lbl in enumerate(self._labels):
            if i < len(lines):
                lbl.config(text=lines[i], fg=colors[i])
                lbl.pack(anchor="w")
            else:
                lbl.pack_forget()

        self._window.wm_geometry(f"+{x + 16}+{y + 16}")
        self._window.deiconify()

    def show_simple(self, text: str, x: int, y: int) -> None:
        """Convenience wrapper for a plain single-line tooltip."""
        self.show([text], ["#e8e8e8"], x, y)

    def hide(self) -> None:
        if self._window is not None:
            self._window.withdraw()

    def destroy(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None


class StatisticsPanel(tk.Frame):
    """Sidebar panel that displays real-time ecological statistics."""

    def __init__(self, parent: tk.Widget, theme: "Theme") -> None:
        super().__init__(parent)
        self.theme = theme
        self._prev_counts = {"plants": 0, "herbivores": 0, "carnivores": 0}
        self._build()

    def _build(self) -> None:
        t = self.theme
        self.config(bg=t["panel_bg"])
        self._themed: List[tk.Widget] = []

        def _section(text: str) -> tk.Label:
            lbl = tk.Label(
                self,
                text=text,
                font=(_UI_FONT, 11, "bold"),
                bg=t["panel_bg"],
                fg=t.get("fg_accent", t["fg"]),
                anchor="w",
            )
            lbl.pack(fill="x", padx=12, pady=(10, 2))
            self._themed.append(lbl)
            sep = tk.Frame(self, bg=t.get("border_glow", t["border"]), height=1)
            sep.pack(fill="x", padx=12)
            self._themed.append(sep)
            return lbl

        def _stat_row(icon: str, label_text: str, fg_key: str) -> tk.Label:
            row = tk.Frame(self, bg=t["panel_bg"])
            row.pack(fill="x", padx=14, pady=2)
            self._themed.append(row)
            tk.Label(row, text=icon, font=(_UI_FONT, 13),
                     bg=t["panel_bg"], fg=t[fg_key]).pack(side="left")
            name_lbl = tk.Label(
                row, text=label_text,
                font=(_UI_FONT, 10),
                bg=t["panel_bg"], fg=t["label_fg"],
            )
            name_lbl.pack(side="left", padx=(4, 0))
            val_lbl = tk.Label(
                row, text="--",
                font=(_UI_FONT, 11, "bold"),
                bg=t["panel_bg"], fg=t[fg_key],
            )
            val_lbl.pack(side="right")
            self._themed += [name_lbl, val_lbl]
            return val_lbl

        # ── Population ──────────────────────────────────────────────────────
        _section("🌍 Population")
        self._plant_val  = _stat_row("🌿", "Plants", "text_plant")
        self._herb_val   = _stat_row("🐇", "Herbivores", "text_herbivore")
        self._carn_val   = _stat_row("🐺", "Carnivores", "text_carnivore")

        # Trend row
        trend_row = tk.Frame(self, bg=t["panel_bg"])
        trend_row.pack(fill="x", padx=14, pady=(0, 4))
        self._themed.append(trend_row)
        for attr, label in (
            ("_plant_trend", "Plants"),
            ("_herb_trend", "Herbivores"),
            ("_carn_trend", "Carnivores"),
        ):
            f = tk.Frame(trend_row, bg=t["panel_bg"])
            f.pack(side="left", expand=True)
            tk.Label(f, text=label, font=(_UI_FONT, 8), bg=t["panel_bg"],
                     fg=t["label_fg"]).pack()
            lbl = tk.Label(f, text="→", font=(_UI_FONT, 14, "bold"),
                           bg=t["panel_bg"], fg=t["stat_neutral"])
            lbl.pack()
            setattr(self, attr, lbl)
            self._themed.append(f)

        # ── Averages ─────────────────────────────────────────────────────────
        _section("📈 Averages")
        self._avg_age    = _stat_row("⏱", "Avg Age", "fg")
        self._avg_energy = _stat_row("⚡", "Avg Energy", "fg")

        # ── This Tick ────────────────────────────────────────────────────────
        _section("🔄 This Tick")
        self._births_val = _stat_row("✨", "Births", "stat_positive")
        self._deaths_val = _stat_row("💀", "Deaths", "stat_negative")

        # ── Balance ──────────────────────────────────────────────────────────
        _section("⚖️ Ecology")

        bal_row = tk.Frame(self, bg=t["panel_bg"])
        bal_row.pack(fill="x", padx=14, pady=(2, 0))
        self._themed.append(bal_row)
        tk.Label(bal_row, text="Balance:", font=(_UI_FONT, 10),
                 bg=t["panel_bg"], fg=t["label_fg"]).pack(side="left")
        self._balance_lbl = tk.Label(
            bal_row, text="--/100",
            font=(_UI_FONT, 11, "bold"),
            bg=t["panel_bg"], fg=t.get("fg_highlight", t["stat_positive"]),
        )
        self._balance_lbl.pack(side="right")
        self._themed.append(self._balance_lbl)

        # Balance bar
        bar_bg = tk.Frame(self, bg=t.get("accent_bg", t["border"]), height=8)
        bar_bg.pack(fill="x", padx=14, pady=(2, 6))
        self._bar_bg = bar_bg
        self._bar_fill = tk.Frame(bar_bg, bg=t.get("fg_highlight", "#00ff88"), height=8)
        self._bar_fill.place(relx=0, rely=0, relwidth=0.0, relheight=1.0)
        self._themed.append(bar_bg)

        self._ratio_lbl = _stat_row("🔀", "Pred/Prey", "fg")

    # ── Public update ─────────────────────────────────────────────────────────

    def update_stats(self, data: Dict[str, Any]) -> None:
        p = data.get("plant_count", 0)
        h = data.get("herbivore_count", 0)
        c = data.get("carnivore_count", 0)

        self._plant_val.config(text=str(p))
        self._herb_val.config(text=str(h))
        self._carn_val.config(text=str(c))

        self._update_trend(self._plant_trend, p, self._prev_counts["plants"])
        self._update_trend(self._herb_trend,  h, self._prev_counts["herbivores"])
        self._update_trend(self._carn_trend,  c, self._prev_counts["carnivores"])
        self._prev_counts = {"plants": p, "herbivores": h, "carnivores": c}

        avg_age = data.get("avg_age", 0.0)
        avg_energy = data.get("avg_energy", 0.0)
        self._avg_age.config(text=f"{avg_age:.1f}")
        self._avg_energy.config(text=f"{avg_energy:.1f}")

        births = data.get("births_this_tick", 0)
        deaths = data.get("deaths_this_tick", 0)
        self._births_val.config(text=str(births))
        self._deaths_val.config(text=str(deaths))

        balance = self._calc_balance(p, h, c)
        self._balance_lbl.config(text=f"{balance}/100")
        self._bar_fill.place(relwidth=balance / 100)

        ratio_text = f"{c}/{h}" if h > 0 else "∞/0"
        self._ratio_lbl.config(text=ratio_text)

    def apply_theme(self, theme: "Theme") -> None:
        self.theme = theme
        t = theme
        self.config(bg=t["panel_bg"])
        for w in self._themed:
            try:
                w.config(bg=t["panel_bg"])  # type: ignore[call-arg]
            except tk.TclError:
                pass

        # Re-apply coloured widgets explicitly
        self._plant_val.config(fg=t["text_plant"])
        self._herb_val.config(fg=t["text_herbivore"])
        self._carn_val.config(fg=t["text_carnivore"])
        self._births_val.config(fg=t["stat_positive"])
        self._deaths_val.config(fg=t["stat_negative"])
        self._avg_age.config(fg=t["fg"])
        self._avg_energy.config(fg=t["fg"])
        self._balance_lbl.config(fg=t.get("fg_highlight", t["stat_positive"]))
        self._bar_fill.config(bg=t.get("fg_highlight", "#00ff88"))
        self._bar_bg.config(bg=t.get("accent_bg", t["border"]))

        for lbl in (self._plant_trend, self._herb_trend, self._carn_trend):
            cur_fg = lbl.cget("fg")
            if cur_fg in ("#2e7d32", "#a5d6a7", "#00ff88", "#00dd77"):
                lbl.config(fg=t["stat_positive"])
            elif cur_fg in ("#c62828", "#ef9a9a", "#ff4444", "#dd3333"):
                lbl.config(fg=t["stat_negative"])
            else:
                lbl.config(fg=t["stat_neutral"])

    def _update_trend(self, label: tk.Label, current: int, previous: int) -> None:
        t = self.theme
        if current > previous:
            label.config(text="↑", fg=t["stat_positive"])
        elif current < previous:
            label.config(text="↓", fg=t["stat_negative"])
        else:
            label.config(text="→", fg=t["stat_neutral"])

    @staticmethod
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


class EnhancedChart(tk.Canvas):
    """Canvas that draws population history with axis labels and subtle gridlines."""

    def __init__(self, parent: tk.Widget, theme: "Theme", **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.theme = theme

    def draw(
        self,
        plant_history: List[int],
        herbivore_history: List[int],
        carnivore_history: List[int],
    ) -> None:
        t = self.theme
        self.config(bg=t["chart_bg"])
        self.delete("all")

        history_length = len(plant_history)
        if history_length == 0:
            return

        width = max(int(self.winfo_width()), int(self.cget("width")))
        height = max(int(self.winfo_height()), int(self.cget("height")))
        if width <= 1:
            width = int(self.cget("width"))
        if height <= 1:
            height = int(self.cget("height"))

        left_margin   = 52
        right_margin  = 130
        top_margin    = 18
        bottom_margin = 32
        chart_w = width  - left_margin - right_margin
        chart_h = height - top_margin  - bottom_margin

        if chart_w <= 0 or chart_h <= 0:
            return

        max_value = max(
            max(plant_history,      default=0),
            max(herbivore_history,  default=0),
            max(carnivore_history,  default=0),
            1,
        )
        x_step  = chart_w / max(history_length - 1, 1)
        y_scale = chart_h / max_value

        ax_color   = t["chart_axis"]
        grid_color = t.get("chart_grid", "#1e2840")

        # Subtle horizontal gridlines (5 ticks)
        num_y_ticks = 5
        for i in range(1, num_y_ticks):
            y = top_margin + chart_h - int(chart_h * i / num_y_ticks)
            self.create_line(
                left_margin, y, left_margin + chart_w, y,
                fill=grid_color, dash=(3, 4),
            )

        # Axes
        self.create_line(left_margin, top_margin, left_margin, top_margin + chart_h,
                         fill=ax_color, width=1)
        self.create_line(left_margin, top_margin + chart_h,
                         left_margin + chart_w, top_margin + chart_h,
                         fill=ax_color, width=1)

        # Y-axis labels
        for i in range(num_y_ticks + 1):
            val = int(max_value * i / num_y_ticks)
            y = top_margin + chart_h - int(val * y_scale)
            self.create_line(left_margin - 4, y, left_margin, y, fill=ax_color)
            self.create_text(
                left_margin - 6, y,
                text=str(val), anchor="e",
                font=(_MONO_FONT, 8),
                fill=t["label_fg"],
            )

        # X-axis labels
        step = max(1, history_length // 8)
        for tick in range(0, history_length, step):
            x = left_margin + tick * x_step
            self.create_text(
                x, top_margin + chart_h + 14,
                text=str(tick + 1),
                font=(_MONO_FONT, 8),
                fill=t["label_fg"],
            )

        def _draw_series(history: List[int], color: str) -> None:
            if len(history) < 2:
                return
            points = []
            for idx, val in enumerate(history):
                x = left_margin + idx * x_step
                y = top_margin + chart_h - val * y_scale
                points.extend([x, y])
            self.create_line(*points, fill=color, width=2, smooth=True)
            # Endpoint dots only (avoids clutter)
            for idx in (0, len(history) - 1):
                val = history[idx]
                x = left_margin + idx * x_step
                y = top_margin + chart_h - val * y_scale
                self.create_oval(x - 3, y - 3, x + 3, y + 3,
                                 fill=color, outline=color)

        _draw_series(plant_history,     t["chart_plant"])
        _draw_series(herbivore_history, t["chart_herbivore"])
        _draw_series(carnivore_history, t["chart_carnivore"])

        # Legend + summary box
        lx = left_margin + chart_w + 10
        ly = top_margin
        box_w = right_margin - 14
        box_h = 74

        self.create_rectangle(
            lx - 2, ly - 2, lx + box_w + 2, ly + box_h + 2,
            fill=t["legend_bg"], outline=t.get("border_glow", t["legend_outline"]),
        )
        self.create_text(
            lx + 4, ly + 8,
            text="Legend", anchor="w",
            font=(_MONO_FONT, 8, "bold"),
            fill=t["label_fg"],
        )
        for i, (label, color) in enumerate([
            ("Plants",      t["chart_plant"]),
            ("Herbivores",  t["chart_herbivore"]),
            ("Carnivores",  t["chart_carnivore"]),
        ]):
            row_y = ly + 22 + i * 17
            self.create_line(lx + 4, row_y, lx + 18, row_y, fill=color, width=2)
            self.create_oval(lx + 10, row_y - 3, lx + 16, row_y + 3,
                             fill=color, outline=color)
            self.create_text(lx + 22, row_y, text=label, anchor="w",
                             font=(_MONO_FONT, 8), fill=color)

        # Min/Max/Avg summary
        stats_y = ly + box_h + 8
        for label, hist in [
            ("P", plant_history),
            ("H", herbivore_history),
            ("C", carnivore_history),
        ]:
            if hist:
                mn, mx, av = min(hist), max(hist), sum(hist) / len(hist)
                self.create_text(
                    lx + 4, stats_y,
                    text=f"{label}: ↓{mn} ↑{mx} ~{av:.0f}",
                    anchor="w",
                    font=(_MONO_FONT, 7),
                    fill=t["label_fg"],
                )
                stats_y += 13

    def apply_theme(self, theme: "Theme") -> None:
        self.theme = theme
