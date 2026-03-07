"""
main.py — Entry point for Kingdoms of the Forgotten.

Normal mode:
    python main.py                  # shows start screen (New Game / Continue)
    python main.py --new-game       # skip start screen, begin a fresh game

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
    parser.add_argument(
        "--new-game",
        action="store_true",
        help="Skip the start screen and begin a fresh game immediately.",
    )
    parser.add_argument(
        "--load",
        metavar="PATH",
        default=None,
        help="(headless) Load a save file and run strategies from that state.",
    )
    parser.add_argument(
        "--llm-agent",
        action="store_true",
        help="Run LLM-driven agent playthrough (requires ANTHROPIC_API_KEY).",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="(llm-agent) Claude model to use (default: claude-sonnet-4-6).",
    )
    parser.add_argument(
        "--checkpoints",
        type=int,
        default=20,
        help="(llm-agent) Number of strategy checkpoints (default: 20).",
    )
    parser.add_argument(
        "--checkpoint-ticks",
        type=int,
        default=1000,
        help="(llm-agent) Ticks per checkpoint (default: 1000).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="(llm-agent) Output log file path (default: auto-named).",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="(llm-agent) Number of consecutive runs to attempt (default: 1).",
    )
    args = parser.parse_args()

    if args.llm_agent:
        from game.agent.playtest import run_llm_agent
        run_llm_agent(
            model=args.model,
            checkpoint_ticks=args.checkpoint_ticks,
            num_checkpoints=args.checkpoints,
            log_path=args.log_file,
            num_runs=args.num_runs,
        )
        return

    if args.headless:
        # Delegate entirely to the agent module — no Pygame needed
        from game.agent.playtest import run_balance_report, run_strategy_from_state, STRATEGIES
        from game.core import engine as _engine

        if args.load:
            from game.core.save import load_game
            from pathlib import Path
            starting_state = load_game(Path(args.load))
            print(f"Loaded save: {args.load} (tick {starting_state.tick})")
        else:
            starting_state = _engine.new_game()

        if args.strategy:
            name = args.strategy
            strat = STRATEGIES[name]
            stats = run_strategy_from_state(
                starting_state, name, strat, runs=args.runs, max_ticks=args.ticks
            )
            print(f"\nStrategy: {name.upper()}\n")
            for metric, values in stats.items():
                print(
                    f"  {metric:<22}  mean={values['mean']:>8.2f}  "
                    f"min={values['min']:>8.2f}  max={values['max']:>8.2f}"
                )
        elif args.load:
            for name, strat in STRATEGIES.items():
                print(f"\n  Strategy: {name.upper()}")
                stats = run_strategy_from_state(
                    starting_state, name, strat, runs=args.runs, max_ticks=args.ticks
                )
                for metric, values in stats.items():
                    print(
                        f"    {metric:<22} mean={values['mean']:>8.2f}  "
                        f"min={values['min']:>8.2f}  max={values['max']:>8.2f}"
                    )
        else:
            run_balance_report(runs=args.runs, max_ticks=args.ticks)
        return

    # -----------------------------------------------------------------------
    # Normal interactive mode — import Pygame only when needed
    # -----------------------------------------------------------------------
    import pygame

    from game.core import config, engine
    from game.core import save as game_save
    from game.core.entities import GameStatus
    from game.meta.progression import MetaState
    from game.renderer.display import Renderer

    meta = MetaState.load()
    renderer = Renderer()

    first_run = True

    while True:
        # Start-screen only on the very first run; subsequent runs skip it
        if first_run:
            if args.new_game:
                state = engine.new_game(meta)
            else:
                saves = game_save.list_saves()
                state = renderer.show_start_screen(saves, meta=meta)
            first_run = False
        else:
            state = engine.new_game(meta)

        renderer.reset_for_new_run()
        last_autosave_tick: int = state.tick
        start_next_run = False

        # ---------------------------------------------------------------
        # Inner game loop — one run
        # ---------------------------------------------------------------
        while not start_next_run:
            dt = renderer.tick_dt()

            # Collect player actions
            actions = renderer.handle_events(state)
            for action in actions:
                if action == "save_and_exit":
                    game_save.save_game(state)
                    pygame.quit()
                    sys.exit()
                elif action == "exit_no_save":
                    pygame.quit()
                    sys.exit()
                elif action == "start_next_run":
                    start_next_run = True
                    break
                elif action == "toggle_auto_hire":
                    state.auto_hire_enabled = not state.auto_hire_enabled
                elif action == "toggle_auto_assign":
                    state.auto_assign_enabled = not state.auto_assign_enabled
                else:
                    engine.apply_action(state, action)

            if start_next_run:
                break

            # Advance simulation if enough real time has passed
            if renderer.should_tick(state, dt):
                engine.tick(state)

                # Autosave every AUTOSAVE_INTERVAL_TICKS ticks
                if (
                    state.tick > 0
                    and state.tick % config.AUTOSAVE_INTERVAL_TICKS == 0
                    and state.tick != last_autosave_tick
                ):
                    game_save.autosave_game(state)
                    last_autosave_tick = state.tick

            # Render
            renderer.draw(state)

        # ---------------------------------------------------------------
        # Run ended — update meta, show between-runs screen
        # ---------------------------------------------------------------
        lp_earned = meta.end_run(state)
        meta.save()
        renderer.show_between_runs_screen(meta, state, lp_earned)
        meta.run_number += 1
        meta.save()


if __name__ == "__main__":
    main()
