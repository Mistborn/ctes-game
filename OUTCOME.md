# Outcome

## Summary
Added the **Scholar's Insight** meta upgrade (`auto_research`, 2 LP). When toggled on, it
automatically researches the cheapest available tech each tick whenever gold exceeds 1.5x the
tech's cost. Follows the exact `auto_hire` / `auto_assign` pattern throughout the codebase.

## Changes Made
- `config.py`: Appended `auto_research` entry to `UPGRADES` list.
- `state.py`: Added `auto_research_unlocked` and `auto_research_enabled` boolean fields; updated
  `to_dict()` and `from_dict()`.
- `engine.py`: Set both fields in `new_game()` when meta unlocks the upgrade; added `_auto_research()`
  helper; called it in `tick()` immediately after the `auto_assign` block (step 6).

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy        | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|-----------------|----------|--------------|-------------|-------------------|
| food_first      | 1.00     | 650          | 500.0       | 0.0               |
| production_rush | 1.00     | 679          | 500.0       | 0.0               |
| balanced        | 1.00     | 650          | 500.0       | 0.0               |
| gold_rush       | 1.00     | 650          | 500.0       | 0.0               |

## Delta vs Baseline
No change -- all strategies perform identically to baseline. The new upgrade is only active when
unlocked via meta progression; base headless strategies do not unlock it.

## Acceptance Criteria Results
- PASS: any(u['id'] == 'auto_research' for u in config.UPGRADES)
- PASS: hasattr(new_game(), 'auto_research_unlocked')
- PASS: hasattr(new_game(), 'auto_research_enabled')
- PASS: 'auto_research_unlocked' in json.loads(new_game().to_json())
- PASS: Serialization roundtrip: s.to_json() == GameState.from_json(s.to_json()).to_json()
- PASS: ruff format + ruff check -- all clean

## PR URL
https://github.com/Mistborn/ctes-game/pull/13

## Status
success

## Notes
None.
