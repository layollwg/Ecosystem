from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Tuple

import config
from ecosystem_core import EcosystemCore
from ecosystem_env import EcosystemEnv
from organisms import Animal

try:
    from ray import init as ray_init
    from ray import shutdown as ray_shutdown
    from ray.rllib.algorithms.ppo import PPOConfig
    from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
    from ray.tune.registry import register_env
except ImportError:  # pragma: no cover - runtime dependency gate
    ray_init = None
    ray_shutdown = None
    PPOConfig = None
    ParallelPettingZooEnv = None
    register_env = None

_PRESET_LABELS = {
    "stable": "稳定",
    "balanced": "均衡",
    "intense": "激烈",
}


@dataclass(frozen=True)
class CurriculumLevel:
    name: str
    plants: int
    herbivores: int
    carnivores: int


CURRICULUM_LEVELS = (
    CurriculumLevel("level1_collect_and_survive", plants=120, herbivores=40, carnivores=0),
    CurriculumLevel("level2_asymmetric_tracking", plants=120, herbivores=40, carnivores=12),
    CurriculumLevel("level3_self_play_coevolution", plants=140, herbivores=45, carnivores=15),
)


def _require_rllib() -> None:
    if PPOConfig is not None:
        return
    raise RuntimeError(
        "Headless training now requires Ray RLlib. "
        "Install with: pip install \"ray[rllib]==2.55.0\" pettingzoo==1.25.0 gymnasium==1.2.3"
    )


def _random_legal_action(mask: List[int]) -> int:
    legal = [idx for idx, enabled in enumerate(mask) if int(enabled) == 1]
    return random.choice(legal) if legal else EcosystemEnv.ACTION_STAY


def _env_creator(env_config: Dict[str, int]) -> ParallelPettingZooEnv:
    env = EcosystemEnv(
        grid_size=env_config["grid_size"],
        max_rabbits=env_config["max_rabbits"],
        max_foxes=env_config["max_foxes"],
        initial_rabbits=env_config["initial_rabbits"],
        initial_foxes=env_config["initial_foxes"],
        initial_plants=env_config["initial_plants"],
        max_steps=env_config["max_steps"],
        render_mode=None,
    )
    return ParallelPettingZooEnv(env)


def _build_rllib_config(env_name: str, args: argparse.Namespace):
    sample_env = EcosystemEnv(
        grid_size=args.grid_size,
        initial_rabbits=1,
        initial_foxes=1,
        initial_plants=1,
        max_steps=args.ticks,
    )
    rabbit_agent = "rabbit_0"
    fox_agent = "fox_0"
    policies = {
        "rabbit_policy": (
            None,
            sample_env.observation_space(rabbit_agent),
            sample_env.action_space(rabbit_agent),
            {},
        ),
        "fox_policy": (
            None,
            sample_env.observation_space(fox_agent),
            sample_env.action_space(fox_agent),
            {},
        ),
    }

    def policy_mapping_fn(agent_id: str, *_args, **_kwargs) -> str:
        if agent_id.startswith("rabbit_"):
            return "rabbit_policy"
        return "fox_policy"

    return (
        PPOConfig()
        .framework(args.framework)
        .environment(env=env_name, disable_env_checking=True)
        .resources(num_gpus=args.num_gpus)
        .env_runners(num_env_runners=args.num_env_runners)
        .training(
            train_batch_size=args.train_batch_size,
            lr=args.learning_rate,
            gamma=args.gamma,
            model={"fcnet_hiddens": [256, 256]},
        )
        .multi_agent(
            policies=policies,
            policy_mapping_fn=policy_mapping_fn,
            policies_to_train=["rabbit_policy", "fox_policy"],
        )
    )


