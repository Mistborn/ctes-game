# Outcome

## Summary
Implemented colony random events (Feature F4). Every 200 ticks, a random event fires from a pool of 6 events, adding unpredictability to each run without breaking balance.

## Changes Made
- `game/core/config.py`: Added `COLONY_EVENT_INTERVAL = 200` and `COLONY_EVENTS` list (6 entries: plague, baby_boom, bountiful_harvest, gold_discovery, supply_rot, skilled_immigrant)
- `game/core/state.py`: Added `colony_event_timer: int = 0` field; updated `to_dict()` and `from_dict()`
- `game/core/engine.py`: Added `_process_colony_event()` helper function; called from `tick()` after caravan processing (step 7d)

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 563.60 | 500.28 | 0.0 |
| production_rush | 1.00 | 600.10 | 501.68 | 0.0 |
| balanced | 1.00 | 562.70 | 500.24 | 0.0 |
| gold_rush | 1.00 | 475.50 | 500.50 | 0.0 |

## Delta vs Baseline
| Strategy | Win Rate delta | Ticks delta (mean) |
|----------|----------------|-------------------|
| food_first | 0.00 | -86.40 |
| production_rush | 0.00 | -78.90 |
| balanced | 0.00 | -87.30 |
| gold_rush | 0.00 | -174.50 |

All strategies maintain 100% win rate. Tick counts decreased slightly — random gain_food/gain_gold events occasionally accelerate completion.

## Acceptance Criteria Results
- PASS: `hasattr(config, 'COLONY_EVENTS')`
- PASS: `len(config.COLONY_EVENTS) >= 5` (6 events)
- PASS: `hasattr(config, 'COLONY_EVENT_INTERVAL')`
- PASS: `hasattr(new_game(), 'colony_event_timer')`
- PASS: `'colony_event_timer' in json.loads(new_game().to_json())`
- PASS: JSON serialization roundtrip
- PASS: ruff format + ruff check

## PR URL
https://github.com/Mistborn/ctes-game/pull/23

## Status
success

## Notes
Colony events fire on tick multiples of 200. The lose_colonist effect is skipped when only 1 colonist remains. The gain_colonist effect uses _add_colonist() same as hiring and updates peak_colonists. All 6 event messages support {amount} format substitution.
