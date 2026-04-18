from __future__ import annotations

import argparse
import sys

def _build_base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生态系统模拟器")
    parser.add_argument(
        "--mode",
        choices=("ui", "headless"),
        default="ui",
        help="使用 Tkinter 图形界面运行，或以无界面课程训练模式运行",
    )
    return parser


def main() -> None:
    argv = sys.argv[1:]
    mode_is_headless = "--mode=headless" in argv
    if "--mode" in argv:
        idx = argv.index("--mode")
        if idx + 1 < len(argv) and argv[idx + 1] == "headless":
            mode_is_headless = True

    if mode_is_headless:
        from headless_training import add_headless_args, run_curriculum

        parser = _build_base_parser()
        add_headless_args(parser)
        args = parser.parse_args()
        run_curriculum(args)
        return

    from game_ui import GameUI

    GameUI().run()


if __name__ == "__main__":
    main()
