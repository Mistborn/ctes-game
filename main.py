"""
main.py — Entry point for Kingdoms of the Forgotten.

Normal mode:
    python main.py

Headless / agent mode (no display, runs balance report):
    python main.py --headless
    python main.py --headless --ticks 500 --runs 10
    python main.py --headless --strategy gold_rush
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kingdoms of the Forgotten — medieval colony builder."
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless agent balance report (no Pygame window).",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=1000,
        help="(headless) Max ticks per run (default: 1000).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=20,
        help="(headless) Number of runs per strategy (default: 20).",
    )
    parser.add_argument(
        "--strategy",
        choices=["food_first", "production_rush", "balanced", "gold_rush"],
        default=None,
        help="(headless) Run only one named strategy.",
    )
    args = parser.parse_args()

    if args.headless:
        # Delegate entirely to the agent module — no Pygame needed
        from game.agent.playtest import run_balance_report, run_strategy, STRATEGIES

        if args.strategy:
            name = args.strategy
            strat = STRATEGIES[name]
            stats = run_strategy(name, strat, runs=args.runs, max_ticks=args.ticks)
            print(f"\nStrategy: {name.upper()}\n")
            for metric, values in stats.items():
                print(
                    f"  {metric:<22}  mean={values['mean']:>8.2f}  "
                    f"min={values['min']:>8.2f}  max={values['max']:>8.2f}"
                )
        else:
            run_balance_report(runs=args.runs, max_ticks=args.ticks)
        return

    # -----------------------------------------------------------------------
    # Normal interactive mode — import Pygame only when needed
    # -----------------------------------------------------------------------
    from game.core import engine
    from game.core.entities import GameStatus
    from game.renderer.display import Renderer

    state = engine.new_game()
    renderer = Renderer()

    while True:
        dt = renderer.tick_dt()

        # Collect player actions
        actions = renderer.handle_events(state)
        for action in actions:
            engine.apply_action(state, action)

        # Advance simulation if enough real time has passed
        if renderer.should_tick(state, dt):
            engine.tick(state)

        # Render
        renderer.draw(state)


if __name__ == "__main__":
    main()
