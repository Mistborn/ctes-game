"""
entities.py — Pure data structures for game objects.

All fields use plain Python primitives so GameState serialises cleanly to JSON.
No Pygame, no engine logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BuildingType(str, Enum):
    """String enum so values round-trip through JSON without extra handling."""
    FARM = "Farm"
    LUMBER_MILL = "Lumber Mill"
    MARKET = "Market"
    QUARRY = "Quarry"
    SAWMILL = "Sawmill"


class GameStatus(str, Enum):
    PLAYING = "playing"
    WIN = "win"
    LOSE = "lose"


# ---------------------------------------------------------------------------
# Resource bundle (used for costs, production snapshots, etc.)
# ---------------------------------------------------------------------------

@dataclass
class ResourceBundle:
    food: float = 0.0
    wood: float = 0.0
    gold: float = 0.0
    stone: float = 0.0
    planks: float = 0.0

    def to_dict(self) -> dict:
        return {"food": self.food, "wood": self.wood, "gold": self.gold,
                "stone": self.stone, "planks": self.planks}

    @classmethod
    def from_dict(cls, d: dict) -> "ResourceBundle":
        return cls(food=d["food"], wood=d["wood"], gold=d["gold"],
                   stone=d.get("stone", 0.0), planks=d.get("planks", 0.0))


# ---------------------------------------------------------------------------
# Colonist
# ---------------------------------------------------------------------------

@dataclass
class Colonist:
    id: int
    # id of the building this colonist is assigned to, or None if idle
    assigned_building_id: int | None = None
    # cumulative ticks starved (for stats / display)
    ticks_starved: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "assigned_building_id": self.assigned_building_id,
            "ticks_starved": self.ticks_starved,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Colonist":
        return cls(
            id=d["id"],
            assigned_building_id=d.get("assigned_building_id"),
            ticks_starved=d.get("ticks_starved", 0),
        )


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

@dataclass
class Building:
    id: int
    building_type: BuildingType
    # current number of workers assigned
    workers_assigned: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "building_type": self.building_type.value,
            "workers_assigned": self.workers_assigned,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Building":
        return cls(
            id=d["id"],
            building_type=BuildingType(d["building_type"]),
            workers_assigned=d.get("workers_assigned", 0),
        )


# ---------------------------------------------------------------------------
# Action types (passed to engine.apply_action)
# ---------------------------------------------------------------------------

@dataclass
class ActionAssignWorker:
    """Add one worker to a building (+1) or remove one (-1)."""
    building_id: int
    delta: int  # +1 or -1


@dataclass
class ActionBuildBuilding:
    """Construct a new building of the given type."""
    building_type: BuildingType


@dataclass
class ActionSetSpeed:
    """Change simulation speed to one of the allowed multipliers."""
    speed_multiplier: int


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

@dataclass
class ResearchTech:
    """Pure data descriptor for a researchable technology (no logic)."""
    tech_id: str
    name: str
    description: str
    gold_cost: int


@dataclass
class ActionResearchTech:
    """Player action: spend gold to unlock a technology."""
    tech_id: str
