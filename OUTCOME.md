# Outcome

## Summary
Implemented Trading Caravan Events (F3). Every 150 ticks a trading caravan arrives offering a
random resource exchange. The player has 30 ticks to accept via `ActionAcceptTrade` before the
caravan departs. Five trade types are available (wood→gold, food→stone, planks→iron, stone→gold,
iron→gold).

## Changes Made
- Added `CARAVAN_INTERVAL_TICKS=150`, `CARAVAN_OFFER_DURATION_TICKS=30`, and `CARAVAN_TRADES` list
  of 5 trade dicts to `config.py`
- Added `ActionAcceptTrade` dataclass to `entities.py`
- Added `caravan_timer: int = 0` and `current_trade: dict | None = None` fields to `GameState` in
  `state.py`, with full `to_dict` / `from_dict` support
- Added `_process_caravan()` (handles arrival and expiry) and `_handle_accept_trade()` (validates
  resources and executes swap) to `engine.py`; wired into `tick()` and `apply_action()`

## Files Modified
- `game/core/config.py`
- `game/core/entities.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 584 | 500.7 | 0.0 |
| production_rush | 1.00 | 610 | 500.3 | 0.0 |
| balanced | 1.00 | 584 | 500.7 | 0.0 |
| gold_rush | 1.00 | 587 | 500.6 | 0.0 |

## Delta vs Baseline
All strategies maintain 100% win rate. Tick counts are similar to baseline (±30 ticks), no
starvations. The caravan events are available but the headless strategies do not call
`ActionAcceptTrade`, so the trades fire passively without affecting win/loss outcomes.

## Acceptance Criteria Results
- [x] `hasattr(config, 'CARAVAN_TRADES')` — PASS
- [x] `len(config.CARAVAN_TRADES) >= 4` — PASS
- [x] `from game.core.entities import ActionAcceptTrade` — PASS
- [x] `hasattr(new_game(), 'caravan_timer')` — PASS
- [x] `'caravan_timer' in json.loads(new_game().to_json())` — PASS
- [x] Serialization roundtrip — PASS
- [x] `ruff format` + `ruff check` — PASS

## PR URL
https://github.com/Mistborn/ctes-game/pull/22

## Status
success

## Notes
The headless playtest strategies do not interact with caravans (they never issue `ActionAcceptTrade`),
so the balance metrics are unaffected. The caravan is purely an opt-in mechanic for the interactive
player or future LLM agent strategies.
