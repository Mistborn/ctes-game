# Outcome

## Summary
Added contextual tutorial hints to the info_log system. Six hints fire once per run based on
game state conditions and are surfaced via `msg_type='info'` entries in the existing info_log.

## Changes Made
- `game/core/config.py`: Added `TUTORIAL_HINTS` list (6 hint dicts with hint_id, condition_description, message)
- `game/core/state.py`: Added `shown_hints: List[str]` field; updated `to_dict()` and `from_dict()`
- `game/core/engine.py`: Added `_check_tutorial_hints()` helper; called in `tick()` after production (step 7) before endgame check (step 8)

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
```
Strategy: FOOD_FIRST      — Win rate: 1.00, Ticks: 650, Gold: 500, Starvations: 0
Strategy: PRODUCTION_RUSH — Win rate: 1.00, Ticks: 679, Gold: 500, Starvations: 0
Strategy: BALANCED        — Win rate: 1.00, Ticks: 650, Gold: 500, Starvations: 0
Strategy: GOLD_RUSH       — Win rate: 1.00, Ticks: 650, Gold: 500, Starvations: 0
```

## Delta vs Baseline
No change. All strategies win at the same tick counts with the same gold. Tutorial hints are
read-only observations of state — they do not affect resources or logic.

## Acceptance Criteria Results
- `hasattr(s, 'shown_hints')` ✅
- `isinstance(s.shown_hints, list)` ✅
- `'shown_hints' in json.loads(s.to_json())` ✅
- `hasattr(config, 'TUTORIAL_HINTS')` ✅
- `len(config.TUTORIAL_HINTS) >= 5` ✅ (6 hints)
- Serialization roundtrip `s.to_json() == GameState.from_json(s.to_json()).to_json()` ✅
- `ruff format` + `ruff check` clean ✅

## PR URL
https://github.com/Mistborn/ctes-game/pull/9

## Status
success

## Notes
The remote branch already had a prior attempt (PR #9 open). This implementation supersedes it
with a clean re-implementation from the worktree. Force-pushed with --force-with-lease.
