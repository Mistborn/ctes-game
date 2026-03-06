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
from typing import Union

from game.core import config
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionSetSpeed,
    Building,
    BuildingType,
    Colonist,
    GameStatus,
)
from game.core.state import GameState


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def new_game() -> GameState:
    """Return a freshly initialised GameState with starting values."""
    state = GameState()

    # Spawn starting colonists
    for _ in range(config.STARTING_COLONISTS):
        _add_colonist(state)

    # Build the two starting buildings
    farm = Building(id=state.next_building_id, building_type=BuildingType.FARM)
    state.next_building_id += 1
    state.buildings.append(farm)

    mill = Building(id=state.next_building_id, building_type=BuildingType.LUMBER_MILL)
    state.next_building_id += 1
    state.buildings.append(mill)

    # Distribute starting workers: 3 on farm, 2 on lumber mill
    _assign_colonist_to_building(state, farm.id, count=3)
    _assign_colonist_to_building(state, mill.id, count=2)

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
    state.ticks_since_last_arrival_check += 1

    # Snapshot resources before tick for rate calculation
    food_before = state.food
    wood_before = state.wood
    gold_before = state.gold

    # 1. Buildings produce resources
    _process_production(state)

    # 2. Colonists consume food
    _process_consumption(state)

    # 3. Apply resource caps
    state.food = min(state.food, config.FOOD_CAP)
    state.wood = min(state.wood, config.WOOD_CAP)
    state.gold = min(state.gold, config.GOLD_CAP)
    # Resources cannot go below zero
    state.food = max(state.food, 0.0)
    state.wood = max(state.wood, 0.0)
    state.gold = max(state.gold, 0.0)

    # 4. Update per-tick rate display values
    state.food_rate = state.food - food_before
    state.wood_rate = state.wood - wood_before
    state.gold_rate = state.gold - gold_before

    # 5. Colonist arrival check
    if state.ticks_since_last_arrival_check >= config.COLONIST_ARRIVAL_INTERVAL_TICKS:
        state.ticks_since_last_arrival_check = 0
        if state.food > config.COLONIST_ARRIVAL_MIN_FOOD_SURPLUS:
            _add_colonist(state)
            if state.colonist_count > state.peak_colonists:
                state.peak_colonists = state.colonist_count

    # 6. Win / Lose checks
    _check_endgame(state)

    return state


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------

def apply_action(
    state: GameState,
    action: Union[ActionAssignWorker, ActionBuildBuilding, ActionSetSpeed],
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
    for building in state.buildings:
        workers = building.workers_assigned
        if workers == 0:
            continue

        btype = building.building_type

        if btype == BuildingType.FARM:
            state.food += workers * config.FARM_FOOD_PER_WORKER_PER_TICK

        elif btype == BuildingType.LUMBER_MILL:
            state.wood += workers * config.LUMBERMILL_WOOD_PER_WORKER_PER_TICK

        elif btype == BuildingType.MARKET:
            # Market converts Wood → Gold; needs enough wood to operate
            wood_needed = workers * config.MARKET_WOOD_PER_WORKER_PER_TICK
            if state.wood >= wood_needed:
                state.wood -= wood_needed
                state.gold += workers * config.MARKET_GOLD_PER_WORKER_PER_TICK
            else:
                # Partial operation: use all available wood proportionally
                if wood_needed > 0:
                    fraction = state.wood / wood_needed
                    state.gold += workers * config.MARKET_GOLD_PER_WORKER_PER_TICK * fraction
                    state.wood = 0.0


# ---------------------------------------------------------------------------
# Internal helpers — consumption
# ---------------------------------------------------------------------------

def _process_consumption(state: GameState) -> None:
    """
    Each colonist consumes food. If food runs out colonists starve and die
    (removed from the roster in the order they were added).
    """
    food_needed = state.colonist_count * config.FOOD_PER_COLONIST_PER_TICK

    if state.food >= food_needed:
        state.food -= food_needed
    else:
        # Not enough food — work out how many colonists go unfed
        fed = int(state.food / config.FOOD_PER_COLONIST_PER_TICK)
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
        BuildingType.FARM: config.FARM_MAX_WORKERS,
        BuildingType.LUMBER_MILL: config.LUMBERMILL_MAX_WORKERS,
        BuildingType.MARKET: config.MARKET_MAX_WORKERS,
    }[btype]


def _build_cost_for(btype: BuildingType) -> float:
    return {
        BuildingType.FARM: config.FARM_BUILD_COST_WOOD,
        BuildingType.LUMBER_MILL: config.LUMBERMILL_BUILD_COST_WOOD,
        BuildingType.MARKET: config.MARKET_BUILD_COST_WOOD,
    }[btype]


# ---------------------------------------------------------------------------
# Win / lose check
# ---------------------------------------------------------------------------

def _check_endgame(state: GameState) -> None:
    if state.gold >= config.WIN_GOLD_TARGET:
        state.status = GameStatus.WIN
    elif state.colonist_count == 0:
        state.status = GameStatus.LOSE
