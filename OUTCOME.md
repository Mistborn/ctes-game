# Outcome

## Summary
Implemented the boss-gated advanced buildings framework (Feature A4). Added a `BOSS_BUILDING_GATES` registry in config, a `boss_unlocked_buildings` list on GameState, and wired up unlock logic in the boss fight handler plus a gate check in the build handler. Phase B buildings (Forge, Brewery, Workshop) will hook in automatically once their `BuildingType` enum values are added.

## Changes Made
- `game/core/config.py`: Added `BOSS_BUILDING_GATES: dict = {2: ["Forge", "Brewery"], 4: ["Workshop"]}`
- `game/core/state.py`: Added `boss_unlocked_buildings: List[str]` field; updated `to_dict` and `from_dict`
- `game/core/engine.py`:
  - `_handle_fight_boss`: On win, extend `boss_unlocked_buildings` with `BOSS_BUILDING_GATES[ring]` entries
  - `_handle_build_building`: Gate check — if building type value appears in any gate list and is not yet unlocked, refuse the build silently

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
No change — all metrics identical to baseline. The gating framework only affects Phase B building types (Forge, Brewery, Workshop) which do not yet exist as BuildingType values.

## Acceptance Criteria Results
- PASS: hasattr(s, 'boss_unlocked_buildings')
- PASS: 'boss_unlocked_buildings' in json.loads(s.to_json())
- PASS: hasattr(config, 'BOSS_BUILDING_GATES')
- PASS: isinstance(config.BOSS_BUILDING_GATES, dict)
- PASS: serialization roundtrip s.to_json() == GameState.from_json(s.to_json()).to_json()

## PR URL
https://github.com/Mistborn/ctes-game/pull/12

## Status
success

## Notes
- ruff format and ruff check both pass cleanly
- Gate entries are deduplicated on append (only added if not already in list)
