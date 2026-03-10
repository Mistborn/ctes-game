# Outcome

## Summary
Implemented a 50-tick cooldown after a failed boss fight. The player cannot re-attempt a boss fight until the cooldown expires.

## Changes Made
- **config.py**: Added `BOSS_FIGHT_COOLDOWN_TICKS = 50`
- **state.py**: Added `boss_fight_cooldown: int = 0` field; updated `to_dict()` and `from_dict()`
- **engine.py** (`tick`): Decrement `boss_fight_cooldown` by 1 each tick when > 0
- **engine.py** (`_handle_fight_boss`): Return early if `boss_fight_cooldown > 0`; set `boss_fight_cooldown = config.BOSS_FIGHT_COOLDOWN_TICKS` after a failed fight

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
No change — all strategies win at identical tick counts and gold. The boss cooldown only affects failed fight attempts; headless strategies don't fight bosses, so metrics are unchanged.

## Acceptance Criteria Results
- ✅ `hasattr(new_game(), 'boss_fight_cooldown')` — passes
- ✅ `'boss_fight_cooldown' in json.loads(new_game().to_json())` — passes
- ✅ `config.BOSS_FIGHT_COOLDOWN_TICKS == 50` — passes
- ✅ Serialization roundtrip: `s.to_json() == GameState.from_json(s.to_json()).to_json()` — passes
- ✅ `ruff format` + `ruff check` — passes (pre-commit hooks passed)

## PR URL
https://github.com/Mistborn/ctes-game/pull/15

## Status
success

## Notes
None.
