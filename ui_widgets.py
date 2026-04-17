from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme


class TooltipManager:
    """Shows a small popup tooltip near the mouse cursor."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._window: Optional[tk.Toplevel] = None
        self._label: Optional[tk.Label] = None

    def show(self, text: str, x: int, y: int) -> None:
        """Display or update the tooltip at screen position (x, y)."""
        if self._window is None:
            self._window = tk.Toplevel(self._root)
            self._window.wm_overrideredirect(True)
            self._window.attributes("-topmost", True)
            self._label = tk.Label(
                self._window,
                text=text,
                justify="left",
                background="#ffffcc",
                relief="solid",
                borderwidth=1,
                font=("Consolas", 9),
                padx=4,
                pady=2,
            )
            self._label.pack()
        else:
            if self._label:
                self._label.config(text=text)
        self._window.wm_geometry(f"+{x + 14}+{y + 14}")
        self._window.deiconify()

    def hide(self) -> None:
        """Hide the tooltip."""
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
    """Tab panel that displays real-time ecological statistics."""

    def __init__(self, parent: tk.Widget, theme: "Theme") -> None:
        super().__init__(parent)
        self.theme = theme
        self._prev_counts = {"plants": 0, "herbivores": 0, "carnivores": 0}
        self._build()

    def _build(self) -> None:
        t = self.theme
        self.config(bg=t["panel_bg"])

        title = tk.Label(
            self,
            text="Real-time Statistics",
            font=("Consolas", 13, "bold"),
            bg=t["panel_bg"],
            fg=t["fg"],
        )
        title.grid(row=0, column=0, columnspan=4, pady=(12, 8))
        self._themed: List[tk.Widget] = [title]

        # ── Population row ──────────────────────────────────────────────────
        pop_frame = tk.LabelFrame(
            self,
            text="Population",
            font=("Consolas", 10, "bold"),
            bg=t["panel_bg"],
            fg=t["fg"],
        )
        pop_frame.grid(row=1, column=0, columnspan=4, padx=16, pady=6, sticky="ew")
        self._themed.append(pop_frame)

        self._plant_cnt = tk.Label(
            pop_frame, text="Plants: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["text_plant"],
        )
        self._plant_cnt.grid(row=0, column=0, padx=12, pady=4)

        self._herb_cnt = tk.Label(
            pop_frame, text="Herbivores: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["text_herbivore"],
        )
        self._herb_cnt.grid(row=0, column=1, padx=12, pady=4)

        self._carn_cnt = tk.Label(
            pop_frame, text="Carnivores: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["text_carnivore"],
        )
        self._carn_cnt.grid(row=0, column=2, padx=12, pady=4)

        self._plant_trend = tk.Label(
            pop_frame, text="→", font=("Consolas", 14),
            bg=t["panel_bg"], fg=t["stat_neutral"],
        )
        self._plant_trend.grid(row=1, column=0, padx=12)
        self._herb_trend = tk.Label(
            pop_frame, text="→", font=("Consolas", 14),
            bg=t["panel_bg"], fg=t["stat_neutral"],
        )
        self._herb_trend.grid(row=1, column=1, padx=12)
        self._carn_trend = tk.Label(
            pop_frame, text="→", font=("Consolas", 14),
            bg=t["panel_bg"], fg=t["stat_neutral"],
        )
        self._carn_trend.grid(row=1, column=2, padx=12)

        self._themed += [
            self._plant_cnt, self._herb_cnt, self._carn_cnt,
            self._plant_trend, self._herb_trend, self._carn_trend,
        ]

        # ── Averages ─────────────────────────────────────────────────────────
        avg_frame = tk.LabelFrame(
            self, text="Averages (animals)", font=("Consolas", 10, "bold"),
            bg=t["panel_bg"], fg=t["fg"],
        )
        avg_frame.grid(row=2, column=0, columnspan=4, padx=16, pady=6, sticky="ew")
        self._themed.append(avg_frame)

        self._avg_age = tk.Label(
            avg_frame, text="Avg Age: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["fg"],
        )
        self._avg_age.grid(row=0, column=0, padx=12, pady=4)

        self._avg_energy = tk.Label(
            avg_frame, text="Avg Energy: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["fg"],
        )
        self._avg_energy.grid(row=0, column=1, padx=12, pady=4)

        self._themed += [self._avg_age, self._avg_energy]

        # ── Births / Deaths ───────────────────────────────────────────────
        bd_frame = tk.LabelFrame(
            self, text="This Tick", font=("Consolas", 10, "bold"),
            bg=t["panel_bg"], fg=t["fg"],
        )
        bd_frame.grid(row=3, column=0, columnspan=4, padx=16, pady=6, sticky="ew")
        self._themed.append(bd_frame)

        self._births = tk.Label(
            bd_frame, text="Births: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["stat_positive"],
        )
        self._births.grid(row=0, column=0, padx=12, pady=4)

        self._deaths = tk.Label(
            bd_frame, text="Deaths: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["stat_negative"],
        )
        self._deaths.grid(row=0, column=1, padx=12, pady=4)

        self._themed += [self._births, self._deaths]

        # ── Ecological indices ───────────────────────────────────────────────
        eco_frame = tk.LabelFrame(
            self, text="Ecological Indices", font=("Consolas", 10, "bold"),
            bg=t["panel_bg"], fg=t["fg"],
        )
        eco_frame.grid(row=4, column=0, columnspan=4, padx=16, pady=6, sticky="ew")
        self._themed.append(eco_frame)

        self._balance = tk.Label(
            eco_frame, text="Balance Index: --/100", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["fg"],
        )
        self._balance.grid(row=0, column=0, padx=12, pady=4)

        self._ratio = tk.Label(
            eco_frame, text="Pred/Prey Ratio: --", font=("Consolas", 11),
            bg=t["panel_bg"], fg=t["fg"],
        )
        self._ratio.grid(row=0, column=1, padx=12, pady=4)

        self._themed += [self._balance, self._ratio]

    def update_stats(self, data: Dict[str, Any]) -> None:
        """Refresh all displayed statistics from the data dict."""
        p = data.get("plant_count", 0)
        h = data.get("herbivore_count", 0)
        c = data.get("carnivore_count", 0)

        self._plant_cnt.config(text=f"Plants: {p}")
        self._herb_cnt.config(text=f"Herbivores: {h}")
        self._carn_cnt.config(text=f"Carnivores: {c}")

        self._update_trend(self._plant_trend, p, self._prev_counts["plants"])
        self._update_trend(self._herb_trend, h, self._prev_counts["herbivores"])
        self._update_trend(self._carn_trend, c, self._prev_counts["carnivores"])
        self._prev_counts = {"plants": p, "herbivores": h, "carnivores": c}

        avg_age = data.get("avg_age", 0.0)
        avg_energy = data.get("avg_energy", 0.0)
        self._avg_age.config(text=f"Avg Age: {avg_age:.1f}")
        self._avg_energy.config(text=f"Avg Energy: {avg_energy:.1f}")

        births = data.get("births_this_tick", 0)
        deaths = data.get("deaths_this_tick", 0)
        self._births.config(text=f"Births: {births}")
        self._deaths.config(text=f"Deaths: {deaths}")

        balance = self._calc_balance(p, h, c)
        self._balance.config(text=f"Balance Index: {balance}/100")
        ratio_text = f"{c}/{h}" if h > 0 else "∞/0"
        self._ratio.config(text=f"Pred/Prey Ratio: {ratio_text}")

    def apply_theme(self, theme: "Theme") -> None:
        self.theme = theme
        t = theme
        self.config(bg=t["panel_bg"])
        for w in self._themed:
            try:
                if isinstance(w, tk.LabelFrame):
                    w.config(bg=t["panel_bg"], fg=t["fg"])
                else:
                    w.config(bg=t["panel_bg"])
            except tk.TclError:
                pass
        self._plant_cnt.config(fg=t["text_plant"])
        self._herb_cnt.config(fg=t["text_herbivore"])
        self._carn_cnt.config(fg=t["text_carnivore"])
        self._births.config(fg=t["stat_positive"])
        self._deaths.config(fg=t["stat_negative"])
        self._avg_age.config(fg=t["fg"])
        self._avg_energy.config(fg=t["fg"])
        self._balance.config(fg=t["fg"])
        self._ratio.config(fg=t["fg"])
        # Refresh trends
        for lbl in (self._plant_trend, self._herb_trend, self._carn_trend):
            cur_fg = lbl.cget("fg")
            if cur_fg == "#2e7d32" or cur_fg == "#a5d6a7":
                lbl.config(fg=t["stat_positive"])
            elif cur_fg == "#c62828" or cur_fg == "#ef9a9a":
                lbl.config(fg=t["stat_negative"])
            else:
                lbl.config(fg=t["stat_neutral"])

    @staticmethod
    def _update_trend(label: tk.Label, current: int, previous: int) -> None:
        if current > previous:
            label.config(text="↑", fg="#2e7d32")
        elif current < previous:
            label.config(text="↓", fg="#c62828")
        else:
            label.config(text="→", fg="#555555")

    @staticmethod
    def _calc_balance(p: int, h: int, c: int) -> int:
        """Shannon diversity index mapped to 0-100."""
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
    """Canvas that draws population history with Y-axis labels and statistics."""

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

        left_margin = 48
        right_margin = 120
        top_margin = 20
        bottom_margin = 30
        chart_w = width - left_margin - right_margin
        chart_h = height - top_margin - bottom_margin

        if chart_w <= 0 or chart_h <= 0:
            return

        max_value = max(
            max(plant_history, default=0),
            max(herbivore_history, default=0),
            max(carnivore_history, default=0),
            1,
        )
        x_step = chart_w / max(history_length - 1, 1)
        y_scale = chart_h / max_value

        # Draw axes
        ax_color = t["chart_axis"]
        self.create_line(left_margin, top_margin, left_margin, top_margin + chart_h, fill=ax_color)
        self.create_line(
            left_margin, top_margin + chart_h,
            left_margin + chart_w, top_margin + chart_h,
            fill=ax_color,
        )

        # Y-axis labels (5 ticks)
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            val = int(max_value * i / num_y_ticks)
            y = top_margin + chart_h - int(val * y_scale)
            self.create_line(left_margin - 4, y, left_margin, y, fill=ax_color)
            self.create_text(
                left_margin - 6, y,
                text=str(val),
                anchor="e",
                font=("Consolas", 8),
                fill=t["label_fg"],
            )

        # X-axis labels
        step = max(1, history_length // 8)
        for tick in range(0, history_length, step):
            x = left_margin + tick * x_step
            self.create_text(
                x, top_margin + chart_h + 12,
                text=str(tick + 1),
                font=("Consolas", 8),
                fill=t["label_fg"],
            )

        def _draw_series(history: List[int], color: str) -> None:
            points = []
            for idx, val in enumerate(history):
                x = left_margin + idx * x_step
                y = top_margin + chart_h - val * y_scale
                points.extend([x, y])
            if len(points) >= 4:
                self.create_line(*points, fill=color, width=2, smooth=True)
            for idx, val in enumerate(history):
                x = left_margin + idx * x_step
                y = top_margin + chart_h - val * y_scale
                self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline=color)

        _draw_series(plant_history, t["chart_plant"])
        _draw_series(herbivore_history, t["chart_herbivore"])
        _draw_series(carnivore_history, t["chart_carnivore"])

        # Legend + stats box
        lx = left_margin + chart_w + 8
        ly = top_margin
        box_w = right_margin - 10
        box_h = 130
        self.create_rectangle(lx, ly, lx + box_w, ly + box_h, fill=t["legend_bg"], outline=t["legend_outline"])
        self.create_text(lx + 4, ly + 10, text="Legend", anchor="w", font=("Consolas", 8, "bold"), fill=t["label_fg"])

        for i, (label, color, hist) in enumerate([
            ("Plants", t["chart_plant"], plant_history),
            ("Herbivores", t["chart_herbivore"], herbivore_history),
            ("Carnivores", t["chart_carnivore"], carnivore_history),
        ]):
            row_y = ly + 26 + i * 18
            self.create_line(lx + 4, row_y, lx + 16, row_y, fill=color, width=2)
            self.create_text(lx + 20, row_y, text=label, anchor="w", font=("Consolas", 8), fill=color)

        # Min/Max/Avg block
        stats_y = ly + box_h + 8
        for label, hist in [
            ("P", plant_history), ("H", herbivore_history), ("C", carnivore_history)
        ]:
            if hist:
                mn, mx, av = min(hist), max(hist), sum(hist) / len(hist)
                self.create_text(
                    lx + 4, stats_y,
                    text=f"{label}: ↓{mn} ↑{mx} ~{av:.0f}",
                    anchor="w",
                    font=("Consolas", 7),
                    fill=t["label_fg"],
                )
                stats_y += 13

    def apply_theme(self, theme: "Theme") -> None:
        self.theme = theme
