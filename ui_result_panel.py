from __future__ import annotations

import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ui_theme import Theme

from ui_widgets import EnhancedChart
from data_exporter import export_to_csv, export_to_json

_UI_FONT = "Arial"
_MONO_FONT = "Courier New"


class ResultPanel(tk.Frame):
    """Post-simulation results panel.

    Displays final statistics, a population history chart, export buttons,
    and navigation options (Back to Config / Run Again / Exit).
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme: "Theme",
        stats: Dict[str, Any],
        reason: str,
        on_back_to_config: Callable[[], None],
        on_run_again: Callable[[], None],
        on_export_csv: Callable[[], None],
        on_export_json: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._stats = stats
        self._reason = reason
        self._on_back = on_back_to_config
        self._on_run_again = on_run_again
        self._on_export_csv = on_export_csv
        self._on_export_json = on_export_json
        self._on_exit = on_exit
        self._build()

    # ── Build ───────────────────────────────────────────────────────────────────

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
        stats = self._stats

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(parent, bg=t.get("header_bg", t["bg"]))
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="🌍  生态系统模拟器——模拟结束",
            font=(_UI_FONT, 18, "bold"),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_accent", t["fg"]),
            pady=14,
        ).pack()
        tk.Label(
            hdr,
            text=self._reason,
            font=(_UI_FONT, 11),
            bg=t.get("header_bg", t["bg"]),
            fg=t.get("fg_secondary", t["fg"]),
            pady=4,
        ).pack()
        tk.Frame(parent, bg=t.get("border_glow", t["border"]), height=2).pack(fill="x")

        body = tk.Frame(parent, bg=t["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=12)

        left = tk.Frame(body, bg=t["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(body, bg=t["bg"])
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # ── Final statistics ──────────────────────────────────────────────────
        stat_card = self._card(left, "📊  最终统计")
        self._build_final_stats(stat_card, stats)

        # ── Export ────────────────────────────────────────────────────────────
        exp_card = self._card(left, "📥  数据导出")
        exp_row = tk.Frame(exp_card, bg=t["card_bg"])
        exp_row.pack(fill="x", pady=4)
        for label, cmd in [
            ("📥 导出 CSV",  self._on_export_csv),
            ("📋 导出 JSON", self._on_export_json),
        ]:
            tk.Button(
                exp_row, text=label,
                font=(_UI_FONT, 10),
                bg=t["button_bg"], fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=10, pady=5,
                cursor="hand2",
                command=cmd,
            ).pack(side="left", padx=4, pady=2)

        # ── Population chart ─────────────────────────────────────────────────
        chart_card = self._card(right, "📈  种群历史")
        chart = EnhancedChart(
            chart_card, self._theme,
            width=420, height=200,
            bg=t["chart_bg"],
        )
        chart.pack(padx=4, pady=4)
        chart.update_idletasks()
        chart.draw(
            stats.get("plant_history", []),
            stats.get("herbivore_history", []),
            stats.get("carnivore_history", []),
        )

        # ── Balance indicator ─────────────────────────────────────────────────
        bal_card = self._card(right, "⚖️  生态平衡")
        self._build_balance(bal_card, stats)

        # ── Navigation buttons ────────────────────────────────────────────────
        nav_card = self._card(parent, "🔄  接下来你想做什么？")
        nav_card.pack(fill="x", padx=24, pady=(8, 16))
        nav_row = tk.Frame(nav_card, bg=t["card_bg"])
        nav_row.pack(fill="x", pady=4)

        for label, cmd, is_primary in [
            ("◀  返回配置页",         self._on_back,       False),
            ("🔄  重新运行（同参数）", self._on_run_again,  True),
            ("❌  退出",               self._on_exit,       False),
        ]:
            tk.Button(
                nav_row, text=label,
                font=(_UI_FONT, 11, "bold" if is_primary else "normal"),
                bg=t["button_bg"] if is_primary else t["panel_bg"],
                fg=t["button_fg"] if is_primary else t["fg"],
                activebackground=t["button_active_bg"],
                relief="flat", padx=14, pady=7,
                cursor="hand2",
                command=cmd,
            ).pack(side="left", padx=6, pady=4, expand=True, fill="x")

    # ── Statistics helpers ────────────────────────────────────────────────────

    def _build_final_stats(self, parent: tk.Widget, stats: Dict[str, Any]) -> None:
        t = self._theme

        def _row(label: str, value: str, fg: Optional[str] = None) -> None:
            row = tk.Frame(parent, bg=t["card_bg"])
            row.pack(fill="x", pady=2)
            tk.Label(
                row, text=label,
                font=(_UI_FONT, 10),
                bg=t["card_bg"], fg=t["label_fg"],
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row, text=value,
                font=(_MONO_FONT, 10, "bold"),
                bg=t["card_bg"],
                fg=fg or t["fg"],
                anchor="e",
            ).pack(side="right")

        total_ticks = stats.get("tick", 0)
        _row("已运行 Tick 数", str(total_ticks))
        _row("网格尺寸",
             f"{stats.get('grid_size', '?')} × {stats.get('grid_size', '?')}")

        sep = tk.Frame(parent, bg=t.get("border", "#333"), height=1)
        sep.pack(fill="x", pady=4)

        for label, key, init_key, fg_key in [
            ("🌿 植物",     "plant_count",    "init_plants",     "text_plant"),
            ("🦌 草食动物", "herbivore_count", "init_herbivores", "text_herbivore"),
            ("🦁 肉食动物", "carnivore_count", "init_carnivores", "text_carnivore"),
        ]:
            final = stats.get(key, 0)
            initial = stats.get(init_key, "?")
            _row(label, f"{final} （初始：{initial}）", fg=t.get(fg_key, t["fg"]))

        # Survival summary
        if total_ticks > 0:
            sep2 = tk.Frame(parent, bg=t.get("border", "#333"), height=1)
            sep2.pack(fill="x", pady=4)
            survived = sum(
                1
                for k in ("plant_count", "herbivore_count", "carnivore_count")
                if stats.get(k, 0) > 0
            )
            status_text = (
                "✅ 三类生物全部存活！"
                if survived == 3
                else f"⚠️ 仅有 {survived}/3 类生物存活"
            )
            status_color = (
                t.get("stat_positive", t["fg"])
                if survived == 3
                else t.get("stat_negative", t["fg"])
            )
            tk.Label(
                parent, text=status_text,
                font=(_UI_FONT, 11, "bold"),
                bg=t["card_bg"], fg=status_color,
            ).pack(anchor="w", pady=(2, 4))

    def _build_balance(self, parent: tk.Widget, stats: Dict[str, Any]) -> None:
        t = self._theme
        p = stats.get("plant_count", 0)
        h = stats.get("herbivore_count", 0)
        c = stats.get("carnivore_count", 0)
        balance = _calc_balance(p, h, c)

        row = tk.Frame(parent, bg=t["card_bg"])
        row.pack(fill="x", pady=2)
        tk.Label(
            row, text="平衡指数：",
            font=(_UI_FONT, 10),
            bg=t["card_bg"], fg=t["label_fg"],
        ).pack(side="left")
        score_color = (
            t.get("stat_positive", t["fg"]) if balance >= 60
            else t.get("stat_negative", t["fg"])
        )
        quality = "优秀" if balance >= 80 else "良好" if balance >= 60 else "较差"
        tk.Label(
            row, text=f"{balance}/100  ({quality})",
            font=(_MONO_FONT, 10, "bold"),
            bg=t["card_bg"], fg=score_color,
        ).pack(side="right")

        bar_bg = tk.Frame(parent, bg=t.get("accent_bg", t["panel_bg"]), height=10)
        bar_bg.pack(fill="x", pady=(2, 4))
        fill = tk.Frame(bar_bg, bg=score_color, height=10)
        fill.place(relx=0, rely=0, relwidth=balance / 100, relheight=1.0)

    # ── Card helper ───────────────────────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────────────────────────

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
