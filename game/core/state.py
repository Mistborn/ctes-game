"""
state.py — GameState dataclass: the single source of truth for all game data.

Rules:
- No logic here, only data.
- Fully JSON-serialisable at any tick.
- No Pygame imports ever.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List

from game.core import config
from game.core.entities import Building, BuildingType, Colonist, GameStatus


@dataclass
class GameState:
    # -------------------------------------------------------------------
    # Time
    # -------------------------------------------------------------------
    tick: int = 0
    speed_multiplier: int = 1  # 1 | 5 | 50

    # -------------------------------------------------------------------
    # Resources
    # -------------------------------------------------------------------
    food: float = float(config.STARTING_FOOD)
    wood: float = float(config.STARTING_WOOD)
    gold: float = float(config.STARTING_GOLD)
    stone: float = float(config.STARTING_STONE)
    planks: float = float(config.STARTING_PLANKS)
    iron: float = float(config.STARTING_IRON)

    # -------------------------------------------------------------------
    # Per-tick rate snapshots (updated by engine each tick for display)
    # -------------------------------------------------------------------
    food_rate: float = 0.0  # net food change last tick
    wood_rate: float = 0.0
    gold_rate: float = 0.0
    stone_rate: float = 0.0
    planks_rate: float = 0.0
    iron_rate: float = 0.0

    # -------------------------------------------------------------------
    # Entities
    # -------------------------------------------------------------------
    colonists: List[Colonist] = field(default_factory=list)
    buildings: List[Building] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Counters / bookkeeping
    # -------------------------------------------------------------------
    next_colonist_id: int = 0
    next_building_id: int = 0

    # Cumulative starvation event count (used by agent metrics)
    starvation_events: int = 0
    # Peak colonist count reached during the run
    peak_colonists: int = 0

    # -------------------------------------------------------------------
    # Military
    # -------------------------------------------------------------------
    soldiers: int = 0
    boss_fights_won: int = 0
    boss_fight_cooldown: int = 0
    # Ring numbers of boss hexes cleared this run (used to award first-kill LP at run end)
    boss_rings_cleared: List[int] = field(default_factory=list)
    # Building type value strings unlocked by killing bosses (populated by BOSS_BUILDING_GATES)
    boss_unlocked_buildings: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Info log — seasonal/event messages shown in the left sidebar
    # Each entry: [tick, message, msg_type]
    # msg_type: "warning" | "winter" | "spring" | "summer" | "info"
    # -------------------------------------------------------------------
    info_log: List = field(default_factory=list)

    # -------------------------------------------------------------------
    # Tutorial hints — IDs of hints already shown this run
    # -------------------------------------------------------------------
    shown_hints: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Research
    # -------------------------------------------------------------------
    researched_tech_ids: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Milestones — IDs of already-triggered milestone notifications
    # -------------------------------------------------------------------
    triggered_milestones: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Hex world map  {"q,r": {"terrain": str, "explored": bool}}
    # -------------------------------------------------------------------
    hex_tiles: dict = field(default_factory=dict)

    # Keys ("q,r") where a hex event has already fired — prevents re-triggering on load
    triggered_hex_events: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Roguelite / meta
    # -------------------------------------------------------------------
    run_number: int = 1
    total_gold_earned: float = 0.0
    # Per-run multipliers set by meta upgrades (1.0 = no effect)
    food_consumption_mult: float = 1.0
    market_gold_bonus_mult: float = 1.0
    # Active run modifier curse IDs chosen at run start
    active_curses: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Automation upgrades (set by new_game based on meta; toggled in-run)
    # -------------------------------------------------------------------
    auto_hire_unlocked: bool = False
    auto_hire_enabled: bool = False
    auto_assign_unlocked: bool = False
    auto_assign_enabled: bool = False
    auto_research_unlocked: bool = False
    auto_research_enabled: bool = False
    auto_explore_unlocked: bool = False
    auto_explore_enabled: bool = False
    auto_explore_timer: int = 0
    auto_balance_unlocked: bool = False
    auto_balance_enabled: bool = False
    auto_balance_timer: int = 0
    auto_build_unlocked: bool = False
    auto_build_enabled: bool = False
    auto_build_timer: int = 0

    # -------------------------------------------------------------------
    # Colony random events
    # -------------------------------------------------------------------
    colony_event_timer: int = 0

    # -------------------------------------------------------------------
    # Trading caravan
    # -------------------------------------------------------------------
    caravan_timer: int = 0
    # {'trade_index': int, 'expires_at_tick': int} or None
    current_trade: dict | None = None

    # -------------------------------------------------------------------
    # Seasons — track previous tick's winter state for transition detection
    # -------------------------------------------------------------------
    last_season_was_winter: bool = False

    # -------------------------------------------------------------------
    # Game status
    # -------------------------------------------------------------------
    status: GameStatus = GameStatus.PLAYING
    paused: bool = False

    # -------------------------------------------------------------------
    # JSON serialisation
    # -------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "speed_multiplier": self.speed_multiplier,
            "food": self.food,
            "wood": self.wood,
            "gold": self.gold,
            "stone": self.stone,
            "planks": self.planks,
            "iron": self.iron,
            "food_rate": self.food_rate,
            "wood_rate": self.wood_rate,
            "gold_rate": self.gold_rate,
            "stone_rate": self.stone_rate,
            "planks_rate": self.planks_rate,
            "iron_rate": self.iron_rate,
            "colonists": [c.to_dict() for c in self.colonists],
            "buildings": [b.to_dict() for b in self.buildings],
            "next_colonist_id": self.next_colonist_id,
            "next_building_id": self.next_building_id,
            "starvation_events": self.starvation_events,
            "peak_colonists": self.peak_colonists,
            "soldiers": self.soldiers,
            "boss_fights_won": self.boss_fights_won,
            "boss_fight_cooldown": self.boss_fight_cooldown,
            "boss_rings_cleared": list(self.boss_rings_cleared),
            "boss_unlocked_buildings": list(self.boss_unlocked_buildings),
            "status": self.status.value,
            "paused": self.paused,
            "researched_tech_ids": list(self.researched_tech_ids),
            "run_number": self.run_number,
            "total_gold_earned": self.total_gold_earned,
            "food_consumption_mult": self.food_consumption_mult,
            "market_gold_bonus_mult": self.market_gold_bonus_mult,
            "active_curses": list(self.active_curses),
            "hex_tiles": self.hex_tiles,
            "triggered_hex_events": list(self.triggered_hex_events),
            "auto_hire_unlocked": self.auto_hire_unlocked,
            "auto_hire_enabled": self.auto_hire_enabled,
            "auto_assign_unlocked": self.auto_assign_unlocked,
            "auto_assign_enabled": self.auto_assign_enabled,
            "auto_research_unlocked": self.auto_research_unlocked,
            "auto_research_enabled": self.auto_research_enabled,
            "auto_explore_unlocked": self.auto_explore_unlocked,
            "auto_explore_enabled": self.auto_explore_enabled,
            "auto_explore_timer": self.auto_explore_timer,
            "auto_balance_unlocked": self.auto_balance_unlocked,
            "auto_balance_enabled": self.auto_balance_enabled,
            "auto_balance_timer": self.auto_balance_timer,
            "auto_build_unlocked": self.auto_build_unlocked,
            "auto_build_enabled": self.auto_build_enabled,
            "auto_build_timer": self.auto_build_timer,
            "last_season_was_winter": self.last_season_was_winter,
            "colony_event_timer": self.colony_event_timer,
            "caravan_timer": self.caravan_timer,
            "current_trade": self.current_trade,
            "info_log": [list(e) for e in self.info_log],
            "shown_hints": list(self.shown_hints),
            "triggered_milestones": list(self.triggered_milestones),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        gs = cls(
            tick=d["tick"],
            speed_multiplier=d["speed_multiplier"],
            food=d["food"],
            wood=d["wood"],
            gold=d["gold"],
            stone=d.get("stone", 0.0),
            planks=d.get("planks", 0.0),
            iron=d.get("iron", 0.0),
            food_rate=d.get("food_rate", 0.0),
            wood_rate=d.get("wood_rate", 0.0),
            gold_rate=d.get("gold_rate", 0.0),
            stone_rate=d.get("stone_rate", 0.0),
            planks_rate=d.get("planks_rate", 0.0),
            iron_rate=d.get("iron_rate", 0.0),
            colonists=[Colonist.from_dict(c) for c in d["colonists"]],
            buildings=[Building.from_dict(b) for b in d["buildings"]],
            next_colonist_id=d["next_colonist_id"],
            next_building_id=d["next_building_id"],
            starvation_events=d.get("starvation_events", 0),
            peak_colonists=d.get("peak_colonists", 0),
            soldiers=d.get("soldiers", 0),
            boss_fights_won=d.get("boss_fights_won", 0),
            boss_fight_cooldown=d.get("boss_fight_cooldown", 0),
            boss_rings_cleared=list(d.get("boss_rings_cleared", [])),
            boss_unlocked_buildings=list(d.get("boss_unlocked_buildings", [])),
            status=GameStatus(d["status"]),
            paused=d.get("paused", False),
            researched_tech_ids=list(d.get("researched_tech_ids", [])),
            run_number=d.get("run_number", 1),
            total_gold_earned=d.get("total_gold_earned", 0.0),
            food_consumption_mult=d.get("food_consumption_mult", 1.0),
            market_gold_bonus_mult=d.get("market_gold_bonus_mult", 1.0),
            active_curses=list(d.get("active_curses", [])),
            hex_tiles=d.get("hex_tiles", {}),
            triggered_hex_events=list(d.get("triggered_hex_events", [])),
            auto_hire_unlocked=d.get("auto_hire_unlocked", False),
            auto_hire_enabled=d.get("auto_hire_enabled", False),
            auto_assign_unlocked=d.get("auto_assign_unlocked", False),
            auto_assign_enabled=d.get("auto_assign_enabled", False),
            auto_research_unlocked=d.get("auto_research_unlocked", False),
            auto_research_enabled=d.get("auto_research_enabled", False),
            auto_explore_unlocked=d.get("auto_explore_unlocked", False),
            auto_explore_enabled=d.get("auto_explore_enabled", False),
            auto_explore_timer=d.get("auto_explore_timer", 0),
            auto_balance_unlocked=d.get("auto_balance_unlocked", False),
            auto_balance_enabled=d.get("auto_balance_enabled", False),
            auto_balance_timer=d.get("auto_balance_timer", 0),
            auto_build_unlocked=d.get("auto_build_unlocked", False),
            auto_build_enabled=d.get("auto_build_enabled", False),
            auto_build_timer=d.get("auto_build_timer", 0),
            last_season_was_winter=d.get("last_season_was_winter", False),
            colony_event_timer=d.get("colony_event_timer", 0),
            caravan_timer=d.get("caravan_timer", 0),
            current_trade=d.get("current_trade", None),
        )
        gs.info_log = [list(e) for e in d.get("info_log", [])]
        gs.shown_hints = list(d.get("shown_hints", []))
        gs.triggered_milestones = list(d.get("triggered_milestones", []))
        return gs

    @classmethod
    def from_json(cls, s: str) -> "GameState":
        return cls.from_dict(json.loads(s))

    # -------------------------------------------------------------------
    # Convenience helpers (read-only, no side effects)
    # -------------------------------------------------------------------

    @property
    def hex_map_unlocked(self) -> bool:
        return "cartography" in self.researched_tech_ids

    @property
    def win_gold_target(self) -> int:
        if self.run_number == 1:
            base = config.WIN_GOLD_TARGET_BASE
        else:
            base = round(config.WIN_GOLD_TARGET_RUN2 * config.WIN_GOLD_TARGET_RUN_MULTIPLIER ** (self.run_number - 2))
        if "heavy_tribute" in self.active_curses:
            curse = next(c for c in config.CURSES if c["curse_id"] == "heavy_tribute")
            base = round(base * curse["effect_value"])
        return base

    @property
    def colonist_count(self) -> int:
        return sum(1 for c in self.colonists if c is not None)

    @property
    def idle_colonists(self) -> int:
        return sum(1 for c in self.colonists if c is not None and c.assigned_building_id is None)

    def workers_on(self, building_id: int) -> int:
        return sum(1 for c in self.colonists if c is not None and c.assigned_building_id == building_id)

    def building_by_id(self, building_id: int) -> Building | None:
        for b in self.buildings:
            if b.id == building_id:
                return b
        return None

    @property
    def has_barracks(self) -> bool:
        return any(b.building_type == BuildingType.BARRACKS for b in self.buildings)
