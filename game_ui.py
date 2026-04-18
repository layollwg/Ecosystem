from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Dict, Optional

from dpi_aware import apply_windows_dpi_awareness
from ui_theme import Theme
from ui_config_panel import ConfigPanel
from ui_simulation_panel import SimulationPanel
from ui_result_panel import ResultPanel
from data_exporter import export_to_csv, export_to_json
import config as _cfg

_MIN_W = 900
_MIN_H = 680


class GameUI:
    """Main game window.

    Manages the full application lifecycle:
        Config Panel → Simulation Panel → Result Panel → (loop back)

    The simulation tick loop is driven by ``root.after()`` so the Tkinter
    event loop is never blocked.
    """

    def __init__(self, checkpoint_path: Optional[str] = None) -> None:
        apply_windows_dpi_awareness()
        self._root = tk.Tk()
        self._root.title("🌍 生态系统模拟器")
        self._root.minsize(_MIN_W, _MIN_H)
        self._theme = Theme(mode="nature")
        self._root.config(bg=self._theme["bg"])
        self._root.protocol("WM_DELETE_WINDOW", self._on_exit)

        # Content area — all panels live here
        self._content = tk.Frame(self._root, bg=self._theme["bg"])
        self._content.pack(fill="both", expand=True)

        # Simulation state
        self._eco: Optional[Any] = None          # Ecosystem instance
        self._total_ticks: int = 500
        self._after_id: Optional[str] = None
        self._sim_paused: bool = False
        self._last_params: Optional[Dict[str, Any]] = None
        self._checkpoint_path: Optional[str] = None
        self._algo: Optional[Any] = None
        self._ray_shutdown = None

        if checkpoint_path:
            self._load_checkpoint(checkpoint_path)

        self._show_config_panel()

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self._root.mainloop()

    # ── Panel helpers ─────────────────────────────────────────────────────────

    def _clear_content(self) -> None:
        """Cancel any pending tick and destroy all panel widgets."""
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None
        for child in self._content.winfo_children():
            child.destroy()

    def _show_config_panel(self) -> None:
        self._clear_content()
        self._sim_paused = False
        ConfigPanel(
            self._content,
            theme=self._theme,
            on_start=self._on_start_simulation,
            on_theme_change=self._on_theme_change,
        ).pack(fill="both", expand=True)

    def _on_theme_change(self, mode: str) -> None:
        """Switch the active palette and rebuild the config panel."""
        self._theme.set_mode(mode)
        self._root.config(bg=self._theme["bg"])
        self._content.config(bg=self._theme["bg"])
        self._show_config_panel()

    def _show_simulation_panel(self) -> None:
        self._clear_content()
        self._sim_paused = False
        eco = self._eco
        assert eco is not None
        self._sim_panel = SimulationPanel(
            self._content,
            theme=self._theme,
            ecosystem=eco,
            total_ticks=self._total_ticks,
            on_pause_toggle=self._on_pause_toggle,
            on_step=self._on_step,
            on_stop=self._on_stop_simulation,
            on_speed_change=self._on_speed_change,
        )
        self._sim_panel.pack(fill="both", expand=True)

    def _show_result_panel(self, reason: str) -> None:
        stats = self._eco.get_statistics() if self._eco is not None else {}
        self._clear_content()
        ResultPanel(
            self._content,
            theme=self._theme,
            stats=stats,
            reason=reason,
            on_back_to_config=self._show_config_panel,
            on_run_again=self._on_run_again,
            on_export_csv=self._on_export_csv,
            on_export_json=self._on_export_json,
            on_exit=self._on_exit,
        ).pack(fill="both", expand=True)

    # ── Simulation lifecycle ──────────────────────────────────────────────────

    def _on_start_simulation(self, params: Dict[str, Any]) -> None:
        """Called by ConfigPanel when the user clicks Start Simulation."""
        self._last_params = params

        # Load chosen preset into the global config module
        _cfg.load_preset(params.get("preset", "stable"))

        self._total_ticks = params.get("total_ticks", 500)

        # Import here to avoid a circular import at module load time
        from ecosystem import Ecosystem
        self._eco = Ecosystem(
            grid_size=params.get("grid_size", 20),
            num_plants=params.get("plants", 80),
            num_herbivores=params.get("herbivores", 30),
            num_carnivores=params.get("carnivores", 5),
            tick_delay=params.get("tick_delay", 0.10),
            theme=self._theme.mode,
        )

        self._show_simulation_panel()
        self._schedule_tick()

    def _on_run_again(self) -> None:
        """Re-run with the identical parameters from the last run."""
        if self._last_params is not None:
            self._on_start_simulation(self._last_params)
        else:
            self._show_config_panel()

    def _on_stop_simulation(self) -> None:
        """Stop the simulation and jump to the result panel."""
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None
        self._show_result_panel("模拟已由用户停止。")

    def _on_exit(self) -> None:
        """Close the application."""
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
        if self._ray_shutdown is not None:
            try:
                self._ray_shutdown()
            except Exception:
                pass
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    # ── Tick loop ──────────────────────────────────────────────────────────────

    def _schedule_tick(self) -> None:
        """Schedule the next tick via ``root.after()``."""
        if self._eco is None or self._sim_paused:
            return
        delay_ms = max(0, int(self._eco.tick_delay * 1000))
        self._after_id = self._root.after(delay_ms, self._run_one_tick)

    def _run_one_tick(self) -> None:
        """Execute a single simulation tick then update the display."""
        eco = self._eco
        if eco is None:
            return

        # Termination conditions
        if not eco.organisms:
            self._finish_simulation("所有生物已灭绝。")
            return
        if eco.tick_count >= self._total_ticks:
            self._finish_simulation("模拟完成。")
            return

        # Advance by one step
        eco.step(action_dict=self._build_inference_actions(eco))

        # Update the panel
        try:
            self._sim_panel.update_display(eco.get_display_data())
        except tk.TclError:
            # Panel was destroyed (user navigated away)
            return

        # Schedule next tick
        self._schedule_tick()

    def _finish_simulation(self, reason: str) -> None:
        """Called when the simulation ends naturally."""
        self._after_id = None
        try:
            self._sim_panel.set_complete()
            self._root.update_idletasks()
        except (tk.TclError, AttributeError):
            pass
        # Brief pause so the user sees the "complete" message
        self._root.after(800, lambda: self._show_result_panel(reason))

    # ── Simulation controls ────────────────────────────────────────────────────

    def _on_pause_toggle(self) -> None:
        self._sim_paused = not self._sim_paused
        try:
            self._sim_panel.set_paused(self._sim_paused)
        except (tk.TclError, AttributeError):
            pass
        if not self._sim_paused:
            # Resume the tick loop
            self._schedule_tick()

    def _on_step(self) -> None:
        """Execute exactly one simulation tick then remain paused (step-forward)."""
        if self._eco is None:
            return

        # Ensure the simulation is paused before stepping
        if not self._sim_paused:
            self._sim_paused = True
            # Cancel any pending auto-tick
            if self._after_id is not None:
                self._root.after_cancel(self._after_id)
                self._after_id = None
            try:
                self._sim_panel.set_paused(True)
            except (tk.TclError, AttributeError):
                pass

        eco = self._eco

        # Check termination conditions before stepping
        if not eco.organisms:
            self._finish_simulation("所有生物已灭绝。")
            return
        if eco.tick_count >= self._total_ticks:
            self._finish_simulation("模拟完成。")
            return

        # Advance exactly one tick
        eco.step(action_dict=self._build_inference_actions(eco))

        try:
            self._sim_panel.update_display(eco.get_display_data())
        except tk.TclError:
            pass
        # Do NOT schedule the next tick — stay paused.

    def _on_speed_change(self, delay: float) -> None:
        if self._eco is not None:
            self._eco.tick_delay = delay

    def _load_checkpoint(self, checkpoint_path: str) -> None:
        resolved = os.path.abspath(os.path.expanduser(checkpoint_path))
        if not os.path.exists(resolved):
            messagebox.showerror("模型加载失败", f"Checkpoint 不存在：\n{resolved}")
            return
        try:
            from ray import init as ray_init
            from ray import shutdown as ray_shutdown
            from ray.rllib.algorithms.ppo import PPO
        except ImportError as exc:
            messagebox.showerror(
                "模型加载失败",
                "当前环境未安装 Ray RLlib。\n请先执行：pip install -r requirement.txt",
            )
            raise RuntimeError("Ray RLlib is required for --load-checkpoint") from exc

        ray_init(ignore_reinit_error=True, include_dashboard=False, log_to_driver=False)
        self._ray_shutdown = ray_shutdown
        try:
            self._algo = PPO.from_checkpoint(resolved)
            self._checkpoint_path = resolved
        except Exception as exc:
            messagebox.showerror("模型加载失败", f"无法恢复 checkpoint：\n{resolved}\n\n{exc}")
            self._algo = None

    def _build_inference_actions(self, eco: Any) -> Optional[Dict[int, int]]:
        if self._algo is None:
            return None
        inference_batch = eco.get_inference_batch()
        action_dict: Dict[int, int] = {}
        try:
            for public_agent_id, payload in inference_batch.items():
                policy_id = payload["policy_id"]
                obs = payload["observation"]
                action = self._algo.compute_single_action(obs, policy_id=policy_id, explore=False)
                if isinstance(action, tuple):
                    action = action[0]
                if not isinstance(action, (int, float)):
                    raise TypeError(f"unexpected action type: {type(action).__name__}, value={action!r}")
                action_dict[public_agent_id] = int(action)
        except Exception as exc:
            messagebox.showerror(
                "模型推理失败",
                "推理失败，已回退为默认行为。\n"
                "请检查 checkpoint 与当前环境观测/策略映射是否一致。\n\n"
                f"{type(exc).__name__}: {exc}",
            )
            self._algo = None
            return None
        return action_dict

    # ── Export helpers ─────────────────────────────────────────────────────────

    def _on_export_csv(self) -> None:
        if self._eco is None:
            return
        fname = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            title="导出种群数据为 CSV",
        )
        if not fname:
            return
        history = {
            "plants":     list(self._eco.plant_history),
            "herbivores": list(self._eco.herbivore_history),
            "carnivores": list(self._eco.carnivore_history),
        }
        try:
            export_to_csv(history, fname)
            messagebox.showinfo("导出成功", f"CSV 已保存到：\n{os.path.basename(fname)}")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))

    def _on_export_json(self) -> None:
        if self._eco is None:
            return
        fname = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            title="导出模拟数据为 JSON",
        )
        if not fname:
            return
        history = {
            "plants":     list(self._eco.plant_history),
            "herbivores": list(self._eco.herbivore_history),
            "carnivores": list(self._eco.carnivore_history),
        }
        metadata = {
            "grid_size":          self._eco.grid_size,
            "initial_plants":     self._eco._init_plants,
            "initial_herbivores": self._eco._init_herbivores,
            "initial_carnivores": self._eco._init_carnivores,
            "preset":             _cfg.active_preset_name(),
        }
        try:
            export_to_json(history, metadata, fname)
            messagebox.showinfo("导出成功", f"JSON 已保存到：\n{os.path.basename(fname)}")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))
