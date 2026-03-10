# Outcome

## Summary
Implemented Feature D3: Building auto-upgrade ("Master Builder"). Added the `auto_build` LP upgrade (3 LP) that automatically builds a second copy of the most productive building type every 30 ticks when resources are ≥ 2× the next build cost and there are idle colonists available.

## Changes Made
- Added `auto_build` upgrade entry to `config.UPGRADES`
- Added `AUTO_BUILD_INTERVAL = 30` and `AUTO_BUILD_COST_MULTIPLIER = 2.0` constants to `config.py`
- Added `auto_build_unlocked`, `auto_build_enabled`, `auto_build_timer` fields to `GameState`
- Updated `to_dict()` and `from_dict()` for the new fields
- Added `_auto_build()` helper in `engine.py` following the auto_balance/auto_explore timer pattern
- Wired `auto_build` into `new_game()` (meta upgrade check) and `tick()` (automation step)

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
No change in win rate or tick counts. The auto_build upgrade is not activated by default in headless strategies (meta upgrades require unlocking), so baseline metrics are preserved.

## Acceptance Criteria Results
- `python -c "from game.core import config; assert any(u['id'] == 'auto_build' for u in config.UPGRADES)"` → **PASS**
- `python -c "from game.core.engine import new_game; s = new_game(); assert hasattr(s, 'auto_build_unlocked')"` → **PASS**
- `python -c "from game.core.engine import new_game; import json; s = new_game(); d = json.loads(s.to_json()); assert 'auto_build_unlocked' in d"` → **PASS**
- Serialization roundtrip: `s.to_json() == GameState.from_json(s.to_json()).to_json()` → **PASS**

## PR URL
https://github.com/Mistborn/ctes-game/pull/18

## Status
success

## Notes
The `_auto_build()` function skips BARRACKS (no production output tracked in `production_rates`) and handles IRON_MINE's stone-based cost separately from wood-only buildings. Building type eligibility requires at least one existing building of that type with workers assigned (so output > 0).
