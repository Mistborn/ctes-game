"""
playtest.py — Headless agent runner.

Imports only from core.engine. No Pygame. No renderer.

Usage:
    python -m game.agent.playtest            # run balance report
    python -m game.agent.playtest --ticks 500 --runs 5
"""

from __future__ import annotations

import argparse
import statistics
import sys
from typing import Callable, Dict, List

from game.core import config, engine
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    BuildingType,
    GameStatus,
)
from game.core.state import GameState


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Strategy = Callable[[GameState], None]
MetricsDict = Dict[str, float]


# ---------------------------------------------------------------------------
# Strategy implementations
#
# Each strategy is a function that receives the current GameState and may call
# engine.apply_action() to mutate it. The strategy is called once per tick
# (after the tick has resolved), so it can react to the new state.
# ---------------------------------------------------------------------------

def strategy_food_first(state: GameState) -> None:
    """
    Maximise farmers until there is a surplus of ≥20 food, then diversify.
    Once surplus is established, start staffing a Lumber Mill, then Market.
    """
    SURPLUS_TARGET = 20  # ticks of buffer we want

    # How much food surplus do we currently have above consumption?
    consumption_per_tick = state.colonist_count * config.FOOD_PER_COLONIST_PER_TICK

    # Total food production from farms
    farm_production = sum(
        b.workers_assigned * config.FARM_FOOD_PER_WORKER_PER_TICK
        for b in state.buildings
        if b.building_type == BuildingType.FARM
    )
    surplus_rate = farm_production - consumption_per_tick

    if surplus_rate < SURPLUS_TARGET / 10:
        # Need more food: move an idle colonist to the first farm with space
        _try_add_worker(state, BuildingType.FARM)
    else:
        # Surplus is healthy — build economy
        # Build a Lumber Mill if we don't have a dedicated wood source for building
        lumber_mills = [b for b in state.buildings if b.building_type == BuildingType.LUMBER_MILL]
        if not lumber_mills and state.wood >= config.LUMBERMILL_BUILD_COST_WOOD:
            engine.apply_action(state, ActionBuildBuilding(BuildingType.LUMBER_MILL))
            return

        # Staff lumber mills
        for b in state.buildings:
            if b.building_type == BuildingType.LUMBER_MILL:
                _try_add_worker_to(state, b.id, BuildingType.LUMBER_MILL)

        # Build a Market once we have enough wood
        markets = [b for b in state.buildings if b.building_type == BuildingType.MARKET]
        if not markets and state.wood >= config.MARKET_BUILD_COST_WOOD:
            engine.apply_action(state, ActionBuildBuilding(BuildingType.MARKET))
            return

        # Staff markets
        for b in state.buildings:
            if b.building_type == BuildingType.MARKET:
                _try_add_worker_to(state, b.id, BuildingType.MARKET)


def strategy_production_rush(state: GameState) -> None:
    """
    Maximise Wood output early. Build Lumber Mills aggressively, then transition
    to Markets once wood is flowing.
    """
    # Always keep at least 2 farmers to avoid starvation
    farm_workers = sum(
        b.workers_assigned for b in state.buildings if b.building_type == BuildingType.FARM
    )
    if farm_workers < 2:
        _try_add_worker(state, BuildingType.FARM)
        return

    # Build Lumber Mills whenever affordable (up to 2 total)
    lumber_mills = [b for b in state.buildings if b.building_type == BuildingType.LUMBER_MILL]
    if len(lumber_mills) < 2 and state.wood >= config.LUMBERMILL_BUILD_COST_WOOD:
        engine.apply_action(state, ActionBuildBuilding(BuildingType.LUMBER_MILL))
        return

    # Fill lumber mills
    for b in state.buildings:
        if b.building_type == BuildingType.LUMBER_MILL:
            _try_add_worker_to(state, b.id, BuildingType.LUMBER_MILL)

    # Once we have plenty of wood, invest in a Market
    markets = [b for b in state.buildings if b.building_type == BuildingType.MARKET]
    if not markets and state.wood >= config.MARKET_BUILD_COST_WOOD + 20:
        engine.apply_action(state, ActionBuildBuilding(BuildingType.MARKET))
        return

    for b in state.buildings:
        if b.building_type == BuildingType.MARKET:
            _try_add_worker_to(state, b.id, BuildingType.MARKET)


