"""
progression.py — Persistent meta-state across roguelite runs.

Saved to meta_save.json in the game working directory.
No Pygame imports. No renderer imports. Peer of game/core/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from game.core import config

if TYPE_CHECKING:
    from game.core.state import GameState

META_SAVE_PATH = Path("meta_save.json")


def compute_lp_earned(state: "GameState") -> int:
    """Return Legacy Points earned for a completed run. Wins give 1 LP, losses give 0."""
    from game.core.entities import GameStatus

    return config.LP_PER_WIN if state.status == GameStatus.WIN else 0


@dataclass
class MetaState:
    run_number: int = 1
    legacy_points: int = 0
    unlocked_upgrades: List[str] = field(default_factory=list)
    carried_tech_id: Optional[str] = None
    total_runs: int = 0
    total_wins: int = 0

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def save(self) -> None:
        data = {
            "run_number": self.run_number,
            "legacy_points": self.legacy_points,
            "unlocked_upgrades": list(self.unlocked_upgrades),
            "carried_tech_id": self.carried_tech_id,
            "total_runs": self.total_runs,
            "total_wins": self.total_wins,
        }
        META_SAVE_PATH.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> "MetaState":
        if not META_SAVE_PATH.exists():
            return cls()
        try:
            data = json.loads(META_SAVE_PATH.read_text())
            return cls(
                run_number=data.get("run_number", 1),
                legacy_points=data.get("legacy_points", 0),
                unlocked_upgrades=list(data.get("unlocked_upgrades", [])),
                carried_tech_id=data.get("carried_tech_id"),
                total_runs=data.get("total_runs", 0),
                total_wins=data.get("total_wins", 0),
            )
        except Exception:
            return cls()

    # -----------------------------------------------------------------------
    # Upgrades
    # -----------------------------------------------------------------------

    def buy_upgrade(self, upgrade_id: str) -> bool:
        """Attempt to purchase an upgrade. Returns True on success."""
        upgrade = next((u for u in config.UPGRADES if u["id"] == upgrade_id), None)
        if upgrade is None:
            return False
        if upgrade_id in self.unlocked_upgrades:
            return False
        requires = upgrade.get("requires")
        if requires and requires not in self.unlocked_upgrades:
            return False
        if self.legacy_points < upgrade["lp_cost"]:
            return False
        self.legacy_points -= upgrade["lp_cost"]
        self.unlocked_upgrades.append(upgrade_id)
        return True

    # -----------------------------------------------------------------------
    # Run end
    # -----------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all persistent progression for a true fresh start."""
        self.run_number = 1
        self.legacy_points = 0
        self.unlocked_upgrades = []
        self.carried_tech_id = None
        self.total_runs = 0
        self.total_wins = 0

    def end_run(self, state: "GameState") -> int:
        """
        Called after a run ends. Updates legacy_points, total_runs, etc.
        Returns LP earned this run.
        """
        from game.core.entities import GameStatus

        lp = compute_lp_earned(state)
        self.legacy_points += lp
        self.total_runs += 1
        if state.status == GameStatus.WIN:
            self.total_wins += 1
        # veteran_memory: carry the most recently researched tech
        if "veteran_memory" in self.unlocked_upgrades and state.researched_tech_ids:
            self.carried_tech_id = state.researched_tech_ids[-1]
        return lp
