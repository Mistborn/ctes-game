# Outcome

## Summary
Implemented the **Pioneer Spirit** auto-explore meta upgrade (Feature D1). When unlocked (3 LP) and toggled on, the game automatically explores the cheapest adjacent unexplored hex every 20 ticks when resources allow.

## Changes Made
- `game/core/config.py`: Added `AUTO_EXPLORE_INTERVAL = 20` and a new `auto_explore` entry to `UPGRADES`
- `game/core/state.py`: Added `auto_explore_unlocked`, `auto_explore_enabled` (bools), and `auto_explore_timer` (int) fields; updated `to_dict()` and `from_dict()`
- `game/core/engine.py`: `new_game()` sets unlocked+enabled when meta has `auto_explore`; `tick()` calls `_auto_explore()` after the auto_research block; new `_auto_explore()` helper increments timer every tick, resets at interval, finds all explorable hexes (unexplored with explored neighbor), sorts by total cost ascending, attempts to explore the cheapest if resources suffice

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 650 | 500.0 | 0.0 |
| production_rush | 1.00 | 679 | 500.0 | 0.0 |
| balanced | 1.00 | 650 | 500.0 | 0.0 |
| gold_rush | 1.00 | 650 | 500.0 | 0.0 |

## Delta vs Baseline
No change — metrics are identical to baseline. The feature only activates when the meta upgrade is unlocked, which headless strategies do not use.

## Acceptance Criteria Results
- ✅ `python -c "from game.core import config; assert any(u['id'] == 'auto_explore' for u in config.UPGRADES)"`
- ✅ `python -c "from game.core.engine import new_game; s = new_game(); assert hasattr(s, 'auto_explore_unlocked')"`
- ✅ `python -c "from game.core.engine import new_game; s = new_game(); assert hasattr(s, 'auto_explore_enabled')"`
- ✅ `python -c "from game.core.engine import new_game; import json; s = new_game(); d = json.loads(s.to_json()); assert 'auto_explore_unlocked' in d"`
- ✅ Serialization roundtrip: `s.to_json() == GameState.from_json(s.to_json()).to_json()`

## PR URL
https://github.com/Mistborn/ctes-game/pull/16

## Status
success

## Notes
None.
