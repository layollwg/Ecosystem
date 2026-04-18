from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

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
    return random.choice(list(EcosystemCore.ACTIONS))


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


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def run_curriculum(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    config.load_preset(args.preset)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    print(f"[headless] mode=curriculum preset={args.preset} grid={args.grid_size} episodes={args.episodes} ticks={args.ticks}")

    for level in CURRICULUM_LEVELS:
        print(f"[headless] start {level.name}")

        env = EcosystemCore(
            grid_size=args.grid_size,
            num_plants=level.plants,
            num_herbivores=level.herbivores,
            num_carnivores=level.carnivores,
            tick_delay=0.0,
            observation_radius=args.observation_radius,
        )

        level_rewards: List[float] = []

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
                    f"[headless] {level.name} episode={episode} "
                    f"reward={cumulative_reward:.2f} "
                    f"mean_reward={_mean(level_rewards):.2f} "
                    f"alive={info.get('agent_species', {}) and len(info.get('agent_species', {})) or 0}"
                )

            if args.checkpoint_every > 0 and episode % args.checkpoint_every == 0:
                ckpt_path = checkpoint_dir / f"{level.name}_ep{episode}.json"
                env.save_checkpoint(
                    str(ckpt_path),
                    metadata={
                        "level": level.name,
                        "episode": episode,
                        "mean_reward": _mean(level_rewards),
                        "preset": args.preset,
                        "grid_size": args.grid_size,
                    },
                )

        print(
            f"[headless] done {level.name} "
            f"episodes={args.episodes} mean_reward={_mean(level_rewards):.2f}"
        )


def add_headless_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", default="stable", choices=list(config.PRESETS.keys()))
    parser.add_argument("--grid-size", type=int, default=25)
    parser.add_argument("--ticks", type=int, default=300)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--observation-radius", type=int, default=2)
    parser.add_argument("--log-interval", type=int, default=1)
    parser.add_argument("--checkpoint-every", type=int, default=5)
    parser.add_argument("--checkpoint-dir", default="./checkpoints")
