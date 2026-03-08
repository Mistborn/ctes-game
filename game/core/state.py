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

from game.core.entities import Building, BuildingType, Colonist, GameStatus
from game.core import config


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

    # -------------------------------------------------------------------
    # Per-tick rate snapshots (updated by engine each tick for display)
    # -------------------------------------------------------------------
    food_rate: float = 0.0   # net food change last tick
    wood_rate: float = 0.0
    gold_rate: float = 0.0
    stone_rate: float = 0.0
    planks_rate: float = 0.0

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
    # Info log — seasonal/event messages shown in the left sidebar
    # Each entry: [tick, message, msg_type]
    # msg_type: "warning" | "winter" | "spring" | "summer" | "info"
    # -------------------------------------------------------------------
    info_log: List = field(default_factory=list)

    # -------------------------------------------------------------------
    # Research
    # -------------------------------------------------------------------
    researched_tech_ids: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------
    # Hex world map  {"q,r": {"terrain": str, "explored": bool}}
    # -------------------------------------------------------------------
    hex_tiles: dict = field(default_factory=dict)

    # -------------------------------------------------------------------
    # Roguelite / meta
    # -------------------------------------------------------------------
    run_number: int = 1
    total_gold_earned: float = 0.0
    # Per-run multipliers set by meta upgrades (1.0 = no effect)
    food_consumption_mult: float = 1.0
    market_gold_bonus_mult: float = 1.0

    # -------------------------------------------------------------------
    # Automation upgrades (set by new_game based on meta; toggled in-run)
    # -------------------------------------------------------------------
    auto_hire_unlocked: bool = False
    auto_hire_enabled: bool = False
    auto_assign_unlocked: bool = False
    auto_assign_enabled: bool = False

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
            "food_rate": self.food_rate,
            "wood_rate": self.wood_rate,
            "gold_rate": self.gold_rate,
            "stone_rate": self.stone_rate,
            "planks_rate": self.planks_rate,
            "colonists": [c.to_dict() for c in self.colonists],
            "buildings": [b.to_dict() for b in self.buildings],
            "next_colonist_id": self.next_colonist_id,
            "next_building_id": self.next_building_id,
            "starvation_events": self.starvation_events,
            "peak_colonists": self.peak_colonists,
            "status": self.status.value,
            "paused": self.paused,
            "researched_tech_ids": list(self.researched_tech_ids),
            "run_number": self.run_number,
            "total_gold_earned": self.total_gold_earned,
            "food_consumption_mult": self.food_consumption_mult,
            "market_gold_bonus_mult": self.market_gold_bonus_mult,
            "hex_tiles": self.hex_tiles,
            "auto_hire_unlocked": self.auto_hire_unlocked,
            "auto_hire_enabled": self.auto_hire_enabled,
            "auto_assign_unlocked": self.auto_assign_unlocked,
            "auto_assign_enabled": self.auto_assign_enabled,
            "info_log": [list(e) for e in self.info_log],
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
            food_rate=d.get("food_rate", 0.0),
            wood_rate=d.get("wood_rate", 0.0),
            gold_rate=d.get("gold_rate", 0.0),
            stone_rate=d.get("stone_rate", 0.0),
            planks_rate=d.get("planks_rate", 0.0),
            colonists=[Colonist.from_dict(c) for c in d["colonists"]],
            buildings=[Building.from_dict(b) for b in d["buildings"]],
            next_colonist_id=d["next_colonist_id"],
            next_building_id=d["next_building_id"],
            starvation_events=d.get("starvation_events", 0),
            peak_colonists=d.get("peak_colonists", 0),
            status=GameStatus(d["status"]),
            paused=d.get("paused", False),
            researched_tech_ids=list(d.get("researched_tech_ids", [])),
            run_number=d.get("run_number", 1),
            total_gold_earned=d.get("total_gold_earned", 0.0),
            food_consumption_mult=d.get("food_consumption_mult", 1.0),
            market_gold_bonus_mult=d.get("market_gold_bonus_mult", 1.0),
            hex_tiles=d.get("hex_tiles", {}),
            auto_hire_unlocked=d.get("auto_hire_unlocked", False),
            auto_hire_enabled=d.get("auto_hire_enabled", False),
            auto_assign_unlocked=d.get("auto_assign_unlocked", False),
            auto_assign_enabled=d.get("auto_assign_enabled", False),
        )
        gs.info_log = [list(e) for e in d.get("info_log", [])]
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
            return config.WIN_GOLD_TARGET_BASE
        return round(config.WIN_GOLD_TARGET_RUN2 * config.WIN_GOLD_TARGET_RUN_MULTIPLIER ** (self.run_number - 2))

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
