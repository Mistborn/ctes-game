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

    # -------------------------------------------------------------------
    # Per-tick rate snapshots (updated by engine each tick for display)
    # -------------------------------------------------------------------
    food_rate: float = 0.0   # net food change last tick
    wood_rate: float = 0.0
    gold_rate: float = 0.0

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

    # Ticks since last colonist-arrival check
    ticks_since_last_arrival_check: int = 0

    # Cumulative starvation event count (used by agent metrics)
    starvation_events: int = 0
    # Peak colonist count reached during the run
    peak_colonists: int = 0

    # -------------------------------------------------------------------
    # Game status
    # -------------------------------------------------------------------
    status: GameStatus = GameStatus.PLAYING

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
            "food_rate": self.food_rate,
            "wood_rate": self.wood_rate,
            "gold_rate": self.gold_rate,
            "colonists": [c.to_dict() for c in self.colonists],
            "buildings": [b.to_dict() for b in self.buildings],
            "next_colonist_id": self.next_colonist_id,
            "next_building_id": self.next_building_id,
            "ticks_since_last_arrival_check": self.ticks_since_last_arrival_check,
            "starvation_events": self.starvation_events,
            "peak_colonists": self.peak_colonists,
            "status": self.status.value,
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
            food_rate=d.get("food_rate", 0.0),
            wood_rate=d.get("wood_rate", 0.0),
            gold_rate=d.get("gold_rate", 0.0),
            colonists=[Colonist.from_dict(c) for c in d["colonists"]],
            buildings=[Building.from_dict(b) for b in d["buildings"]],
            next_colonist_id=d["next_colonist_id"],
            next_building_id=d["next_building_id"],
            ticks_since_last_arrival_check=d.get("ticks_since_last_arrival_check", 0),
            starvation_events=d.get("starvation_events", 0),
            peak_colonists=d.get("peak_colonists", 0),
            status=GameStatus(d["status"]),
        )
        return gs

    @classmethod
    def from_json(cls, s: str) -> "GameState":
        return cls.from_dict(json.loads(s))

    # -------------------------------------------------------------------
    # Convenience helpers (read-only, no side effects)
    # -------------------------------------------------------------------

    @property
    def colonist_count(self) -> int:
        return len(self.colonists)

    @property
    def idle_colonists(self) -> int:
        return sum(1 for c in self.colonists if c.assigned_building_id is None)

    def workers_on(self, building_id: int) -> int:
        return sum(1 for c in self.colonists if c.assigned_building_id == building_id)

    def building_by_id(self, building_id: int) -> Building | None:
        for b in self.buildings:
            if b.id == building_id:
                return b
        return None