def strategy_balanced(state: GameState) -> None:
    """
    Spread workers evenly across all building types. Build one of each kind
    as soon as affordable.
    """
    # Ensure each building type exists
    types_present = {b.building_type for b in state.buildings}

    for btype, cost in [
        (BuildingType.LUMBER_MILL, config.LUMBERMILL_BUILD_COST_WOOD),
        (BuildingType.MARKET, config.MARKET_BUILD_COST_WOOD),
        (BuildingType.FARM, config.FARM_BUILD_COST_WOOD),
    ]:
        if btype not in types_present and state.wood >= cost:
            engine.apply_action(state, ActionBuildBuilding(btype))
            return

    # Count workers per building type
    counts: Dict[BuildingType, int] = {
        BuildingType.FARM: 0,
        BuildingType.LUMBER_MILL: 0,
        BuildingType.MARKET: 0,
    }
    for b in state.buildings:
        counts[b.building_type] += b.workers_assigned

    # Add worker to the type with fewest workers (tiebreak: Farm > Mill > Market)
    priority = sorted(counts.items(), key=lambda kv: (kv[1], list(BuildingType).index(kv[0])))
    for btype, _ in priority:
        added = _try_add_worker(state, btype)
        if added:
            return


def strategy_gold_rush(state: GameState) -> None:
    """
    Get to the Market as fast as possible and max out gold production.
    Sacrifice food security to rush wood for construction.
    """
    # Keep only 1 farmer as food floor
    farm_workers = sum(
        b.workers_assigned for b in state.buildings if b.building_type == BuildingType.FARM
    )
    if farm_workers < 1:
        _try_add_worker(state, BuildingType.FARM)
        return

    # Rush a Lumber Mill immediately
    lumber_mills = [b for b in state.buildings if b.building_type == BuildingType.LUMBER_MILL]
    if not lumber_mills and state.wood >= config.LUMBERMILL_BUILD_COST_WOOD:
        engine.apply_action(state, ActionBuildBuilding(BuildingType.LUMBER_MILL))
        return

    # Max out lumber mill workers to get wood fast
    for b in state.buildings:
        if b.building_type == BuildingType.LUMBER_MILL:
            _try_add_worker_to(state, b.id, BuildingType.LUMBER_MILL)

    # Build Market ASAP
    markets = [b for b in state.buildings if b.building_type == BuildingType.MARKET]
    if not markets and state.wood >= config.MARKET_BUILD_COST_WOOD:
        engine.apply_action(state, ActionBuildBuilding(BuildingType.MARKET))
        return

    # Max out Market workers
    for b in state.buildings:
        if b.building_type == BuildingType.MARKET:
            _try_add_worker_to(state, b.id, BuildingType.MARKET)

    # Build more Markets if we have wood
    if len(markets) < 2 and state.wood >= config.MARKET_BUILD_COST_WOOD + 10:
        engine.apply_action(state, ActionBuildBuilding(BuildingType.MARKET))


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

STRATEGIES: Dict[str, Strategy] = {
    "food_first": strategy_food_first,
    "production_rush": strategy_production_rush,
    "balanced": strategy_balanced,
    "gold_rush": strategy_gold_rush,
}


# ---------------------------------------------------------------------------
# Run a single strategy for N ticks → metrics dict
# ---------------------------------------------------------------------------

def run_once(strategy: Strategy, max_ticks: int = 1000) -> MetricsDict:
    """Run one game with the given strategy, return a metrics dictionary."""
    state = engine.new_game()

    for _ in range(max_ticks):
        if state.status != GameStatus.PLAYING:
            break
        engine.tick(state)
        strategy(state)

    return {
        "ticks_survived": state.tick,
        "gold_earned": state.gold,
        "peak_colonists": state.peak_colonists,
        "starvation_events": state.starvation_events,
        "final_food": state.food,
        "final_wood": state.wood,
        "final_gold": state.gold,
        "won": 1.0 if state.status == GameStatus.WIN else 0.0,
    }


# ---------------------------------------------------------------------------
# Run a strategy N times and return aggregate stats
# ---------------------------------------------------------------------------

