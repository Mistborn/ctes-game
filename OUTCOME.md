# Outcome

## Summary
Implemented explored hex passive income: each explored hex on the world map now generates a small per-tick resource income based on terrain type, incentivizing exploration beyond one-time rewards.

## Changes Made
- Added `HEX_PASSIVE_INCOME` dict to `game/core/config.py` mapping terrain to resource amounts per tick.
- Added `_process_hex_passive_income()` helper to `game/core/engine.py`.
- Called the helper in `tick()` after `_process_production()`, before consumption and rate calculation.

## Files Modified
- `game/core/config.py` — added `HEX_PASSIVE_INCOME` constant
- `game/core/engine.py` — added `_process_hex_passive_income()` and call site in `tick()`

## Metrics After Change

| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 584 | 500.7 | 0.0 |
| production_rush | 1.00 | 610 | 500.3 | 0.0 |
| balanced | 1.00 | 584 | 500.7 | 0.0 |
| gold_rush | 1.00 | 587 | 500.6 | 0.0 |

## Delta vs Baseline

| Strategy | Ticks delta | Gold delta | Starvations delta |
|----------|-------------|------------|-------------------|
| food_first | -66 (faster) | +0.7 | 0.0 |
| production_rush | -69 (faster) | +0.3 | 0.0 |
| balanced | -66 (faster) | +0.7 | 0.0 |
| gold_rush | -63 (faster) | +0.6 | 0.0 |

All strategies win faster due to supplemental passive income from explored hexes.

## Acceptance Criteria Results
- [x] `hasattr(config, 'HEX_PASSIVE_INCOME')` — PASS
- [x] `'forest' in config.HEX_PASSIVE_INCOME` — PASS
- [x] `config.HEX_PASSIVE_INCOME['forest']['wood'] > 0` — PASS
- [x] `'plains' in config.HEX_PASSIVE_INCOME` — PASS
- [x] Serialization roundtrip — PASS
- [x] `ruff format` + `ruff check` — PASS

## PR URL
(to be filled after push)

## Status
success

## Notes
The hex passive income naturally scales with the number of explored hexes, rewarding players who invest in exploration. The income amounts are small (0.01-0.05 per hex per tick) so the effect is noticeable over many ticks without trivializing the economy.
