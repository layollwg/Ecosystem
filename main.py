from __future__ import annotations

import argparse

from headless_training import add_headless_args, run_curriculum


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生态系统模拟器")
    parser.add_argument(
        "--mode",
        choices=("ui", "headless"),
        default="ui",
        help="使用 Tkinter 图形界面运行，或以无界面课程训练模式运行",
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