def run_strategy(
    name: str,
    strategy: Strategy,
    runs: int = 20,
    max_ticks: int = 1000,
) -> Dict[str, Dict[str, float]]:
    """Run a strategy `runs` times and return mean/min/max for each metric."""
    all_results: List[MetricsDict] = []
    for i in range(runs):
        result = run_once(strategy, max_ticks=max_ticks)
        all_results.append(result)

    aggregated: Dict[str, Dict[str, float]] = {}
    metric_keys = list(all_results[0].keys())
    for key in metric_keys:
        values = [r[key] for r in all_results]
        aggregated[key] = {
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
        }
    return aggregated


# ---------------------------------------------------------------------------
# Balance report: run all 4 strategies and print a formatted table
# ---------------------------------------------------------------------------

def run_balance_report(runs: int = 20, max_ticks: int = 1000) -> None:
    print("=" * 72)
    print("  KINGDOMS OF THE FORGOTTEN — Agent Balance Report")
    print(f"  {runs} runs per strategy, up to {max_ticks} ticks each")
    print("=" * 72)

    for name, strategy in STRATEGIES.items():
        print(f"\n  Strategy: {name.upper()}")
        print("  " + "-" * 60)
        stats = run_strategy(name, strategy, runs=runs, max_ticks=max_ticks)
        col_w = 18
        metrics_to_show = [
            ("ticks_survived", "Ticks survived"),
            ("won", "Win rate (0/1)"),
            ("gold_earned", "Gold earned"),
            ("peak_colonists", "Peak colonists"),
            ("starvation_events", "Starvations"),
            ("final_food", "Final food"),
            ("final_wood", "Final wood"),
        ]
        header = f"  {'Metric':<22} {'Mean':>{col_w}} {'Min':>{col_w}} {'Max':>{col_w}}"
        print(header)
        print("  " + "-" * (22 + col_w * 3 + 2))
        for key, label in metrics_to_show:
            if key not in stats:
                continue
            s = stats[key]
            row = (
                f"  {label:<22} "
                f"{s['mean']:>{col_w}.2f} "
                f"{s['min']:>{col_w}.2f} "
                f"{s['max']:>{col_w}.2f}"
            )
            print(row)

    print("\n" + "=" * 72)
    print("  Balance report complete.")
    print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# Helper: assign a worker to the first building of a given type with space
# ---------------------------------------------------------------------------

_MAX_WORKERS_MAP = {
    BuildingType.FARM:        config.FARM_MAX_WORKERS,
    BuildingType.LUMBER_MILL: config.LUMBERMILL_MAX_WORKERS,
    BuildingType.MARKET:      config.MARKET_MAX_WORKERS,
    BuildingType.QUARRY:      config.QUARRY_MAX_WORKERS,
    BuildingType.SAWMILL:     config.SAWMILL_MAX_WORKERS,
}


def _try_add_worker(state: GameState, btype: BuildingType) -> bool:
    """Assign one idle colonist to the first available building of btype."""
    max_w = _MAX_WORKERS_MAP[btype]
    for b in state.buildings:
        if b.building_type == btype and b.workers_assigned < max_w:
            if state.idle_colonists > 0:
                engine.apply_action(state, ActionAssignWorker(b.id, +1))
                return True
    return False


def _try_add_worker_to(state: GameState, building_id: int, btype: BuildingType) -> bool:
    max_w = _MAX_WORKERS_MAP[btype]
    b = state.building_by_id(building_id)
    if b and b.workers_assigned < max_w and state.idle_colonists > 0:
        engine.apply_action(state, ActionAssignWorker(building_id, +1))
        return True
    return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Headless colony builder balance tester.")
    parser.add_argument("--ticks", type=int, default=1000, help="Max ticks per run (default 1000)")
    parser.add_argument("--runs", type=int, default=20, help="Runs per strategy (default 20)")
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        default=None,
        help="Run only one strategy (default: all)",
    )
    args = parser.parse_args()

    if args.strategy:
        name = args.strategy
        strat = STRATEGIES[name]
        stats = run_strategy(name, strat, runs=args.runs, max_ticks=args.ticks)
        print(f"\nStrategy: {name}\n")
        for metric, values in stats.items():
            print(f"  {metric}: mean={values['mean']:.2f}  min={values['min']:.2f}  max={values['max']:.2f}")
    else:
        run_balance_report(runs=args.runs, max_ticks=args.ticks)


if __name__ == "__main__":
    main()
