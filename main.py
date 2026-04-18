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
    parser.add_argument(
        "--load-checkpoint",
        type=str,
        default=None,
        help="提供 RLlib Checkpoint 的绝对路径，用于 UI 推理回放",
    )
    return parser


def _is_headless_mode(argv: list[str]) -> bool:
    if "--mode=headless" in argv:
        return True
    if "--mode" not in argv:
        return False
    idx = argv.index("--mode")
    return idx + 1 < len(argv) and argv[idx + 1] == "headless"


def main() -> None:
    argv = sys.argv[1:]
    if _is_headless_mode(argv):
        from headless_training import add_headless_args, run_curriculum

        parser = _build_base_parser()
        add_headless_args(parser)
        args = parser.parse_args()
        run_curriculum(args)
        return

    parser = _build_base_parser()
    args = parser.parse_args(argv)
    from game_ui import GameUI

    GameUI(checkpoint_path=args.load_checkpoint).run()


if __name__ == "__main__":
    main()