def _run_rllib_curriculum(args: argparse.Namespace) -> None:
    _require_rllib()
    assert ray_init is not None
    assert ray_shutdown is not None
    assert register_env is not None

    random.seed(args.seed)
    config.load_preset(args.preset)
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    preset_label = _PRESET_LABELS.get(args.preset, args.preset)

    print(
        f"[无界面-RLlib] 预设={preset_label} 网格={args.grid_size} 回合={args.episodes} "
        f"每回合最大步数={args.ticks} 框架={args.framework}"
    )

    ray_init(ignore_reinit_error=True, include_dashboard=False, log_to_driver=False)
    try:
        for level in CURRICULUM_LEVELS:
            env_name = f"ecosystem_{level.name}"
            max_rabbits = max(level.herbivores * 10, 500)
            max_foxes = max(level.carnivores * 10, 100)
            env_config = {
                "grid_size": args.grid_size,
                "max_rabbits": max_rabbits,
                "max_foxes": max_foxes,
                "initial_rabbits": level.herbivores,
                "initial_foxes": level.carnivores,
                "initial_plants": level.plants,
                "max_steps": args.ticks,
            }
            register_env(env_name, lambda cfg, _ec=env_config: _env_creator(_ec))

            algo = _build_rllib_config(env_name, args).build()
            print(f"[无界面-RLlib] 开始 {level.name}")
            episode_returns: List[float] = []

            for episode in range(1, args.episodes + 1):
                result = algo.train()
                reward_mean = float(result.get("env_runners", {}).get("episode_return_mean", 0.0))
                episode_returns.append(reward_mean)

                if episode % args.log_interval == 0:
                    print(
                        f"[无界面-RLlib] {level.name} 轮次={episode} "
                        f"当前均值回报={reward_mean:.2f} "
                        f"累计均值回报={mean(episode_returns):.2f}"
                    )

                if args.checkpoint_every > 0 and episode % args.checkpoint_every == 0:
                    ckpt_path = Path(algo.save(checkpoint_dir / f"{level.name}_ep{episode}"))
                    print(f"[无界面-RLlib] 保存检查点: {ckpt_path}")

            final_ckpt = Path(algo.save(checkpoint_dir / f"{level.name}_final"))
            print(
                f"[无界面-RLlib] 完成 {level.name} "
                f"轮次={args.episodes} 均值回报={mean(episode_returns) if episode_returns else 0.0:.2f} "
                f"最终检查点={final_ckpt}"
            )
            algo.stop()
    finally:
        ray_shutdown()


def _calc_balance(plants: int, herbivores: int, carnivores: int) -> float:
    counts = [value for value in (plants, herbivores, carnivores) if value > 0]
    if not counts:
        return 0.0
    if len(counts) == 1:
        return 15.0
    total = sum(counts)
    import math

    proportions = [value / total for value in counts]
    diversity = -sum(value * math.log(value) for value in proportions)
    max_diversity = math.log(len(counts))
    return (diversity / max_diversity * 100.0) if max_diversity > 0 else 100.0


def _simulate_core(grid_size: int, plants: int, herbivores: int, carnivores: int, ticks: int) -> Dict[str, float]:
    env = EcosystemCore(
        grid_size=grid_size,
        num_plants=plants,
        num_herbivores=herbivores,
        num_carnivores=carnivores,
        tick_delay=0.0,
    )
    env.reset()
    for _ in range(ticks):
        action_dict: Dict[int, int] = {}
        for organism in env.organisms:
            if not organism.alive or not isinstance(organism, Animal):
                continue
            action_dict[organism.agent_id] = random.choice(EcosystemCore.ACTIONS)
        _obs, _rewards, dones, _info = env.step(action_dict)
        if dones.get("__all__"):
            break
    stats = env.get_statistics()
    return {
        "plant_final": float(stats["plant_count"]),
        "herb_final": float(stats["herbivore_count"]),
        "carn_final": float(stats["carnivore_count"]),
        "plant_mean": float(mean(env.plant_history) if env.plant_history else 0.0),
        "herb_mean": float(mean(env.herbivore_history) if env.herbivore_history else 0.0),
        "carn_mean": float(mean(env.carnivore_history) if env.carnivore_history else 0.0),
        "balance_mean": float(
            mean(
                _calc_balance(p, h, c)
                for p, h, c in zip(env.plant_history, env.herbivore_history, env.carnivore_history)
            )
            if env.plant_history
            else 0.0
        ),
        "avg_age": float(env.get_display_data()["avg_age"]),
    }


