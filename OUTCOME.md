# Outcome

## Summary
Added a Tier 2 boss on a ring-4 hex. The hex map initialization now places exactly one guaranteed boss on a random ring-4 hex in addition to the existing ring-2 boss. The fight handler determines boss tier from ring distance and uses tier-specific min_soldiers, strength, rewards, and soldier losses.

## Changes Made
- **config.py**: Added 6 new constants: `BOSS_TIER2_STRENGTH=15`, `BOSS_TIER2_MIN_SOLDIERS=10`, `BOSS_TIER2_REWARD={'gold': 250, 'stone': 100}`, `BOSS_TIER2_SOLDIERS_LOST_WIN=4`, `BOSS_TIER2_SOLDIERS_LOST_LOSE=8`, `BOSS_TIER2_LP_REWARD=1`.
- **engine.py** (`_initialize_hex_map`): Collect ring-4 keys alongside ring-2 keys; place one boss on a random ring-4 hex after placing the ring-2 boss.
- **engine.py** (`_handle_fight_boss`): Determine boss tier from `_ring_distance`; ring 4 uses tier-2 stats, all other rings use tier-1 stats. No new state fields needed.

## Files Modified
- `game/core/config.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy        | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|-----------------|----------|--------------|-------------|-------------------|
| food_first      | 1.00     | 650          | 500.0       | 0.0               |
| production_rush | 1.00     | 679          | 500.0       | 0.0               |
| balanced        | 1.00     | 650          | 500.0       | 0.0               |
| gold_rush       | 1.00     | 650          | 500.0       | 0.0               |

## Delta vs Baseline
No change. The tier-2 boss is placed on ring 4 which headless strategies do not explore (ring-4 exploration costs gold + planks and none of the 4 strategies attempt it). Balance is unchanged.

## Acceptance Criteria Results
- PASS: `hasattr(config, 'BOSS_TIER2_STRENGTH')`
- PASS: `config.BOSS_TIER2_STRENGTH > config.BOSS_STRENGTH` (15 > 8)
- PASS: `hasattr(config, 'BOSS_TIER2_MIN_SOLDIERS')`
- PASS: Serialization roundtrip: `s.to_json() == s2.to_json()`
- PASS: `ruff format` + `ruff check` — all passed

## PR URL
https://github.com/Mistborn/ctes-game/pull/14

## Status
success

## Notes
- No new state fields required; existing `boss_rings_cleared` list tracks per-ring clears.
- LP reward on first kill is handled by the existing `boss_rings_cleared` + `progression.end_run()` logic, which already grants 1 LP per new ring cleared.
