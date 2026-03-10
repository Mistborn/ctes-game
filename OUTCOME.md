# Outcome

## Summary
Implemented Feature D2: 'Efficient Governance' meta upgrade (3 LP). When toggled on, the engine checks every 10 ticks: if food < 10, it moves one worker from the least-critical building (market > sawmill > quarry priority) to a farm; if food > 200 and the farm has more than 2 workers, it moves one farm worker to a building with open slots.

## Changes Made
- Added `AUTO_BALANCE_INTERVAL=10`, `AUTO_BALANCE_LOW_FOOD=10`, `AUTO_BALANCE_HIGH_FOOD=200`, `AUTO_BALANCE_MIN_FARM_WORKERS=2` constants to config.py
- Added `auto_balance` entry to `config.UPGRADES` (id='auto_balance', name='Efficient Governance', lp_cost=3, requires=None)
- Added `auto_balance_unlocked`, `auto_balance_enabled`, `auto_balance_timer` fields to `GameState` with full `to_dict`/`from_dict` support
- Wired `auto_balance` in `engine.new_game()` following the auto_hire pattern
- Added `_auto_balance()` call in `engine.tick()` automation block
- Implemented `_auto_balance()` function in engine.py

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
No change — all strategies retain 100% win rate and identical tick counts. The auto-balance feature is gated behind a meta upgrade (not unlocked in headless baseline runs), so baseline strategies are unaffected.

## Acceptance Criteria Results
- `python -c "from game.core import config; assert any(u['id'] == 'auto_balance' for u in config.UPGRADES)"` → **PASS**
- `python -c "from game.core.engine import new_game; s = new_game(); assert hasattr(s, 'auto_balance_unlocked')"` → **PASS**
- `python -c "from game.core.engine import new_game; import json; s = new_game(); d = json.loads(s.to_json()); assert 'auto_balance_unlocked' in d"` → **PASS**
- Serialization roundtrip: `s.to_json() == GameState.from_json(s.to_json()).to_json()` → **PASS**

## PR URL
https://github.com/Mistborn/ctes-game/pull/17

## Status
success

## Notes
Implementation follows the existing auto_hire/auto_explore patterns exactly. The `_auto_balance()` function uses a timer identical to `_auto_explore()`. Worker moves are done by updating both the colonist's `assigned_building_id` and the building's `workers_assigned` counter, consistent with `_handle_assign_worker()`.
