# Outcome

## Summary
Implemented run modifiers ("curses") that players can opt into at run start for increased difficulty in exchange for bonus Legacy Points. Four curses defined; each active curse grants +1 LP on win.

## Changes Made
- **config.py**: Added `CURSES` list (4 entries: drought, heavy_tribute, hard_winter, scarce_lands) and `CURSE_LP_BONUS_PER_CURSE = 1` constant.
- **state.py**: Added `active_curses: List[str]` field; updated `to_dict`/`from_dict`; updated `win_gold_target` property to apply `heavy_tribute` multiplier (×1.5).
- **engine.py**: Applied curse effects in `_process_production` (drought: farm_mult ×0.7), added `_is_winter_for_state` helper for hard_winter (winter length ×1.5 = 90 ticks), applied scarce_lands multiplier (×1.5) to explore costs in `_handle_explore_hex`.
- **progression.py**: Added curse LP bonus in `end_run`: `+len(active_curses) * CURSE_LP_BONUS_PER_CURSE` on win.

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`
- `game/meta/progression.py`

## Metrics After Change
| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 650 | 500.0 | 0.0 |
| production_rush | 1.00 | 679 | 500.0 | 0.0 |
| balanced | 1.00 | 650 | 500.0 | 0.0 |
| gold_rush | 1.00 | 650 | 500.0 | 0.0 |

## Delta vs Baseline
No change — curses are opt-in (active_curses defaults to []), so headless strategies (which don't activate curses) are unaffected.

## Acceptance Criteria Results
- ✅ `hasattr(s, 'active_curses')` — passes
- ✅ `'active_curses' in json.loads(s.to_json())` — passes
- ✅ `hasattr(config, 'CURSES')` — passes
- ✅ `len(config.CURSES) >= 4` — passes (4 curses defined)
- ✅ `hasattr(config, 'CURSE_LP_BONUS_PER_CURSE')` — passes
- ✅ Serialization roundtrip: `s.to_json() == s2.to_json()` — passes
- ✅ `ruff format` + `ruff check` — all passed

## PR URL
(filled after push)

## Status
success

## Notes
- `_is_winter_for_state(state)` is a new internal helper used in `_process_production`; the existing `_is_winter(tick)` is preserved for backwards compatibility and used in `get_season`.
- Curse effects are composable: multiple curses stack independently.
