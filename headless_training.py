from __future__ import annotations

import argparse
import random
from statistics import mean
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Optional

import config
from ecosystem_core import EcosystemCore, RewardConfig
from organisms import Animal, Carnivore, Herbivore

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
    freeze_herbivore: bool = False
    freeze_carnivore: bool = False


CURRICULUM_LEVELS = (
    CurriculumLevel("level1_collect_and_survive", plants=120, herbivores=40, carnivores=0),
    CurriculumLevel(
        "level2_asymmetric_tracking",
        plants=120,
        herbivores=40,
        carnivores=12,
        freeze_herbivore=True,
    ),
    CurriculumLevel(
        "level3_self_play_coevolution",
        plants=140,
        herbivores=45,
        carnivores=15,
    ),
)


def _random_action() -> int:
    return random.choice(EcosystemCore.ACTIONS)


def _build_action_dict(
    env: EcosystemCore,
    level: CurriculumLevel,
) -> Dict[int, int]:
    action_dict: Dict[int, int] = {}
    for organism in env.organisms:
        if not organism.alive or not isinstance(organism, Animal):
            continue

        if level.freeze_herbivore and isinstance(organism, Herbivore):
            continue
        if level.freeze_carnivore and isinstance(organism, Carnivore):
            continue

        action_dict[organism.agent_id] = _random_action()
    return action_dict


def _build_reward_config(args: argparse.Namespace) -> Optional[RewardConfig]:
    overrides: Dict[str, Any] = {}
    if args.living_penalty is not None:
        overrides["living_penalty"] = args.living_penalty
    if args.energy_delta_scale is not None:
        overrides["energy_delta_scale"] = args.energy_delta_scale
    if args.reproduction_reward is not None:
        overrides["reproduce_success"] = args.reproduction_reward
    if args.collision_penalty is not None:
        overrides["invalid_collision"] = args.collision_penalty
    if args.death_penalty_starvation is not None:
        overrides["death_penalty_starvation"] = args.death_penalty_starvation
    if args.death_penalty_predation is not None:
        overrides["death_penalty_predation"] = args.death_penalty_predation
    if args.death_penalty_old_age is not None:
        overrides["death_penalty_old_age"] = args.death_penalty_old_age
    if args.reward_breakdown_agents:
        overrides["include_agent_breakdown"] = True

    if not overrides:
        return None
    # args.api_version is validated by argparse choices in add_headless_args.
    base = RewardConfig.for_api_version(args.api_version)
    return replace(base, **overrides)


def run_curriculum(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    config.load_preset(args.preset)
    preset_label = _PRESET_LABELS.get(args.preset, args.preset)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    observation_width = args.observation_radius * 2 + 1
    reward_config = _build_reward_config(args)
    print(
        f"[无界面] 模式=课程训练 预设={preset_label} 网格={args.grid_size} 回合={args.episodes} 步数={args.ticks} "
        f"API={args.api_version} 观测窗口={observation_width}x{observation_width}"
    )

    for level in CURRICULUM_LEVELS:
        print(f"[无界面] 开始 {level.name}")

        env = EcosystemCore(
            grid_size=args.grid_size,
            num_plants=level.plants,
            num_herbivores=level.herbivores,
            num_carnivores=level.carnivores,
            tick_delay=0.0,
            observation_radius=args.observation_radius,
            api_version=args.api_version,
            reward_config=reward_config,
        )

        level_rewards: list[float] = []

        for episode in range(1, args.episodes + 1):
            env.reset()
            cumulative_reward = 0.0

            for _ in range(args.ticks):
                action_dict = _build_action_dict(env, level)
                _obs, rewards, dones, info = env.step(action_dict)
                cumulative_reward += sum(rewards.values())
                if dones.get("__all__"):
                    break

            level_rewards.append(cumulative_reward)

            if episode % args.log_interval == 0:
                print(
                    f"[无界面] {level.name} 回合={episode} "
                    f"奖励={cumulative_reward:.2f} "
                    f"平均奖励={(mean(level_rewards) if level_rewards else 0.0):.2f} "
                    f"存活体数={len(info.get('agent_species', {}))}"
                )
                if args.api_version == "v2":
                    reward_parts = info.get("reward_breakdown_totals", {})
                    death_parts = info.get("death_reasons", {})
                    print(f"[无界面] 奖励分解={reward_parts} 死亡原因={death_parts}")

            if args.checkpoint_every > 0 and episode % args.checkpoint_every == 0:
                ckpt_path = checkpoint_dir / f"{level.name}_ep{episode}.json"
                env.save_checkpoint(
                    str(ckpt_path),
                    metadata={
                        "level": level.name,
                        "episode": episode,
                        "mean_reward": mean(level_rewards) if level_rewards else 0.0,
                        "preset": args.preset,
                        "grid_size": args.grid_size,
                    },
                )

        print(
            f"[无界面] 完成 {level.name} "
            f"回合数={args.episodes} 平均奖励={(mean(level_rewards) if level_rewards else 0.0):.2f}"
        )


def add_headless_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("无界面模式参数")
    group.add_argument("--api-version", default="v1", choices=("v1", "v2"))
    group.add_argument("--preset", default="stable", choices=list(config.PRESETS.keys()))
    group.add_argument("--grid-size", type=int, default=25)
    group.add_argument("--ticks", type=int, default=300)
    group.add_argument("--episodes", type=int, default=10)
    group.add_argument("--seed", type=int, default=42)
    group.add_argument("--observation-radius", type=int, default=2)
    group.add_argument("--log-interval", type=int, default=1)
    group.add_argument("--checkpoint-every", type=int, default=5)
    group.add_argument("--checkpoint-dir", default="./checkpoints")
    group.add_argument("--living-penalty", type=float, default=None)
    group.add_argument("--energy-delta-scale", type=float, default=None)
    group.add_argument("--reproduction-reward", type=float, default=None)
    group.add_argument("--collision-penalty", type=float, default=None)
    group.add_argument("--death-penalty-starvation", type=float, default=None)
    group.add_argument("--death-penalty-predation", type=float, default=None)
    group.add_argument("--death-penalty-old-age", type=float, default=None)
    group.add_argument("--reward-breakdown-agents", action="store_true")
