# Outcome

## Summary
Implemented hex map exploration events (Feature E1). When exploring certain hex terrain types, a one-time random event may fire: Wandering Merchant (forest, 20%), Ancient Cache (ruins, 30%), or Refugee Camp (plains, 15%). Events resolve instantly, are logged to the info log, and are tracked via `triggered_hex_events` to prevent re-triggering on save/load.

## Changes Made
- **config.py**: Added `HEX_EVENTS` dict mapping terrain to list of `{event_id, probability, description, effects}`. Added `HEX_EVENT_MERCHANT_MIN_WOOD = 30` constant.
- **state.py**: Added `triggered_hex_events: List[str]` field; updated `to_dict` and `from_dict`.
- **engine.py**: Extended `_handle_explore_hex` — after normal terrain rewards, iterates HEX_EVENTS for the terrain, rolls random, applies resource/colonist effects, logs to info_log, appends hex key to triggered_hex_events.

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
No change — all strategies identical to baseline. Headless strategies do not explore hexes, so events never fire.

## Acceptance Criteria Results
- PASS: `hasattr(s, 'triggered_hex_events')`
- PASS: `'triggered_hex_events' in json.loads(s.to_json())`
- PASS: `hasattr(config, 'HEX_EVENTS')`
- PASS: Serialization roundtrip `s.to_json() == GameState.from_json(s.to_json()).to_json()`
- PASS: `ruff format` + `ruff check` — all checks passed

## PR URL
https://github.com/Mistborn/ctes-game/pull/19

## Status
success

## Notes
The Wandering Merchant event requires wood >= 30 before triggering to prevent negative resources. triggered_hex_events uses "q,r" string keys matching the hex_tiles dict format for correct deduplication across save/load.
