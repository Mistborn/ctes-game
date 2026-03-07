"""
engine.py — Pure game logic. No Pygame. No renderer imports. Ever.

Public API:
    new_game()          -> GameState
    tick(state)         -> GameState   (advances simulation by one tick)
    apply_action(state, action) -> GameState
    get_state(state)    -> dict        (snapshot for renderer / agent)
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Optional, Union

from game.core import config
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionRecruitCitizen,
    ActionResearchTech,
    ActionSetSpeed,
    Building,
    BuildingType,
    Colonist,
    GameStatus,
)
from game.core.state import GameState

if TYPE_CHECKING:
    from game.meta.progression import MetaState


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def new_game(meta: Optional["MetaState"] = None) -> GameState:
    """Return a freshly initialised GameState, applying meta upgrades if provided."""
    state = GameState()

    # Apply meta context
    if meta is not None:
        state.run_number = meta.run_number
        unlocked = set(meta.unlocked_upgrades)

        # Starting colonist count (use highest tier only)
        if "extra_colonists_2" in unlocked:
            starting_colonists = 7
        elif "extra_colonists_1" in unlocked:
            starting_colonists = 6
        else:
            starting_colonists = config.STARTING_COLONISTS

        # Starting food (use highest tier only)
        if "more_food_2" in unlocked:
            state.food = 120.0
        elif "more_food_1" in unlocked:
            state.food = 80.0

        # Hearty colonists: -10% food consumption
        if "hearty_colonists" in unlocked:
            state.food_consumption_mult = 0.9

        # Trade connections: +15% market gold
        if "trade_connections" in unlocked:
            state.market_gold_bonus_mult = 1.15
    else:
        starting_colonists = config.STARTING_COLONISTS

    # Tribute schedule for this run
    state.tribute_schedule = _compute_tribute_schedule(state.run_number)

    # Spawn starting colonists
    for _ in range(starting_colonists):
        _add_colonist(state)

    # Build the two starting buildings
    farm = Building(id=state.next_building_id, building_type=BuildingType.FARM)
    state.next_building_id += 1
    state.buildings.append(farm)

    mill = Building(id=state.next_building_id, building_type=BuildingType.LUMBER_MILL)
    state.next_building_id += 1
    state.buildings.append(mill)

    # Distribute starting workers: 3 on farm, 2 on lumber mill (capped to actual colonists)
    _assign_colonist_to_building(state, farm.id, count=3)
    _assign_colonist_to_building(state, mill.id, count=2)

    # Free sawmill upgrade
    if meta is not None and "free_sawmill" in set(meta.unlocked_upgrades):
        sawmill = Building(id=state.next_building_id, building_type=BuildingType.SAWMILL)
        state.next_building_id += 1
        state.buildings.append(sawmill)

    # Veteran memory: carry the last researched tech from the previous run
    if (
        meta is not None
        and "veteran_memory" in set(meta.unlocked_upgrades)
        and meta.carried_tech_id
        and meta.carried_tech_id not in state.researched_tech_ids
    ):
        state.researched_tech_ids.append(meta.carried_tech_id)

    state.peak_colonists = state.colonist_count
    return state


# ---------------------------------------------------------------------------
# Main tick
# ---------------------------------------------------------------------------

def tick(state: GameState) -> GameState:
    """
    Advance the simulation by one tick.
    Returns the mutated state (mutated in-place for performance;
    callers that need immutability should pass copy.deepcopy(state)).
    """
    if state.status != GameStatus.PLAYING:
        return state

    state.tick += 1

    # Snapshot resources before tick for rate calculation
    food_before  = state.food
    wood_before  = state.wood
    gold_before  = state.gold
    stone_before = state.stone
    planks_before = state.planks

    # 1. Buildings produce resources
    _process_production(state)

    # 2. Colonists consume food
    _process_consumption(state)

    # 3. Apply resource caps
    state.food   = min(state.food,   config.FOOD_CAP)
    state.wood   = min(state.wood,   config.WOOD_CAP)
    state.gold   = min(state.gold,   config.GOLD_CAP)
    state.stone  = min(state.stone,  config.STONE_CAP)
    state.planks = min(state.planks, config.PLANKS_CAP)
    # Resources cannot go below zero
    state.food   = max(state.food,   0.0)
    state.wood   = max(state.wood,   0.0)
    state.gold   = max(state.gold,   0.0)
    state.stone  = max(state.stone,  0.0)
    state.planks = max(state.planks, 0.0)

    # 4. Update per-tick rate display values
    state.food_rate   = state.food   - food_before
    state.wood_rate   = state.wood   - wood_before
    state.gold_rate   = state.gold   - gold_before
    state.stone_rate  = state.stone  - stone_before
    state.planks_rate = state.planks - planks_before

    # 5. Track total gold produced (for LP; measured before tribute deduction)
    if state.gold_rate > 0:
        state.total_gold_earned += state.gold_rate

    # 6. Tribute demand (every TRIBUTE_INTERVAL_TICKS, skipping tick 0)
    if state.tick > 0 and state.tick % config.TRIBUTE_INTERVAL_TICKS == 0:
        _check_tribute(state)

    # 7. Win / Lose checks
    _check_endgame(state)

    return state


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------

def apply_action(
    state: GameState,
    action: Union[ActionAssignWorker, ActionBuildBuilding, ActionSetSpeed, ActionResearchTech, ActionRecruitCitizen],
) -> GameState:
    """Apply a player action to the state. Returns the mutated state."""
    if state.status != GameStatus.PLAYING:
        return state

    if isinstance(action, ActionAssignWorker):
        _handle_assign_worker(state, action)
    elif isinstance(action, ActionBuildBuilding):
        _handle_build_building(state, action)
    elif isinstance(action, ActionSetSpeed):
        _handle_set_speed(state, action)
    elif isinstance(action, ActionResearchTech):
        _handle_research_tech(state, action)
    elif isinstance(action, ActionRecruitCitizen):
        _handle_recruit_citizen(state)

    return state


# ---------------------------------------------------------------------------
# State snapshot (for renderer / agent)
# ---------------------------------------------------------------------------

def get_state(state: GameState) -> dict:
    """Return a plain-dict snapshot of the current state."""
    return state.to_dict()


# ---------------------------------------------------------------------------
# Internal helpers — production
# ---------------------------------------------------------------------------

def _process_production(state: GameState) -> None:
    """Apply per-tick resource production from all buildings."""
    researched = set(state.researched_tech_ids)
    passive_mult = config.RESEARCH_GUILD_HALLS_PASSIVE_MULT if "guild_halls" in researched else 1.0
    farm_mult    = config.RESEARCH_CROP_ROTATION_FARM_MULT  if "crop_rotation" in researched else 1.0
    tool_mult    = config.RESEARCH_REINFORCED_TOOLS_MULT    if "reinforced_tools" in researched else 1.0
    market_mult  = (config.RESEARCH_TRADE_ROUTES_MARKET_MULT if "trade_routes" in researched else 1.0) * state.market_gold_bonus_mult
    sawmill_mult = config.RESEARCH_STONE_MASONRY_SAWMILL_MULT if "stone_masonry" in researched else 1.0

    for building in state.buildings:
        workers = building.workers_assigned
        btype = building.building_type

        # Passive income (applied regardless of worker count)
        if btype == BuildingType.FARM:
            state.food += config.FARM_PASSIVE_FOOD_PER_TICK * farm_mult * passive_mult
        elif btype == BuildingType.LUMBER_MILL:
            state.wood += config.LUMBERMILL_PASSIVE_WOOD_PER_TICK * tool_mult * passive_mult
        elif btype == BuildingType.QUARRY:
            state.stone += config.QUARRY_PASSIVE_STONE_PER_TICK * tool_mult * passive_mult

        # Worker-based production
        if workers == 0:
            continue

        if btype == BuildingType.FARM:
            state.food += workers * config.FARM_FOOD_PER_WORKER_PER_TICK * farm_mult

        elif btype == BuildingType.LUMBER_MILL:
            state.wood += workers * config.LUMBERMILL_WOOD_PER_WORKER_PER_TICK * tool_mult

        elif btype == BuildingType.QUARRY:
            state.stone += workers * config.QUARRY_STONE_PER_WORKER_PER_TICK * tool_mult

        elif btype == BuildingType.SAWMILL:
            # Sawmill converts Wood → Planks
            wood_needed = workers * config.SAWMILL_WOOD_PER_WORKER_PER_TICK
            if state.wood >= wood_needed:
                state.wood -= wood_needed
                state.planks += workers * config.SAWMILL_PLANKS_PER_WORKER_PER_TICK * sawmill_mult
            else:
                if wood_needed > 0:
                    fraction = state.wood / wood_needed
                    state.planks += workers * config.SAWMILL_PLANKS_PER_WORKER_PER_TICK * sawmill_mult * fraction
                    state.wood = 0.0

        elif btype == BuildingType.MARKET:
            # Prefer Planks over Wood for gold production (better rate)
            planks_needed = workers * config.MARKET_PLANKS_PER_WORKER_PER_TICK
            wood_needed   = workers * config.MARKET_WOOD_PER_WORKER_PER_TICK
            if state.planks >= planks_needed:
                state.planks -= planks_needed
                state.gold += workers * config.MARKET_GOLD_WITH_PLANKS_PER_WORKER_PER_TICK * market_mult
            elif state.planks > 0:
                # Partial planks: use planks first, then wood for the remainder
                planks_fraction = state.planks / planks_needed
                state.gold += workers * config.MARKET_GOLD_WITH_PLANKS_PER_WORKER_PER_TICK * market_mult * planks_fraction
                state.planks = 0.0
                # Fill the remaining fraction with wood
                remaining_fraction = 1.0 - planks_fraction
                wood_for_remainder = wood_needed * remaining_fraction
                if state.wood >= wood_for_remainder:
                    state.wood -= wood_for_remainder
                    state.gold += workers * config.MARKET_GOLD_PER_WORKER_PER_TICK * market_mult * remaining_fraction
                elif wood_needed > 0:
                    wood_frac = state.wood / wood_needed
                    state.gold += workers * config.MARKET_GOLD_PER_WORKER_PER_TICK * market_mult * wood_frac
                    state.wood = 0.0
            elif state.wood >= wood_needed:
                state.wood -= wood_needed
                state.gold += workers * config.MARKET_GOLD_PER_WORKER_PER_TICK * market_mult
            else:
                # Partial wood operation
                if wood_needed > 0:
                    fraction = state.wood / wood_needed
                    state.gold += workers * config.MARKET_GOLD_PER_WORKER_PER_TICK * market_mult * fraction
                    state.wood = 0.0


# ---------------------------------------------------------------------------
# Internal helpers — consumption
# ---------------------------------------------------------------------------

def _process_consumption(state: GameState) -> None:
    """
    Each colonist consumes food. If food runs out colonists starve and die
    (removed from the roster in the order they were added).
    Winter doubles food consumption.
    """
    food_per_colonist = config.FOOD_PER_COLONIST_PER_TICK * state.food_consumption_mult
    if _is_winter(state.tick):
        food_per_colonist *= config.WINTER_FOOD_MULT
    food_needed = state.colonist_count * food_per_colonist

    if state.food >= food_needed:
        state.food -= food_needed
    else:
        # Not enough food — work out how many colonists go unfed
        fed = int(state.food / food_per_colonist) if food_per_colonist > 0 else 0
        starving_count = state.colonist_count - fed
        state.food = 0.0

        # Increment starvation counter and remove the unfed colonists
        state.starvation_events += starving_count
        # Remove idle colonists first, then assigned ones
        _remove_starving_colonists(state, starving_count)


def _remove_starving_colonists(state: GameState, count: int) -> None:
    """Remove `count` colonists, preferring idle ones first."""
    to_remove: list[Colonist] = []

    # Collect idle colonists first
    idle = [c for c in state.colonists if c.assigned_building_id is None]
    to_remove.extend(idle[:count])

    if len(to_remove) < count:
        remaining = count - len(to_remove)
        assigned = [c for c in state.colonists if c.assigned_building_id is not None]
        to_remove.extend(assigned[:remaining])

    # Actually remove them and update building worker counts
    remove_ids = {c.id for c in to_remove}
    for colonist in to_remove:
        if colonist.assigned_building_id is not None:
            building = state.building_by_id(colonist.assigned_building_id)
            if building and building.workers_assigned > 0:
                building.workers_assigned -= 1

    state.colonists = [c for c in state.colonists if c.id not in remove_ids]


# ---------------------------------------------------------------------------
# Internal helpers — arrivals
# ---------------------------------------------------------------------------

def _add_colonist(state: GameState) -> Colonist:
    colonist = Colonist(id=state.next_colonist_id)
    state.next_colonist_id += 1
    state.colonists.append(colonist)
    return colonist


def _assign_colonist_to_building(
    state: GameState, building_id: int, count: int = 1
) -> None:
    """Assign up to `count` idle colonists to a building (startup helper)."""
    building = state.building_by_id(building_id)
    if building is None:
        return
    max_workers = _max_workers_for(building.building_type)

    assigned = 0
    for colonist in state.colonists:
        if assigned >= count:
            break
        if colonist.assigned_building_id is not None:
            continue
        if building.workers_assigned >= max_workers:
            break
        colonist.assigned_building_id = building_id
        building.workers_assigned += 1
        assigned += 1


# ---------------------------------------------------------------------------
# Internal helpers — actions
# ---------------------------------------------------------------------------

def _handle_assign_worker(state: GameState, action: ActionAssignWorker) -> None:
    building = state.building_by_id(action.building_id)
    if building is None:
        return

    max_workers = _max_workers_for(building.building_type)

    if action.delta == 1:
        # Find an idle colonist and assign them
        if building.workers_assigned >= max_workers:
            return
        idle = next((c for c in state.colonists if c.assigned_building_id is None), None)
        if idle is None:
            return
        idle.assigned_building_id = action.building_id
        building.workers_assigned += 1

    elif action.delta == -1:
        # Remove one worker from this building
        if building.workers_assigned <= 0:
            return
        assigned = next(
            (c for c in state.colonists if c.assigned_building_id == action.building_id),
            None,
        )
        if assigned is None:
            return
        assigned.assigned_building_id = None
        building.workers_assigned -= 1


def _handle_build_building(state: GameState, action: ActionBuildBuilding) -> None:
    cost = _build_cost_for(action.building_type)
    if state.wood < cost:
        return  # Cannot afford — silently ignore

    state.wood -= cost
    building = Building(
        id=state.next_building_id,
        building_type=action.building_type,
        workers_assigned=0,
    )
    state.next_building_id += 1
    state.buildings.append(building)


def _handle_set_speed(state: GameState, action: ActionSetSpeed) -> None:
    if action.speed_multiplier in config.SPEED_MULTIPLIERS:
        state.speed_multiplier = action.speed_multiplier


# ---------------------------------------------------------------------------
# Internal helpers — lookups from config
# ---------------------------------------------------------------------------

def _max_workers_for(btype: BuildingType) -> int:
    return {
        BuildingType.FARM:        config.FARM_MAX_WORKERS,
        BuildingType.LUMBER_MILL: config.LUMBERMILL_MAX_WORKERS,
        BuildingType.MARKET:      config.MARKET_MAX_WORKERS,
        BuildingType.QUARRY:      config.QUARRY_MAX_WORKERS,
        BuildingType.SAWMILL:     config.SAWMILL_MAX_WORKERS,
    }[btype]


def _build_cost_for(btype: BuildingType) -> float:
    return {
        BuildingType.FARM:        config.FARM_BUILD_COST_WOOD,
        BuildingType.LUMBER_MILL: config.LUMBERMILL_BUILD_COST_WOOD,
        BuildingType.MARKET:      config.MARKET_BUILD_COST_WOOD,
        BuildingType.QUARRY:      config.QUARRY_BUILD_COST_WOOD,
        BuildingType.SAWMILL:     config.SAWMILL_BUILD_COST_WOOD,
    }[btype]


def _handle_research_tech(state: GameState, action: ActionResearchTech) -> None:
    # Already researched?
    if action.tech_id in state.researched_tech_ids:
        return
    # Find the tech definition
    tech_def = next(
        (t for t in config.RESEARCH_TECHS if t["tech_id"] == action.tech_id), None
    )
    if tech_def is None:
        return
    cost = tech_def["gold_cost"]
    if state.gold < cost:
        return
    state.gold -= cost
    state.researched_tech_ids.append(action.tech_id)


def _handle_recruit_citizen(state: GameState) -> None:
    if state.food < config.RECRUIT_CITIZEN_FOOD_COST:
        return
    state.food -= config.RECRUIT_CITIZEN_FOOD_COST
    colonist = _add_colonist(state)
    if state.colonist_count > state.peak_colonists:
        state.peak_colonists = state.colonist_count


# ---------------------------------------------------------------------------
# Win / lose check
# ---------------------------------------------------------------------------

def _check_endgame(state: GameState) -> None:
    if state.status != GameStatus.PLAYING:
        return  # already set (e.g. LOSE_TRIBUTE); don't overwrite
    if state.gold >= config.WIN_GOLD_TARGET:
        state.status = GameStatus.WIN
    elif state.colonist_count == 0:
        state.status = GameStatus.LOSE


# ---------------------------------------------------------------------------
# Season / tribute helpers
# ---------------------------------------------------------------------------

def _is_winter(tick: int) -> bool:
    return (tick % config.SEASON_CYCLE_TICKS) >= (config.SEASON_CYCLE_TICKS - config.WINTER_LENGTH_TICKS)


def get_season(tick: int) -> str:
    """Return current season name for display."""
    pos = tick % config.SEASON_CYCLE_TICKS
    if pos < 100:
        return "Spring"
    elif pos < 200:
        return "Summer"
    elif pos < config.SEASON_CYCLE_TICKS - config.WINTER_LENGTH_TICKS:
        return "Autumn"
    else:
        return "Winter"


def _compute_tribute_schedule(run_number: int) -> list:
    """Pre-compute tribute amounts for a full run (50 tributes = 10000 ticks)."""
    return [
        config.TRIBUTE_BASE
        + (run_number - 1) * config.TRIBUTE_RUN_INCREMENT
        + i * config.TRIBUTE_ESCALATION
        for i in range(50)
    ]


def _check_tribute(state: GameState) -> None:
    """Deduct tribute or set LOSE_TRIBUTE if the player can't pay."""
    if state.tributes_paid >= len(state.tribute_schedule):
        return
    due = state.tribute_schedule[state.tributes_paid]
    if state.gold >= due:
        state.gold -= due
        state.tributes_paid += 1
    else:
        state.status = GameStatus.LOSE_TRIBUTE
