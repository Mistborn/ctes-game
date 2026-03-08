"""
gen_save.py — Generate debug savegame files for playtesting.

Usage:
    uv run python gen_save.py [scenario]

Scenarios:
    mid_game   (default)  Market + Quarry + Sawmill, 10 colonists, world map open
    pre_boss              Full economy, Barracks, 10 soldiers, boss hex reachable

The generated files appear in saves/ and can be loaded from the main menu.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from game.core import engine
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionExploreHex,
    ActionRecruitCitizen,
    ActionResearchTech,
    BuildingType,
)
from game.core.save import save_game

SAVES_DIR = Path("saves")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bid(state, btype: BuildingType, index: int = 0):
    """Return the building id of the nth building of a type."""
    found = [b.id for b in state.buildings if b.building_type == btype]
    return found[index] if index < len(found) else None


def _add_workers(state, btype: BuildingType, count: int, index: int = 0):
    bid = _bid(state, btype, index)
    if bid is not None:
        for _ in range(count):
            engine.apply_action(state, ActionAssignWorker(building_id=bid, delta=+1))


def _build(state, btype: BuildingType):
    engine.apply_action(state, ActionBuildBuilding(building_type=btype))


def _recruit(state, n: int):
    for _ in range(n):
        state.food = max(state.food, 500.0)
        engine.apply_action(state, ActionRecruitCitizen())


def _research(state, *tech_ids: str):
    state.gold = max(state.gold, 5000.0)
    for tid in tech_ids:
        engine.apply_action(state, ActionResearchTech(tid))


def _explore(state, coords):
    for q, r in coords:
        engine.apply_action(state, ActionExploreHex(q=q, r=r))


RING1 = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
RING2 = [(2, 0), (2, -1), (2, -2), (1, -2), (0, -2), (-1, -1),
         (-2, 0), (-2, 1), (-2, 2), (-1, 2), (0, 2), (1, 1)]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_mid_game():
    """
    ~200 ticks in: market economy running, cartography unlocked, world map
    partially explored. Good starting point for testing economy balance.
    """
    state = engine.new_game()
    state.tick = 200

    # Comfortable mid-game resources
    state.food  = 80.0
    state.wood  = 150.0
    state.gold  = 120.0
    state.stone = 50.0
    state.planks = 20.0

    # 5 → 10 colonists
    _recruit(state, 5)

    # Build economy buildings
    state.wood = 300.0
    _build(state, BuildingType.MARKET)
    _build(state, BuildingType.QUARRY)
    _build(state, BuildingType.SAWMILL)

    # Assign workers (farm/mill already have workers from new_game)
    _add_workers(state, BuildingType.MARKET, 2)
    _add_workers(state, BuildingType.QUARRY, 2)
    _add_workers(state, BuildingType.SAWMILL, 2)

    # Research
    _research(state, "crop_rotation", "reinforced_tools", "cartography")

    # Explore ring 1 + a few ring 2 hexes
    _explore(state, RING1)
    _explore(state, RING2[:4])

    # Settle resources to a realistic mid-game level
    state.gold  = 120.0
    state.wood  = 80.0
    state.food  = 80.0

    SAVES_DIR.mkdir(exist_ok=True)
    path = save_game(state, SAVES_DIR / "scenario_mid_game.json")
    print(f"Saved: {path}")


def scenario_pre_boss():
    """
    ~500 ticks in: full economy with Iron Mine and Barracks, 10 soldiers
    ready, world map fully explored. Good for testing the boss fight flow.
    """
    state = engine.new_game()
    state.tick = 500

    state.food  = 150.0
    state.wood  = 300.0
    state.gold  = 500.0
    state.stone = 300.0
    state.planks = 80.0
    state.iron  = 60.0

    # 5 → 14 colonists
    _recruit(state, 9)

    # Build all building types
    _build(state, BuildingType.MARKET)
    _build(state, BuildingType.QUARRY)
    _build(state, BuildingType.SAWMILL)

    state.stone = 500.0
    _build(state, BuildingType.IRON_MINE)

    state.wood = 300.0
    state.iron = 80.0
    _build(state, BuildingType.BARRACKS)

    # Assign workers
    _add_workers(state, BuildingType.FARM,        3)
    _add_workers(state, BuildingType.LUMBER_MILL, 2)
    _add_workers(state, BuildingType.MARKET,      3)
    _add_workers(state, BuildingType.QUARRY,      2)
    _add_workers(state, BuildingType.SAWMILL,     2)
    _add_workers(state, BuildingType.IRON_MINE,   2)

    # Research everything
    _research(state, "crop_rotation", "reinforced_tools", "trade_routes",
              "guild_halls", "stone_masonry", "cartography")

    # Explore full rings 1 and 2
    _explore(state, RING1 + RING2)

    # 10 soldiers ready to fight
    state.soldiers = 10

    # Settle resources
    state.gold  = 300.0
    state.wood  = 120.0
    state.food  = 150.0
    state.stone = 80.0
    state.iron  = 30.0

    SAVES_DIR.mkdir(exist_ok=True)
    path = save_game(state, SAVES_DIR / "scenario_pre_boss.json")
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

SCENARIOS = {
    "mid_game": scenario_mid_game,
    "pre_boss": scenario_pre_boss,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "mid_game"
    if name == "all":
        for fn in SCENARIOS.values():
            fn()
    elif name in SCENARIOS:
        SCENARIOS[name]()
    else:
        print(f"Unknown scenario '{name}'. Available: {', '.join(SCENARIOS)}, all")
        sys.exit(1)