def _simulate_parallel(grid_size: int, plants: int, herbivores: int, carnivores: int, ticks: int) -> Dict[str, float]:
    env = EcosystemEnv(
        grid_size=grid_size,
        initial_plants=plants,
        initial_rabbits=herbivores,
        initial_foxes=carnivores,
        max_steps=ticks,
    )
    obs, _ = env.reset()
    plant_history: List[int] = [len(env.plants)]
    herb_history: List[int] = [sum(1 for aid in env.agents if aid.startswith("rabbit_"))]
    carn_history: List[int] = [sum(1 for aid in env.agents if aid.startswith("fox_"))]
    age_snapshots: List[float] = []

    for _ in range(ticks):
        actions: Dict[str, int] = {}
        for agent_id in env.agents:
            action_mask = obs.get(agent_id, {}).get("action_mask")
            if action_mask is None:
                actions[agent_id] = EcosystemEnv.ACTION_STAY
                continue
            actions[agent_id] = _random_legal_action(list(action_mask))
        obs, _rewards, terminations, truncations, _infos = env.step(actions)
        if env.agents:
            age_snapshots.append(mean(env.agent_to_object[aid].age for aid in env.agents))
        plant_history.append(len(env.plants))
        herb_history.append(sum(1 for aid in env.agents if aid.startswith("rabbit_")))
        carn_history.append(sum(1 for aid in env.agents if aid.startswith("fox_")))
        if all(terminations.values()) or all(truncations.values()):
            break

    return {
        "plant_final": float(plant_history[-1] if plant_history else 0.0),
        "herb_final": float(herb_history[-1] if herb_history else 0.0),
        "carn_final": float(carn_history[-1] if carn_history else 0.0),
        "plant_mean": float(mean(plant_history) if plant_history else 0.0),
        "herb_mean": float(mean(herb_history) if herb_history else 0.0),
        "carn_mean": float(mean(carn_history) if carn_history else 0.0),
        "balance_mean": float(
            mean(_calc_balance(p, h, c) for p, h, c in zip(plant_history, herb_history, carn_history))
            if plant_history
            else 0.0
        ),
        "avg_age": float(mean(age_snapshots) if age_snapshots else 0.0),
    }


def _aggregate(samples: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    keys = sorted(samples[0].keys())
    output: Dict[str, Dict[str, float]] = {}
    for key in keys:
        values = [sample[key] for sample in samples]
        output[key] = {
            "mean": float(mean(values)),
            "std": float(pstdev(values)) if len(values) > 1 else 0.0,
        }
    return output


def _run_statistical_alignment(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    config.load_preset(args.preset)
    level = CURRICULUM_LEVELS[-1]
    print(
        f"[对齐验证] 运行次数={args.alignment_runs} "
        f"网格={args.grid_size} ticks={args.ticks} "
        f"(初始: plants={level.plants}, herb={level.herbivores}, carn={level.carnivores})"
    )

    core_samples = []
    parallel_samples = []
    for run_idx in range(1, args.alignment_runs + 1):
        core = _simulate_core(
            args.grid_size,
            level.plants,
            level.herbivores,
            level.carnivores,
            args.ticks,
        )
        parallel = _simulate_parallel(
            args.grid_size,
            level.plants,
            level.herbivores,
            level.carnivores,
            args.ticks,
        )
        core_samples.append(core)
        parallel_samples.append(parallel)
        print(f"[对齐验证] run={run_idx} core={core} parallel={parallel}")

    core_agg = _aggregate(core_samples)
    parallel_agg = _aggregate(parallel_samples)
    comparison: Dict[str, Dict[str, float]] = {}
    for metric, c_stats in core_agg.items():
        p_stats = parallel_agg[metric]
        std_guard = max(c_stats["std"], p_stats["std"], 1e-6)
        comparison[metric] = {
            "core_mean": c_stats["mean"],
            "parallel_mean": p_stats["mean"],
            "abs_delta": abs(c_stats["mean"] - p_stats["mean"]),
            "delta_over_max_std": abs(c_stats["mean"] - p_stats["mean"]) / std_guard,
        }

    report = {
        "runs": args.alignment_runs,
        "preset": args.preset,
        "grid_size": args.grid_size,
        "ticks": args.ticks,
        "core": core_agg,
        "parallel": parallel_agg,
        "comparison": comparison,
    }
    report_path = Path(args.checkpoint_dir) / "statistical_alignment_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[对齐验证] 报告已写入: {report_path}")


def run_curriculum(args: argparse.Namespace) -> None:
    if args.validate_statistics:
        _run_statistical_alignment(args)
        return
    _run_rllib_curriculum(args)


def add_headless_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("无界面模式参数")
    group.add_argument("--preset", default="stable", choices=list(config.PRESETS.keys()))
    group.add_argument("--grid-size", type=int, default=25)
    group.add_argument("--ticks", type=int, default=300)
    group.add_argument("--episodes", type=int, default=10)
    group.add_argument("--seed", type=int, default=42)
    group.add_argument("--log-interval", type=int, default=1)
    group.add_argument("--checkpoint-every", type=int, default=5)
    group.add_argument("--checkpoint-dir", default="./checkpoints")
    group.add_argument("--framework", default="torch", choices=("torch",))
    group.add_argument("--num-env-runners", type=int, default=0)
    group.add_argument("--num-gpus", type=float, default=0.0)
    group.add_argument("--train-batch-size", type=int, default=4000)
    group.add_argument("--learning-rate", type=float, default=3e-4)
    group.add_argument("--gamma", type=float, default=0.99)
    group.add_argument("--validate-statistics", action="store_true")
    group.add_argument("--alignment-runs", type=int, default=10)
