"""
playtest.py — Headless agent runner.

Imports only from core.engine (and core.save for --load). No Pygame. No renderer.

Usage:
    python -m game.agent.playtest                        # run balance report
    python -m game.agent.playtest --ticks 500 --runs 5
    python -m game.agent.playtest --load saves/autosave.json  # start from save
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
    ActionResearchTech,
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
    return run_once_from_state(engine.new_game(), strategy, max_ticks)


def run_once_from_state(
    state: GameState,
    strategy: Strategy,
    max_ticks: int = 1000,
) -> MetricsDict:
    """
    Run *strategy* from an existing *state* until the game ends or *max_ticks*
    additional ticks have elapsed.

    The state is **not** mutated — a deep copy is used so the caller can call
    this multiple times with the same starting state to compare strategies or
    explore different continuations.
    """
    import copy

    state = copy.deepcopy(state)
    ticks_run = 0
    while ticks_run < max_ticks:
        if state.status != GameStatus.PLAYING:
            break
        engine.tick(state)
        strategy(state)
        ticks_run += 1

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
    """Run a strategy `runs` times (each from a fresh new game) and return mean/min/max."""
    return run_strategy_from_state(engine.new_game(), name, strategy, runs, max_ticks)


def run_strategy_from_state(
    starting_state: GameState,
    name: str,
    strategy: Strategy,
    runs: int = 20,
    max_ticks: int = 1000,
) -> Dict[str, Dict[str, float]]:
    """
    Run *strategy* from *starting_state* for *runs* independent trials.

    Each trial deep-copies the starting state so all runs begin identically.
    Returns mean/min/max for each metric — useful for evaluating how a
    strategy performs from a specific mid-game checkpoint.

    Example (agent usage)::

        from game.core.save import load_game
        from game.agent.playtest import run_strategy_from_state, STRATEGIES

        state = load_game("saves/autosave.json")
        stats = run_strategy_from_state(state, "gold_rush", STRATEGIES["gold_rush"], runs=50)
    """
    all_results: List[MetricsDict] = []
    for _ in range(runs):
        result = run_once_from_state(starting_state, strategy, max_ticks=max_ticks)
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
# LLM Evaluator — requires `anthropic` package
# An LLM writes a new Python strategy function at each checkpoint.
# ---------------------------------------------------------------------------

def _format_state_for_llm(state: GameState) -> str:
    """Return a compact human-readable summary of the current game state."""
    lines = [
        f"Tick: {state.tick}  |  Status: {state.status.value.upper()}",
        "",
        "Resources:",
        (
            f"  food={state.food:.1f} ({state.food_rate:+.2f}/tick)  "
            f"wood={state.wood:.1f} ({state.wood_rate:+.2f}/tick)  "
            f"gold={state.gold:.1f} ({state.gold_rate:+.2f}/tick)"
        ),
        (
            f"  stone={state.stone:.1f} ({state.stone_rate:+.2f}/tick)  "
            f"planks={state.planks:.1f} ({state.planks_rate:+.2f}/tick)"
        ),
        "",
        f"Colonists: {state.colonist_count} total, {state.idle_colonists} idle",
        "",
        "Buildings:",
    ]
    for b in state.buildings:
        max_w = _MAX_WORKERS_MAP.get(b.building_type, "?")
        lines.append(f"  {b.building_type.value} (id={b.id}): {b.workers_assigned}/{max_w} workers")
    techs = state.researched_tech_ids or []
    lines += [
        "",
        f"Researched: {', '.join(techs) if techs else 'none'}",
        f"Starvation events: {state.starvation_events}",
        f"Win condition: {config.WIN_GOLD_TARGET} gold (current: {state.gold:.1f})",
    ]
    return "\n".join(lines)


def _compile_strategy(code: str) -> Strategy:
    """
    exec() LLM-generated strategy code in a sandboxed namespace.
    Returns the `strategy` callable, or raises ValueError.
    """
    _SAFE_BUILTINS = {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "filter": filter, "float": float, "int": int,
        "isinstance": isinstance, "iter": iter, "len": len, "list": list,
        "map": map, "max": max, "min": min, "next": next, "print": print,
        "range": range, "round": round, "set": set, "sorted": sorted,
        "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
        "None": None, "True": True, "False": False,
    }
    namespace: Dict = {
        "__builtins__": _SAFE_BUILTINS,
        "engine": engine,
        "config": config,
        "ActionAssignWorker": ActionAssignWorker,
        "ActionBuildBuilding": ActionBuildBuilding,
        "ActionResearchTech": ActionResearchTech,
        "BuildingType": BuildingType,
        "GameStatus": GameStatus,
    }
    exec(compile(code, "<llm_strategy>", "exec"), namespace)  # noqa: S102
    fn = namespace.get("strategy")
    if not callable(fn):
        raise ValueError("LLM code did not define a callable `strategy` function.")
    return fn  # type: ignore[return-value]


def _ask_llm_for_strategy(
    client,
    model: str,
    state_summary: str,
    checkpoint: int,
    checkpoint_ticks: int,
    history: List[Dict],
) -> "tuple[str, str]":
    """Ask the LLM to write a strategy function. Returns (code, rationale)."""
    import re

    system_prompt = (
        'You are playing "Kingdoms of the Forgotten", a medieval colony builder.\n'
        f"Each checkpoint you write a Python function that drives the colony for the next {checkpoint_ticks} ticks.\n\n"
        "Available names (already in scope — do NOT use import statements):\n"
        "  engine           — call engine.apply_action(state, action) to act\n"
        "  config           — balance constants (e.g. config.FARM_BUILD_COST_WOOD)\n"
        "  ActionAssignWorker(building_id, delta)   — delta=+1 assign, -1 remove\n"
        "  ActionBuildBuilding(building_type)       — spend wood to construct\n"
        "  ActionResearchTech(tech_id)              — spend gold to research\n"
        "  BuildingType.FARM / LUMBER_MILL / MARKET / QUARRY / SAWMILL\n"
        "  GameStatus.PLAYING / WIN / LOSE\n\n"
        "Function signature (must match exactly):\n"
        "  def strategy(state) -> None:\n"
        "      # called once per tick; act via engine.apply_action()\n\n"
        f"Win: gold >= {config.WIN_GOLD_TARGET}. Lose: all colonists starve.\n"
        f"Food consumption: {config.FOOD_PER_COLONIST_PER_TICK} per colonist per tick.\n"
        "Market consumes wood (or planks) to produce gold.\n"
        "Key state attributes: state.idle_colonists (int), state.colonist_count (int),\n"
        "  state.food/wood/gold/stone/planks (float), state.researched_tech_ids (list[str])\n"
        "Building attributes: b.id (int), b.building_type (BuildingType), b.workers_assigned (int)\n"
        "  (NOT num_workers — use workers_assigned)\n"
        "\nResearch — costs and tech_ids (DO NOT guess config constant names for costs):\n"
        + "".join(
            f"  ActionResearchTech('{t['tech_id']}')  — costs {t['gold_cost']} gold  — {t['description']}\n"
            for t in config.RESEARCH_TECHS
        )
        + "Use: if state.gold >= <cost> and '<tech_id>' not in state.researched_tech_ids: engine.apply_action(state, ActionResearchTech('<tech_id>'))\n"
        "\nUseful config constants (use these exact names):\n"
        f"  FARM_BUILD_COST_WOOD={config.FARM_BUILD_COST_WOOD}  LUMBERMILL_BUILD_COST_WOOD={config.LUMBERMILL_BUILD_COST_WOOD}\n"
        f"  MARKET_BUILD_COST_WOOD={config.MARKET_BUILD_COST_WOOD}  QUARRY_BUILD_COST_WOOD={config.QUARRY_BUILD_COST_WOOD}\n"
        f"  FARM_MAX_WORKERS={config.FARM_MAX_WORKERS}  LUMBERMILL_MAX_WORKERS={config.LUMBERMILL_MAX_WORKERS}\n"
        f"  MARKET_MAX_WORKERS={config.MARKET_MAX_WORKERS}  QUARRY_MAX_WORKERS={config.QUARRY_MAX_WORKERS}"
    )

    if history:
        hist_parts = [
            f"Checkpoint {h['checkpoint']}: {h['rationale']}\n  Result: {h['outcome_summary']}"
            for h in history[-5:]
        ]
        history_text = "\n".join(hist_parts)
    else:
        history_text = "None — this is checkpoint 0."

    user_prompt = (
        f"## Checkpoint {checkpoint} — Current State\n\n"
        f"{state_summary}\n\n"
        f"## Previous decisions\n{history_text}\n\n"
        "Respond in this EXACT format (nothing else before or after):\n\n"
        f"RATIONALE: <2-4 sentences on your plan for the next {checkpoint_ticks} ticks>\n"
        "CODE:\n```python\ndef strategy(state):\n    <your implementation>\n```"
    )

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = response.content[0].text.strip()

    rationale_match = re.search(r"RATIONALE:\s*(.+?)(?=\nCODE:|$)", text, re.DOTALL)
    rationale = rationale_match.group(1).strip() if rationale_match else ""

    code_match = re.search(r"```python\s*(def strategy[\s\S]+?)```", text)
    if not code_match:
        raise ValueError(f"No valid code block in LLM response:\n{text[:400]}")
    code = code_match.group(1).strip()

    return code, rationale


def _write_markdown_log(
    log_path: str,
    entries: List[Dict],
    final_state: GameState,
    model: str,
    checkpoint_ticks: int,
) -> None:
    """Write the decision log to a Markdown file."""
    import datetime as _dt
    from pathlib import Path as _Path

    status = final_state.status.value
    if status == "win":
        result = f"WIN at tick {final_state.tick}"
    elif status in ("lose", "lose_tribute"):
        result = f"LOSE ({status}) at tick {final_state.tick}"
    else:
        result = f"INCOMPLETE — reached tick {final_state.tick}"

    lines = [
        "# LLM Agent Playthrough Log",
        f"Date: {_dt.date.today()}  |  Model: {model}",
        f"{len(entries)} checkpoints x {checkpoint_ticks} ticks each",
        "",
        f"## Final Result: {result}",
        (
            f"Resources: food={final_state.food:.1f}  wood={final_state.wood:.1f}  "
            f"gold={final_state.gold:.1f}  stone={final_state.stone:.1f}  "
            f"planks={final_state.planks:.1f}"
        ),
        f"Peak colonists: {final_state.peak_colonists}  |  "
        f"Starvation events: {final_state.starvation_events}",
        "",
        "---",
    ]

    for entry in entries:
        lines += [
            "",
            f"## Checkpoint {entry['checkpoint']} (Tick {entry['tick_start']})",
            "",
            "### Game State",
            entry["state_before"],
            "",
            "### LLM Decision",
            f"**Rationale:** {entry['rationale']}",
            "",
            "**Strategy Code:**",
            "```python",
            entry["code"] or "# (no valid code produced — no-op fallback used)",
            "```",
            "",
            "### Outcome",
            entry["outcome_summary"],
            "",
            "---",
        ]

    _Path(log_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"  Log written to: {log_path}")


def run_llm_agent(
    model: str = "claude-sonnet-4-6",
    checkpoint_ticks: int = 1000,
    num_checkpoints: int = 20,
    log_path: str | None = None,
) -> MetricsDict:
    """
    Run one game driven by an LLM that writes a new Python strategy function
    at each checkpoint. Requires ANTHROPIC_API_KEY environment variable.
    Returns a MetricsDict (same schema as run_once).
    """
    import anthropic
    import datetime

    if log_path is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"llm_agent_{ts}.md"

    client = anthropic.Anthropic()
    state = engine.new_game()
    entries: List[Dict] = []

    print(f"\n{'=' * 72}")
    print(
        f"  LLM Agent  |  model={model}  |  "
        f"{num_checkpoints} checkpoints x {checkpoint_ticks} ticks"
    )
    print("=" * 72)

    def _noop(s: GameState) -> None:
        pass

    for checkpoint in range(num_checkpoints):
        if state.status != GameStatus.PLAYING:
            break

        tick_start = state.tick
        food0, wood0, gold0 = state.food, state.wood, state.gold
        col0 = state.colonist_count

        state_summary = _format_state_for_llm(state)
        print(f"\n  Checkpoint {checkpoint} (tick {tick_start}) — querying {model}...")

        try:
            code, rationale = _ask_llm_for_strategy(
                client, model, state_summary, checkpoint, checkpoint_ticks, entries
            )
            strategy_fn = _compile_strategy(code)
            preview = rationale[:80] + ("..." if len(rationale) > 80 else "")
            print(f"  Rationale: {preview}")
        except Exception as exc:
            print(f"  WARNING: strategy failed ({exc}). Using no-op.")
            code, rationale, strategy_fn = "", f"[ERROR: {exc}]", _noop

        exec_error: str = ""
        for _ in range(checkpoint_ticks):
            if state.status != GameStatus.PLAYING:
                break
            engine.tick(state)
            try:
                strategy_fn(state)
            except Exception as exc:
                if not exec_error:
                    exec_error = str(exc)
                    print(f"  WARNING: strategy raised {type(exc).__name__}: {exc} — switching to no-op.")
                strategy_fn = _noop
        if exec_error:
            rationale += f"\n[RUNTIME ERROR: {exec_error}]"

        outcome = (
            f"food {food0:.1f}->{state.food:.1f}  wood {wood0:.1f}->{state.wood:.1f}  "
            f"gold {gold0:.1f}->{state.gold:.1f}  colonists {col0}->{state.colonist_count}"
        )
        print(f"  Result: {outcome}")

        entries.append({
            "checkpoint": checkpoint,
            "tick_start": tick_start,
            "state_before": state_summary,
            "rationale": rationale,
            "code": code,
            "outcome_summary": outcome,
        })

    _write_markdown_log(log_path, entries, state, model, checkpoint_ticks)
    print(f"\n{'=' * 72}")
    print(f"  LLM Agent complete. Status: {state.status.value.upper()}")
    print("=" * 72 + "\n")

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
    parser.add_argument(
        "--load",
        metavar="PATH",
        default=None,
        help="Load a save file and run strategies from that state instead of a new game.",
    )
    args = parser.parse_args()

    # Determine starting state
    if args.load:
        from game.core.save import load_game
        from pathlib import Path
        starting_state = load_game(Path(args.load))
        print(f"Loaded save: {args.load} (tick {starting_state.tick})")
    else:
        starting_state = engine.new_game()

    if args.strategy:
        name = args.strategy
        strat = STRATEGIES[name]
        stats = run_strategy_from_state(starting_state, name, strat, runs=args.runs, max_ticks=args.ticks)
        print(f"\nStrategy: {name}\n")
        for metric, values in stats.items():
            print(f"  {metric}: mean={values['mean']:.2f}  min={values['min']:.2f}  max={values['max']:.2f}")
    elif args.load:
        # With a loaded state, run all strategies and print a mini-report
        for name, strat in STRATEGIES.items():
            print(f"\n  Strategy: {name.upper()}")
            stats = run_strategy_from_state(starting_state, name, strat, runs=args.runs, max_ticks=args.ticks)
            for metric, values in stats.items():
                print(f"    {metric:<22} mean={values['mean']:>8.2f}  min={values['min']:>8.2f}  max={values['max']:>8.2f}")
    else:
        run_balance_report(runs=args.runs, max_ticks=args.ticks)


if __name__ == "__main__":
    main()
