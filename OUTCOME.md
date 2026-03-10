# Outcome

## Summary
Implemented the Seasonal Harvest Bonus feature. At summer→winter transitions, players with food > 100 gain 10% of current food as gold (harvest festival). At winter→summer transitions, players with wood > 50 gain 5% of current wood as planks (spring crafting). The `last_season_was_winter` boolean on `GameState` tracks season transitions and is fully JSON-serializable.

## Changes Made
- Added 4 constants to `config.py`: `HARVEST_FOOD_THRESHOLD=100`, `HARVEST_GOLD_FRACTION=0.10`, `SPRING_WOOD_THRESHOLD=50`, `SPRING_PLANKS_FRACTION=0.05`
- Added `last_season_was_winter: bool = False` field to `GameState`
- Updated `to_dict()` and `from_dict()` in `state.py` to include `last_season_was_winter`
- Added seasonal bonus logic in `engine.tick()` after existing season transition detection; fires once per transition using `_is_winter_for_state()` (respects hard_winter curse)

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 584 | 500.70 | 0.0 |
| production_rush | 1.00 | 610 | 500.30 | 0.0 |
| balanced | 1.00 | 584 | 500.70 | 0.0 |
| gold_rush | 1.00 | 587 | 500.60 | 0.0 |

## Delta vs Baseline
| Strategy | Ticks delta | Gold delta | Starvations delta |
|----------|-------------|------------|-------------------|
| food_first | -66 | +0.70 | 0.0 |
| production_rush | -69 | +0.30 | 0.0 |
| balanced | -66 | +0.70 | 0.0 |
| gold_rush | -63 | +0.60 | 0.0 |

All strategies win faster (fewer ticks) due to harvest festival gold bonuses accelerating progress toward the 500 gold win condition. Win rate and starvation rate unchanged.

## Acceptance Criteria Results
- [x] `hasattr(s, 'last_season_was_winter')` — PASS
- [x] `'last_season_was_winter' in json.loads(new_game().to_json())` — PASS
- [x] `hasattr(config, 'HARVEST_FOOD_THRESHOLD')` — PASS
- [x] `hasattr(config, 'HARVEST_GOLD_FRACTION')` — PASS
- [x] `hasattr(config, 'SPRING_WOOD_THRESHOLD')` — PASS
- [x] Serialization roundtrip: `s.to_json() == GameState.from_json(s.to_json()).to_json()` — PASS
- [x] `ruff format` + `ruff check` — PASS (no issues)

## PR URL
https://github.com/Mistborn/ctes-game/pull/20

## Status
success

## Notes
The harvest bonus fires at the first tick of winter (summer→winter) and at the first tick of spring (winter→summer), using `_is_winter_for_state()` which correctly respects the `hard_winter` curse. The info log messages use `"info"` type as specified. All 10 test runs per strategy produced identical results (no randomness in base strategies).
