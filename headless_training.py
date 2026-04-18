from __future__ import annotations

import argparse
import random
from statistics import mean
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import config
from ecosystem_core import EcosystemCore
from organisms import Animal, Carnivore, Herbivore


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


def run_curriculum(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    config.load_preset(args.preset)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    print(f"[无界面] 模式=课程训练 预设={args.preset} 网格={args.grid_size} 回合={args.episodes} 步数={args.ticks}")

    for level in CURRICULUM_LEVELS:
        print(f"[无界面] 开始 {level.name}")

        env = EcosystemCore(
            grid_size=args.grid_size,
            num_plants=level.plants,
            num_herbivores=level.herbivores,
            num_carnivores=level.carnivores,
            tick_delay=0.0,
            observation_radius=args.observation_radius,
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
    group.add_argument("--preset", default="stable", choices=list(config.PRESETS.keys()))
    group.add_argument("--grid-size", type=int, default=25)
    group.add_argument("--ticks", type=int, default=300)
    group.add_argument("--episodes", type=int, default=10)
    group.add_argument("--seed", type=int, default=42)
    group.add_argument("--observation-radius", type=int, default=2)
    group.add_argument("--log-interval", type=int, default=1)
    group.add_argument("--checkpoint-every", type=int, default=5)
    group.add_argument("--checkpoint-dir", default="./checkpoints")
