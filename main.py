from __future__ import annotations

import argparse
from ecosystem import Ecosystem
import config


def prompt_preset(args: argparse.Namespace) -> str:
    """Return the chosen preset name, prompting interactively when needed."""
    if args.preset is not None:
        return args.preset

    preset_list = list(config.PRESETS.items())
    print("\nChoose a simulation preset:")
    for i, (name, data) in enumerate(preset_list, 1):
        print(f"  {i}) {name} — {data['description']}")
    print()

    while True:
        choice = input(
            f"Enter preset name or number (default: stable): "
        ).strip()
        if not choice:
            return "stable"
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(preset_list):
                return preset_list[idx][0]
        if choice in config.PRESETS:
            return choice
        print(
            f"Invalid choice. Enter a name "
            f"({', '.join(config.PRESETS.keys())}) or a number 1–{len(preset_list)}."
        )


def prompt_positive_int(prompt: str) -> int:
    while True:
        try:
            value = int(input(prompt))
            if value <= 0:
                raise ValueError
            return value
        except ValueError:
            print("Please enter a positive integer.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the ecosystem simulation with optional command-line configuration."
    )
    parser.add_argument("--grid-size", type=int, help="Grid size for the simulation")
    parser.add_argument("--plants", type=int, help="Initial number of plants")
    parser.add_argument("--herbivores", type=int, help="Initial number of herbivores")
    parser.add_argument("--carnivores", type=int, help="Initial number of carnivores")
    parser.add_argument("--ticks", type=int, help="Number of ticks to simulate")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay in seconds between ticks")
    parser.add_argument(
        "--preset",
        type=str,
        choices=list(config.PRESETS.keys()),
        help="Simulation preset (stable / balanced / intense)",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Run the simulation in manual step-by-step mode",
    )
    return parser.parse_args()


def prompt_non_negative_float(prompt: str) -> float:
    while True:
        try:
            value = float(input(prompt))
            if value < 0:
                raise ValueError
            return value
        except ValueError:
            print("Please enter a non-negative number.")


def collect_simulation_parameters(args: argparse.Namespace) -> tuple[int, int, int, int, int, float, bool]:
    preset_name = prompt_preset(args)
    config.load_preset(preset_name)
    print(f"\nLoaded preset '{preset_name}': {config.PRESETS[preset_name]['description']}")
    print(config.energy_flow_summary())
    print()

    grid_size = args.grid_size if args.grid_size is not None else prompt_positive_int(
        "Enter grid size (e.g., 20 for a 20x20 grid): "
    )
    num_plants = args.plants if args.plants is not None else prompt_positive_int(
        "Enter initial number of plants: "
    )
    num_herbivores = args.herbivores if args.herbivores is not None else prompt_positive_int(
        "Enter initial number of herbivores: "
    )
    num_carnivores = args.carnivores if args.carnivores is not None else prompt_positive_int(
        "Enter initial number of carnivores: "
    )

    total_organisms = num_plants + num_herbivores + num_carnivores
    capacity = grid_size * grid_size
    if total_organisms > capacity:
        raise ValueError(
            "The total number of starting organisms exceeds the grid capacity."
        )

    total_ticks = args.ticks if args.ticks is not None else prompt_positive_int(
        "Enter the number of ticks to simulate: "
    )

    if args.manual:
        manual_mode = True
        delay = 0.0
    else:
        while True:
            mode = input(
                "Choose simulation mode:\n"
                "1) Auto with delay\n"
                "2) Manual step-by-step\n"
                "Enter 1 or 2: "
            ).strip()
            if mode == "1":
                manual_mode = False
                delay = prompt_non_negative_float(
                    "Enter delay in seconds between ticks (0 for no delay): "
                )
                break
            if mode == "2":
                manual_mode = True
                delay = 0.0
                break
            print("Please enter 1 or 2.")

    return (
        grid_size,
        num_plants,
        num_herbivores,
        num_carnivores,
        total_ticks,
        delay,
        manual_mode,
    )


def main() -> None:
    args = parse_args()
    try:
        (
            grid_size,
            num_plants,
            num_herbivores,
            num_carnivores,
            total_ticks,
            delay,
            manual_mode,
        ) = collect_simulation_parameters(args)
    except ValueError as exc:
        print(exc)
        return

    ecosystem = Ecosystem(
        grid_size=grid_size,
        num_plants=num_plants,
        num_herbivores=num_herbivores,
        num_carnivores=num_carnivores,
        tick_delay=delay,
        manual_step=manual_mode,
    )

    try:
        ecosystem.run(total_ticks)
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")


if __name__ == "__main__":
    main()
