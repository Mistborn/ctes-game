"""
engine.py — Pure game logic. No Pygame. No renderer imports. Ever.

Public API:
    new_game()          -> GameState
    tick(state)         -> GameState   (advances simulation by one tick)
    apply_action(state, action) -> GameState
    get_state(state)    -> dict        (snapshot for renderer / agent)
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from game.core import config
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionExploreHex,
    ActionFightBoss,
    ActionRecruitCitizen,
    ActionResearchTech,
    ActionSetSpeed,
    ActionTrainSoldier,
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

        # Starting colonist count
        if "extra_colonists_2" in unlocked:
            starting_colonists = 7
        else:
            starting_colonists = config.STARTING_COLONISTS

        # Hearty colonists: -10% food consumption
        if "hearty_colonists" in unlocked:
            state.food_consumption_mult = 0.9

        # Trade connections: +15% market gold
        if "trade_connections" in unlocked:
            state.market_gold_bonus_mult = 1.15

        # Automation upgrades
        if "auto_hire" in unlocked:
            state.auto_hire_unlocked = True
            state.auto_hire_enabled = True
        if "auto_assign" in unlocked:
            state.auto_assign_unlocked = True
            state.auto_assign_enabled = True
        if "auto_research" in unlocked:
            state.auto_research_unlocked = True
            state.auto_research_enabled = True
        if "auto_explore" in unlocked:
            state.auto_explore_unlocked = True
            state.auto_explore_enabled = True
        if "auto_balance" in unlocked:
            state.auto_balance_unlocked = True
            state.auto_balance_enabled = True
        if "auto_build" in unlocked:
            state.auto_build_unlocked = True
            state.auto_build_enabled = True
    else:
        starting_colonists = config.STARTING_COLONISTS

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

    # Decrement boss fight cooldown
    if state.boss_fight_cooldown > 0:
        state.boss_fight_cooldown -= 1

    # Detect season transitions and add log messages
    if state.tick > 1:
        prev_season = get_season(state.tick - 1)
        curr_season = get_season(state.tick)
        if curr_season != prev_season:
            _add_season_log(state, curr_season)

    # Seasonal harvest bonuses (fire once at each season transition)
    is_winter = _is_winter_for_state(state)
    if not state.last_season_was_winter and is_winter:
        # Summer → Winter: harvest festival
        if state.food > config.HARVEST_FOOD_THRESHOLD:
            amount = int(state.food * config.HARVEST_GOLD_FRACTION)
            state.gold += amount
            state.info_log.append([state.tick, f"Harvest festival! Gained {amount} gold from food surplus.", "info"])
            if len(state.info_log) > config.INFO_LOG_MAX_ENTRIES:
                state.info_log = state.info_log[-config.INFO_LOG_MAX_ENTRIES :]
    elif state.last_season_was_winter and not is_winter:
        # Winter → Summer: spring crafting
        if state.wood > config.SPRING_WOOD_THRESHOLD:
            amount = int(state.wood * config.SPRING_PLANKS_FRACTION)
            state.planks += amount
            state.info_log.append([state.tick, f"Spring crafting! Gained {amount} planks from stored wood.", "info"])
            if len(state.info_log) > config.INFO_LOG_MAX_ENTRIES:
                state.info_log = state.info_log[-config.INFO_LOG_MAX_ENTRIES :]
    state.last_season_was_winter = is_winter

    # Snapshot resources before tick for rate calculation
    food_before = state.food
    wood_before = state.wood
    gold_before = state.gold
    stone_before = state.stone
    planks_before = state.planks
    iron_before = state.iron

    # 1. Buildings produce resources
    _process_production(state)

    # 1b. Explored hex passive income
    _process_hex_passive_income(state)

    # 2. Colonists consume food
    _process_consumption(state)

    # 3. Apply resource caps
    state.food = min(state.food, config.FOOD_CAP)
    state.wood = min(state.wood, config.WOOD_CAP)
    state.gold = min(state.gold, config.GOLD_CAP)
    state.stone = min(state.stone, config.STONE_CAP)
    state.planks = min(state.planks, config.PLANKS_CAP)
    state.iron = min(state.iron, config.IRON_CAP)
    # Resources cannot go below zero
    state.food = max(state.food, 0.0)
    state.wood = max(state.wood, 0.0)
    state.gold = max(state.gold, 0.0)
    state.stone = max(state.stone, 0.0)
    state.planks = max(state.planks, 0.0)
    state.iron = max(state.iron, 0.0)

    # 4. Update per-tick rate display values
    state.food_rate = state.food - food_before
    state.wood_rate = state.wood - wood_before
    state.gold_rate = state.gold - gold_before
    state.stone_rate = state.stone - stone_before
    state.planks_rate = state.planks - planks_before
    state.iron_rate = state.iron - iron_before

    # 5. Track total gold produced (for LP)
    if state.gold_rate > 0:
        state.total_gold_earned += state.gold_rate

    # 6. Automation: auto-hire and auto-assign
    if state.auto_hire_enabled and state.food >= config.RECRUIT_CITIZEN_FOOD_COST:
        _handle_recruit_citizen(state)
    if state.auto_assign_enabled:
        _auto_assign_idle_colonists(state)
    if state.auto_research_enabled:
        _auto_research(state)
    if state.auto_explore_enabled and state.hex_map_unlocked:
        _auto_explore(state)
    if state.auto_balance_enabled:
        _auto_balance(state)
    if state.auto_build_enabled:
        _auto_build(state)

    # 7. Tutorial hints
    _check_tutorial_hints(state)

    # 7b. Milestone: colonist count threshold
    if state.colonist_count >= 10:
        _trigger_milestone(state, "colonists_10", "10 colonists reached!")

    # 8. Win / Lose checks
    _check_endgame(state)

    return state


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------


def apply_action(state: GameState, action) -> GameState:
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
    elif isinstance(action, ActionExploreHex):
        _handle_explore_hex(state, action)
    elif isinstance(action, ActionTrainSoldier):
        _handle_train_soldier(state)
    elif isinstance(action, ActionFightBoss):
        _handle_fight_boss(state, action)

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
    farm_mult = config.RESEARCH_CROP_ROTATION_FARM_MULT if "crop_rotation" in researched else 1.0
    tool_mult = config.RESEARCH_REINFORCED_TOOLS_MULT if "reinforced_tools" in researched else 1.0
    market_mult = (
        config.RESEARCH_TRADE_ROUTES_MARKET_MULT if "trade_routes" in researched else 1.0
    ) * state.market_gold_bonus_mult
    sawmill_mult = config.RESEARCH_STONE_MASONRY_SAWMILL_MULT if "stone_masonry" in researched else 1.0
    winter_food_mult = config.WINTER_FOOD_PRODUCTION_MULT if _is_winter_for_state(state) else 1.0

    # Curse: drought — farm production multiplier
    if "drought" in state.active_curses:
        drought_curse = next(c for c in config.CURSES if c["curse_id"] == "drought")
        farm_mult *= drought_curse["effect_value"]

    for building in state.buildings:
        workers = building.workers_assigned
        btype = building.building_type

        # Passive income (applied regardless of worker count)
        if btype == BuildingType.FARM:
            state.food += config.FARM_PASSIVE_FOOD_PER_TICK * farm_mult * passive_mult * winter_food_mult
        elif btype == BuildingType.LUMBER_MILL:
            state.wood += config.LUMBERMILL_PASSIVE_WOOD_PER_TICK * tool_mult * passive_mult
        elif btype == BuildingType.QUARRY:
            state.stone += config.QUARRY_PASSIVE_STONE_PER_TICK * tool_mult * passive_mult

        # Worker-based production
        if workers == 0:
            continue

        if btype == BuildingType.FARM:
            state.food += workers * config.FARM_FOOD_PER_WORKER_PER_TICK * farm_mult * winter_food_mult

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

        elif btype == BuildingType.IRON_MINE:
            state.iron += workers * config.IRON_MINE_PRODUCTION

        elif btype == BuildingType.MARKET:
            # Prefer Planks over Wood for gold production (better rate)
            planks_needed = workers * config.MARKET_PLANKS_PER_WORKER_PER_TICK
            wood_needed = workers * config.MARKET_WOOD_PER_WORKER_PER_TICK
            if state.planks >= planks_needed:
                state.planks -= planks_needed
                state.gold += workers * config.MARKET_GOLD_WITH_PLANKS_PER_WORKER_PER_TICK * market_mult
            elif state.planks > 0:
                # Partial planks: use planks first, then wood for the remainder
                planks_fraction = state.planks / planks_needed
                state.gold += (
                    workers * config.MARKET_GOLD_WITH_PLANKS_PER_WORKER_PER_TICK * market_mult * planks_fraction
                )
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
# Internal helpers — hex passive income
# ---------------------------------------------------------------------------


def _process_hex_passive_income(state: GameState) -> None:
    """Apply per-tick passive income from all explored hexes."""
    if not state.hex_map_unlocked or not state.hex_tiles:
        return
    for tile in state.hex_tiles.values():
        if not tile.get("explored", False):
            continue
        terrain = tile.get("terrain", "")
        if terrain == "colony":
            continue
        for resource, amount in config.HEX_PASSIVE_INCOME.get(terrain, {}).items():
            if resource == "food":
                state.food += amount
            elif resource == "wood":
                state.wood += amount
            elif resource == "gold":
                state.gold += amount
            elif resource == "stone":
                state.stone += amount
            elif resource == "iron":
                state.iron += amount


# ---------------------------------------------------------------------------
# Internal helpers — consumption
# ---------------------------------------------------------------------------


def _process_consumption(state: GameState) -> None:
    """
    Each colonist consumes food. If food runs out colonists starve and die
    (removed from the roster in the order they were added).
    Winter halves food production instead of increasing consumption.
    """
    food_per_colonist = config.FOOD_PER_COLONIST_PER_TICK * state.food_consumption_mult
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
    # Purge any None entries that LLM-generated strategy code may have injected
    state.colonists = [c for c in state.colonists if c is not None]

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


def _assign_colonist_to_building(state: GameState, building_id: int, count: int = 1) -> None:
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


def _auto_assign_idle_colonists(state: GameState) -> None:
    """Assign each idle colonist to the first building with an open slot."""
    for colonist in state.colonists:
        if colonist is None or colonist.assigned_building_id is not None:
            continue
        for building in state.buildings:
            max_w = _max_workers_for(building.building_type)
            if building.workers_assigned < max_w:
                colonist.assigned_building_id = building.id
                building.workers_assigned += 1
                break


def _auto_research(state: GameState) -> None:
    """Research the cheapest available tech when gold exceeds 1.5x its cost."""
    unresearched = [t for t in config.RESEARCH_TECHS if t["tech_id"] not in state.researched_tech_ids]
    if not unresearched:
        return
    cheapest = min(unresearched, key=lambda t: t["gold_cost"])
    if cheapest["gold_cost"] * 1.5 <= state.gold:
        _handle_research_tech(state, ActionResearchTech(tech_id=cheapest["tech_id"]))


def _auto_explore(state: GameState) -> None:
    """Every AUTO_EXPLORE_INTERVAL ticks, explore the cheapest adjacent unexplored hex if resources allow."""
    state.auto_explore_timer += 1
    if state.auto_explore_timer < config.AUTO_EXPLORE_INTERVAL:
        return
    state.auto_explore_timer = 0

    # Collect explorable hexes: unexplored with at least one explored neighbor
    explorable = []
    for key, tile in state.hex_tiles.items():
        if tile.get("explored"):
            continue
        q, r = (int(x) for x in key.split(","))
        if not _has_explored_neighbor(state, q, r):
            continue
        ring = _ring_distance(q, r)
        base_cost = config.HEX_EXPLORE_COST_BY_RING.get(ring, {})
        if "scarce_lands" in state.active_curses:
            curse = next(c for c in config.CURSES if c["curse_id"] == "scarce_lands")
            cost = {k: v * curse["effect_value"] for k, v in base_cost.items()}
        else:
            cost = base_cost
        total_cost = sum(cost.values())
        explorable.append((total_cost, q, r, cost))

    if not explorable:
        return

    # Sort by total cost ascending, pick cheapest
    explorable.sort(key=lambda x: x[0])
    total_cost, q, r, cost = explorable[0]

    # Attempt to explore if resources suffice
    if (
        state.wood >= cost.get("wood", 0)
        and state.stone >= cost.get("stone", 0)
        and state.gold >= cost.get("gold", 0)
        and state.planks >= cost.get("planks", 0)
    ):
        _handle_explore_hex(state, ActionExploreHex(q=q, r=r))


def _auto_balance(state: GameState) -> None:
    """Every AUTO_BALANCE_INTERVAL ticks, rebalance workers based on food level."""
    state.auto_balance_timer += 1
    if state.auto_balance_timer < config.AUTO_BALANCE_INTERVAL:
        return
    state.auto_balance_timer = 0

    farms = [b for b in state.buildings if b.building_type == BuildingType.FARM]
    if not farms:
        return
    farm = farms[0]

    if state.food < config.AUTO_BALANCE_LOW_FOOD:
        # Move one worker from least-critical building (market > sawmill > quarry) to farm
        max_farm_workers = _max_workers_for(BuildingType.FARM)
        if farm.workers_assigned >= max_farm_workers:
            return
        for btype in [BuildingType.MARKET, BuildingType.SAWMILL, BuildingType.QUARRY]:
            source = next(
                (b for b in state.buildings if b.building_type == btype and b.workers_assigned > 0),
                None,
            )
            if source is not None:
                worker = next(
                    (c for c in state.colonists if c is not None and c.assigned_building_id == source.id),
                    None,
                )
                if worker is not None:
                    worker.assigned_building_id = farm.id
                    source.workers_assigned -= 1
                    farm.workers_assigned += 1
                    return

    elif state.food > config.AUTO_BALANCE_HIGH_FOOD and farm.workers_assigned > config.AUTO_BALANCE_MIN_FARM_WORKERS:
        # Move one farm worker to a building with open slots
        for building in state.buildings:
            if building.id == farm.id:
                continue
            max_w = _max_workers_for(building.building_type)
            if max_w == 0:
                continue
            if building.workers_assigned < max_w:
                worker = next(
                    (c for c in state.colonists if c is not None and c.assigned_building_id == farm.id),
                    None,
                )
                if worker is not None:
                    worker.assigned_building_id = building.id
                    farm.workers_assigned -= 1
                    building.workers_assigned += 1
                    return


def _auto_build(state: GameState) -> None:
    """Every AUTO_BUILD_INTERVAL ticks, build a second copy of the most productive building
    type when resources are AUTO_BUILD_COST_MULTIPLIER x the next build cost and there are
    idle colonists."""
    state.auto_build_timer += 1
    if state.auto_build_timer < config.AUTO_BUILD_INTERVAL:
        return
    state.auto_build_timer = 0

    if state.idle_colonists == 0:
        return

    production_rates = {
        BuildingType.FARM: config.FARM_FOOD_PER_WORKER_PER_TICK,
        BuildingType.LUMBER_MILL: config.LUMBERMILL_WOOD_PER_WORKER_PER_TICK,
        BuildingType.MARKET: config.MARKET_GOLD_PER_WORKER_PER_TICK,
        BuildingType.QUARRY: config.QUARRY_STONE_PER_WORKER_PER_TICK,
        BuildingType.SAWMILL: config.SAWMILL_PLANKS_PER_WORKER_PER_TICK,
        BuildingType.IRON_MINE: config.IRON_MINE_PRODUCTION,
    }

    # Compute total output per building type (sum of workers * production_rate)
    type_outputs: dict[BuildingType, float] = {}
    for building in state.buildings:
        btype = building.building_type
        rate = production_rates.get(btype)
        if rate is None:
            continue
        type_outputs[btype] = type_outputs.get(btype, 0.0) + building.workers_assigned * rate

    if not type_outputs:
        return

    # Find building type with highest total output
    best_type = max(type_outputs, key=lambda bt: type_outputs[bt])

    # Check if resources >= AUTO_BUILD_COST_MULTIPLIER * next build cost
    existing = sum(1 for b in state.buildings if b.building_type == best_type)
    multiplier = config.AUTO_BUILD_COST_MULTIPLIER
    if best_type == BuildingType.IRON_MINE:
        stone_cost = config.IRON_MINE_BUILD_COST.get("stone", 0) * (2**existing)
        if state.stone < stone_cost * multiplier:
            return
    else:
        wood_cost = _build_cost_for(best_type) * (2**existing)
        if state.wood < wood_cost * multiplier:
            return

    _handle_build_building(state, ActionBuildBuilding(building_type=best_type))


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
    # Check boss gate: if this building type is listed in any BOSS_BUILDING_GATES entry,
    # it must have been unlocked by defeating the corresponding boss first.
    all_gated = [v for values in config.BOSS_BUILDING_GATES.values() for v in values]
    if action.building_type.value in all_gated and action.building_type.value not in state.boss_unlocked_buildings:
        return

    existing = sum(1 for b in state.buildings if b.building_type == action.building_type)

    # Multi-resource buildings handled separately
    if action.building_type == BuildingType.IRON_MINE:
        stone_cost = config.IRON_MINE_BUILD_COST.get("stone", 0) * (2**existing)
        if state.stone < stone_cost:
            return
        state.stone -= stone_cost
    elif action.building_type == BuildingType.BARRACKS:
        wood_cost = config.BARRACKS_BUILD_COST.get("wood", 0) * (2**existing)
        iron_cost = config.BARRACKS_BUILD_COST.get("iron", 0) * (2**existing)
        if state.wood < wood_cost or state.iron < iron_cost:
            return
        state.wood -= wood_cost
        state.iron -= iron_cost
    else:
        cost = _build_cost_for(action.building_type) * (2**existing)
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

    if action.building_type == BuildingType.MARKET:
        _trigger_milestone(state, "first_market", "First Market built!")


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
        BuildingType.QUARRY: config.QUARRY_MAX_WORKERS,
        BuildingType.SAWMILL: config.SAWMILL_MAX_WORKERS,
        BuildingType.IRON_MINE: config.IRON_MINE_MAX_WORKERS,
        BuildingType.BARRACKS: 0,  # Barracks has no workers
    }.get(btype, 0)


def _build_cost_for(btype: BuildingType) -> float:
    """Returns the wood-only build cost for simple buildings. Returns 0 for multi-resource buildings."""
    return {
        BuildingType.FARM: config.FARM_BUILD_COST_WOOD,
        BuildingType.LUMBER_MILL: config.LUMBERMILL_BUILD_COST_WOOD,
        BuildingType.MARKET: config.MARKET_BUILD_COST_WOOD,
        BuildingType.QUARRY: config.QUARRY_BUILD_COST_WOOD,
        BuildingType.SAWMILL: config.SAWMILL_BUILD_COST_WOOD,
    }.get(btype, 0.0)


def _handle_research_tech(state: GameState, action: ActionResearchTech) -> None:
    # Already researched?
    if action.tech_id in state.researched_tech_ids:
        return
    # Find the tech definition
    tech_def = next((t for t in config.RESEARCH_TECHS if t["tech_id"] == action.tech_id), None)
    if tech_def is None:
        return
    cost = tech_def["gold_cost"]
    if state.gold < cost:
        return
    state.gold -= cost
    state.researched_tech_ids.append(action.tech_id)
    _trigger_milestone(state, f"research_{action.tech_id}", f"Research complete: {tech_def['name']}!")
    # Initialize hex map when cartography is researched
    if action.tech_id == "cartography" and not state.hex_tiles:
        _initialize_hex_map(state)


def _colonist_recruit_cost(state: GameState) -> int:
    extra = state.colonist_count - config.STARTING_COLONISTS
    return round(config.RECRUIT_CITIZEN_FOOD_COST * (config.COLONIST_COST_SCALE**extra))


def _handle_recruit_citizen(state: GameState) -> None:
    cost = _colonist_recruit_cost(state)
    if state.food < cost:
        return
    state.food -= cost
    _add_colonist(state)
    if state.colonist_count > state.peak_colonists:
        state.peak_colonists = state.colonist_count


# ---------------------------------------------------------------------------
# Military — train soldiers and fight boss
# ---------------------------------------------------------------------------


def _handle_train_soldier(state: GameState) -> None:
    if not state.has_barracks:
        return
    if state.soldiers >= config.BARRACKS_MAX_SOLDIERS:
        return
    food_cost = config.TRAIN_SOLDIER_COST["food"]
    iron_cost = config.TRAIN_SOLDIER_COST["iron"]
    if state.food < food_cost or state.iron < iron_cost:
        return
    state.food -= food_cost
    state.iron -= iron_cost
    state.soldiers += 1


def _handle_fight_boss(state: GameState, action: ActionFightBoss) -> None:
    if state.boss_fight_cooldown > 0:
        return
    key = f"{action.q},{action.r}"
    tile = state.hex_tiles.get(key)
    if tile is None or not tile.get("explored") or not tile.get("has_boss"):
        return
    if not state.has_barracks:
        return

    ring = _ring_distance(action.q, action.r)
    if ring == 4:
        min_soldiers = config.BOSS_TIER2_MIN_SOLDIERS
        strength = config.BOSS_TIER2_STRENGTH
        rewards = config.BOSS_TIER2_REWARD
        soldiers_lost_win = config.BOSS_TIER2_SOLDIERS_LOST_WIN
        soldiers_lost_lose = config.BOSS_TIER2_SOLDIERS_LOST_LOSE
    else:
        min_soldiers = config.BOSS_MIN_SOLDIERS
        strength = config.BOSS_STRENGTH
        rewards = config.BOSS_WIN_REWARDS
        soldiers_lost_win = config.BOSS_SOLDIERS_LOST_WIN
        soldiers_lost_lose = config.BOSS_SOLDIERS_LOST_LOSE

    if state.soldiers < min_soldiers:
        return

    win_prob = state.soldiers / (state.soldiers + strength)
    won = random.random() < win_prob

    if won:
        state.soldiers = max(0, state.soldiers - soldiers_lost_win)
        tile["has_boss"] = False
        state.boss_fights_won += 1
        _trigger_milestone(state, "boss_defeated", "Boss defeated!")
        if ring not in state.boss_rings_cleared:
            state.boss_rings_cleared.append(ring)
        gate_entries = config.BOSS_BUILDING_GATES.get(ring, [])
        for entry in gate_entries:
            if entry not in state.boss_unlocked_buildings:
                state.boss_unlocked_buildings.append(entry)
        state.gold = min(state.gold + rewards.get("gold", 0), config.GOLD_CAP)
        state.stone = min(state.stone + rewards.get("stone", 0), config.STONE_CAP)
    else:
        state.soldiers = max(0, state.soldiers - soldiers_lost_lose)
        state.boss_fight_cooldown = config.BOSS_FIGHT_COOLDOWN_TICKS


# ---------------------------------------------------------------------------
# Hex world map
# ---------------------------------------------------------------------------


def _ring_distance(q: int, r: int) -> int:
    return max(abs(q), abs(r), abs(q + r))


def _axial_neighbors(q: int, r: int):
    return [(q + dq, r + dr) for dq, dr in [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]]


def _has_explored_neighbor(state: GameState, q: int, r: int) -> bool:
    for nq, nr in _axial_neighbors(q, r):
        tile = state.hex_tiles.get(f"{nq},{nr}")
        if tile and tile.get("explored"):
            return True
    return False


def _initialize_hex_map(state: GameState) -> None:
    terrain_types = list(config.HEX_TERRAIN_WEIGHTS.keys())
    weights = [config.HEX_TERRAIN_WEIGHTS[t] for t in terrain_types]
    rng = random.Random(state.run_number * 99991 + 12345)

    radius = config.HEX_MAP_RADIUS

    # First pass: assign terrain to every hex
    tiles: dict[str, dict] = {}
    ring2_keys: list[str] = []
    ring4_keys: list[str] = []
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            key = f"{q},{r}"
            if q == 0 and r == 0:
                tiles[key] = {"terrain": "colony", "explored": True, "has_boss": False}
            else:
                terrain = rng.choices(terrain_types, weights=weights)[0]
                ring = max(abs(q), abs(r), abs(q + r))
                tiles[key] = {"terrain": terrain, "explored": False, "has_boss": False}
                if ring == 2:
                    ring2_keys.append(key)
                elif ring == 4:
                    ring4_keys.append(key)

    # Guarantee exactly one boss on a random ring-2 hex (tier 1 boss)
    if ring2_keys:
        boss_key = rng.choice(ring2_keys)
        tiles[boss_key]["has_boss"] = True

    # Guarantee exactly one boss on a random ring-4 hex (tier 2 boss)
    if ring4_keys:
        boss_key = rng.choice(ring4_keys)
        tiles[boss_key]["has_boss"] = True

    state.hex_tiles = tiles


def _handle_explore_hex(state: GameState, action: ActionExploreHex) -> None:
    key = f"{action.q},{action.r}"
    tile = state.hex_tiles.get(key)
    if tile is None or tile.get("explored"):
        return

    ring = _ring_distance(action.q, action.r)
    if not _has_explored_neighbor(state, action.q, action.r):
        return

    base_cost = config.HEX_EXPLORE_COST_BY_RING.get(ring, {})
    if "scarce_lands" in state.active_curses:
        curse = next(c for c in config.CURSES if c["curse_id"] == "scarce_lands")
        cost = {k: v * curse["effect_value"] for k, v in base_cost.items()}
    else:
        cost = base_cost
    if (
        state.wood < cost.get("wood", 0)
        or state.stone < cost.get("stone", 0)
        or state.gold < cost.get("gold", 0)
        or state.planks < cost.get("planks", 0)
    ):
        return

    state.wood -= cost.get("wood", 0)
    state.stone -= cost.get("stone", 0)
    state.gold -= cost.get("gold", 0)
    state.planks -= cost.get("planks", 0)

    tile["explored"] = True
    _trigger_milestone(state, "first_hex_explored", "First hex explored!")

    rewards = config.HEX_TERRAIN_REWARDS.get(tile["terrain"], {})
    state.food = min(state.food + rewards.get("food", 0), config.FOOD_CAP)
    state.wood = min(state.wood + rewards.get("wood", 0), config.WOOD_CAP)
    state.gold = min(state.gold + rewards.get("gold", 0), config.GOLD_CAP)
    state.stone = min(state.stone + rewards.get("stone", 0), config.STONE_CAP)
    state.planks = min(state.planks + rewards.get("planks", 0), config.PLANKS_CAP)

    # Check for one-time hex events (only fires once per tile, even across save/load)
    if key not in state.triggered_hex_events:
        terrain = tile["terrain"]
        events = config.HEX_EVENTS.get(terrain, [])
        for event in events:
            if random.random() < event["probability"]:
                effects = event["effects"]
                # Wandering Merchant requires minimum wood to trigger the trade
                if event["event_id"] == "wandering_merchant":
                    if state.wood < config.HEX_EVENT_MERCHANT_MIN_WOOD:
                        break
                # Apply resource effects
                state.food = min(max(state.food + effects.get("food", 0), 0.0), config.FOOD_CAP)
                state.wood = min(max(state.wood + effects.get("wood", 0), 0.0), config.WOOD_CAP)
                state.gold = min(max(state.gold + effects.get("gold", 0), 0.0), config.GOLD_CAP)
                state.stone = min(max(state.stone + effects.get("stone", 0), 0.0), config.STONE_CAP)
                state.planks = min(max(state.planks + effects.get("planks", 0), 0.0), config.PLANKS_CAP)
                # Special: free colonist
                if effects.get("colonists", 0) > 0:
                    for _ in range(effects["colonists"]):
                        _add_colonist(state)
                        if state.colonist_count > state.peak_colonists:
                            state.peak_colonists = state.colonist_count
                # Log the event
                state.info_log.append([state.tick, event["description"], "info"])
                if len(state.info_log) > config.INFO_LOG_MAX_ENTRIES:
                    state.info_log = state.info_log[-config.INFO_LOG_MAX_ENTRIES :]
                state.triggered_hex_events.append(key)
                break  # Only one event per hex


# ---------------------------------------------------------------------------
# Tutorial hints
# ---------------------------------------------------------------------------


def _check_tutorial_hints(state: GameState) -> None:
    """Fire any tutorial hints whose conditions are met (once per hint per run)."""
    shown = set(state.shown_hints)

    def _fire(hint_id: str, message: str) -> None:
        state.shown_hints.append(hint_id)
        state.info_log.append([state.tick, message, "info"])
        if len(state.info_log) > config.INFO_LOG_MAX_ENTRIES:
            state.info_log = state.info_log[-config.INFO_LOG_MAX_ENTRIES :]

    hint = config.TUTORIAL_HINTS[0]  # assign_workers
    if hint["hint_id"] not in shown and state.tick <= 3:
        _fire(hint["hint_id"], hint["message"])
        shown.add(hint["hint_id"])

    hint = config.TUTORIAL_HINTS[1]  # build_market
    if hint["hint_id"] not in shown and state.wood > 50:
        has_market = any(b.building_type == BuildingType.MARKET for b in state.buildings)
        if not has_market:
            _fire(hint["hint_id"], hint["message"])
            shown.add(hint["hint_id"])

    hint = config.TUTORIAL_HINTS[2]  # research_tech
    if hint["hint_id"] not in shown and state.gold > 80 and not state.researched_tech_ids:
        _fire(hint["hint_id"], hint["message"])
        shown.add(hint["hint_id"])

    hint = config.TUTORIAL_HINTS[3]  # explore_hexes
    if hint["hint_id"] not in shown and "cartography" in state.researched_tech_ids:
        non_colony_explored = any(tile.get("explored") for key, tile in state.hex_tiles.items() if key != "0,0")
        if not non_colony_explored:
            _fire(hint["hint_id"], hint["message"])
            shown.add(hint["hint_id"])

    hint = config.TUTORIAL_HINTS[4]  # train_soldiers
    if hint["hint_id"] not in shown and state.soldiers == 0:
        boss_explored = any(tile.get("explored") and tile.get("has_boss") for tile in state.hex_tiles.values())
        if boss_explored:
            _fire(hint["hint_id"], hint["message"])
            shown.add(hint["hint_id"])

    hint = config.TUTORIAL_HINTS[5]  # gold_target_close
    if hint["hint_id"] not in shown and state.gold > 0.8 * state.win_gold_target:
        _fire(hint["hint_id"], hint["message"])
        shown.add(hint["hint_id"])


# ---------------------------------------------------------------------------
# Milestone helpers
# ---------------------------------------------------------------------------


def _trigger_milestone(state: GameState, milestone_id: str, message: str) -> None:
    """Append a milestone notification to info_log if not already triggered."""
    if milestone_id in state.triggered_milestones:
        return
    state.triggered_milestones.append(milestone_id)
    state.info_log.append([state.tick, message, "info"])
    if len(state.info_log) > config.INFO_LOG_MAX_ENTRIES:
        state.info_log = state.info_log[-config.INFO_LOG_MAX_ENTRIES :]


# ---------------------------------------------------------------------------
# Win / lose check
# ---------------------------------------------------------------------------


def _check_endgame(state: GameState) -> None:
    if state.status != GameStatus.PLAYING:
        return
    if state.gold >= state.win_gold_target:
        state.status = GameStatus.WIN
    elif state.colonist_count == 0:
        state.status = GameStatus.LOSE


# ---------------------------------------------------------------------------
# Season helpers
# ---------------------------------------------------------------------------


def _add_season_log(state: GameState, season: str) -> None:
    """Append a seasonal event message to state.info_log."""
    messages = {
        "Autumn": ("Warning: Winter approaches — food production will be halved!", "warning"),
        "Winter": ("Winter has begun. Food production is halved.", "winter"),
        "Spring": ("Spring has arrived. Food production is restored.", "spring"),
        "Summer": ("Summer is here.", "summer"),
    }
    entry = messages.get(season)
    if entry is None:
        return
    state.info_log.append([state.tick, entry[0], entry[1]])
    if len(state.info_log) > config.INFO_LOG_MAX_ENTRIES:
        state.info_log = state.info_log[-config.INFO_LOG_MAX_ENTRIES :]


def _is_winter(tick: int) -> bool:
    return (tick % config.SEASON_CYCLE_TICKS) >= (config.SEASON_CYCLE_TICKS - config.WINTER_LENGTH_TICKS)


def _is_winter_for_state(state: GameState) -> bool:
    """Like _is_winter but respects the hard_winter curse (extends winter length)."""
    if "hard_winter" in state.active_curses:
        curse = next(c for c in config.CURSES if c["curse_id"] == "hard_winter")
        winter_length = round(config.WINTER_LENGTH_TICKS * curse["effect_value"])
    else:
        winter_length = config.WINTER_LENGTH_TICKS
    return (state.tick % config.SEASON_CYCLE_TICKS) >= (config.SEASON_CYCLE_TICKS - winter_length)


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
