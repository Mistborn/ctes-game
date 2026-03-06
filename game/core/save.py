"""
save.py — Persist and restore GameState to/from disk.

Pure logic only — no Pygame, no renderer imports.

Save file layout (all under saves/):
    autosave.json              — rolling autosave, overwritten every N ticks
    save_YYYYMMDD_HHMMSS.json  — manual saves created on "Save & Exit"

Public API:
    autosave_game(state)           -> None
    save_game(state, path)         -> None
    new_manual_save_path()         -> Path
    load_game(path)                -> GameState
    has_save()                     -> bool
    get_most_recent_save()         -> tuple[Path, dict] | None
    list_saves()                   -> list[dict]   (sorted newest-first)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from game.core.state import GameState

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SAVES_DIR = Path(__file__).parent.parent.parent / "saves"
AUTOSAVE_PATH = SAVES_DIR / "autosave.json"


def _ensure_dir() -> None:
    SAVES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def autosave_game(state: GameState) -> None:
    """Overwrite the rolling autosave (saves/autosave.json)."""
    _ensure_dir()
    AUTOSAVE_PATH.write_text(state.to_json(), encoding="utf-8")


def new_manual_save_path() -> Path:
    """Return a fresh timestamped path for a manual save."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SAVES_DIR / f"save_{stamp}.json"


def save_game(state: GameState, path: Optional[Path] = None) -> Path:
    """
    Write *state* to *path*.  If *path* is None a timestamped manual-save
    path is generated automatically.  Returns the path used.
    """
    if path is None:
        path = new_manual_save_path()
    _ensure_dir()
    path.write_text(state.to_json(), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_game(path: Path = AUTOSAVE_PATH) -> GameState:
    """Deserialise a GameState from *path*."""
    return GameState.from_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Listing / querying
# ---------------------------------------------------------------------------

def has_save() -> bool:
    """Return True if at least one save file exists."""
    if not SAVES_DIR.exists():
        return False
    return any(SAVES_DIR.glob("*.json"))


def _save_info(path: Path) -> dict | None:
    """Parse a save file and return a summary dict, or None if corrupt."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    mtime = path.stat().st_mtime
    dt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    name = "Autosave" if path.name == "autosave.json" else "Manual Save"

    return {
        "path": path,
        "name": name,
        "datetime_str": dt_str,
        "mtime": mtime,
        "tick": data.get("tick", 0),
        "gold": data.get("gold", 0.0),
        "colonists": len(data.get("colonists", [])),
        "status": data.get("status", "playing"),
    }


def list_saves() -> list[dict]:
    """
    Return info dicts for every save in SAVES_DIR, sorted newest-first.
    Corrupt or unreadable files are silently skipped.
    """
    if not SAVES_DIR.exists():
        return []
    infos = []
    for p in SAVES_DIR.glob("*.json"):
        info = _save_info(p)
        if info is not None:
            infos.append(info)
    infos.sort(key=lambda x: x["mtime"], reverse=True)
    return infos


def get_most_recent_save() -> tuple[Path, dict] | None:
    """
    Return (path, info_dict) for the most recently modified save, or None.
    """
    saves = list_saves()
    if not saves:
        return None
    info = saves[0]
    return info["path"], info
