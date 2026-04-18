from __future__ import annotations

import argparse

from headless_training import add_headless_args, run_curriculum


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ecosystem simulator")
    parser.add_argument(
        "--mode",
        choices=("ui", "headless"),
        default="ui",
        help="Run with Tkinter UI or run headless curriculum training",
    )
    add_headless_args(parser)
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.mode == "headless":
        run_curriculum(args)
        return

    from game_ui import GameUI

    GameUI().run()


if __name__ == "__main__":
    main()
