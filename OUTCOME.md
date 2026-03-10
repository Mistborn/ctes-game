# Outcome

## Summary
Implemented resource stockpile production bonuses (F6). When food exceeds 200, wood exceeds 150, or gold exceeds 200, passive production bonuses activate colony-wide and/or for the Market specifically.

## Changes Made
- **config.py**: Added `STOCKPILE_BONUSES` list with 3 entries: `well_fed` (+5% all production at food≥200), `abundant_timber` (+3% all production at wood≥150), `merchant_confidence` (+10% market production at gold≥200).
- **state.py**: Added `active_stockpile_bonuses: List[str]` field (default empty list); updated `to_dict` and `from_dict`.
- **engine.py**: In `tick()`, computes `active_stockpile_bonuses` before calling `_process_production()`. In `_process_production()`, derives `stockpile_all_mult` and `stockpile_market_mult` and multiplies all building outputs accordingly (Market gets both multipliers combined via `eff_market_mult`).

## Files Modified
- `game/core/config.py`
- `game/core/state.py`
- `game/core/engine.py`

## Metrics After Change
| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |
|----------|----------|--------------|-------------|-------------------|
| food_first | 1.00 | 504.0 | 500.4 | 0.0 |
| production_rush | 1.00 | 528.7 | 500.6 | 0.0 |
| balanced | 1.00 | 502.5 | 500.6 | 0.0 |
| gold_rush | 1.00 | 498.6 | 500.9 | 0.0 |

## Delta vs Baseline
| Strategy | Ticks Δ | Notes |
|----------|---------|-------|
| food_first | -146 | Faster wins due to production bonuses activating |
| production_rush | -150 | Faster wins |
| balanced | -148 | Faster wins |
| gold_rush | -151 | Faster wins |

Win rate unchanged at 1.00 for all strategies. Stockpile bonuses reward resource accumulation and accelerate production, resulting in ~23% faster wins on average. Zero starvations maintained.

## Acceptance Criteria Results
- PASS: `hasattr(config, 'STOCKPILE_BONUSES')`
- PASS: `len(config.STOCKPILE_BONUSES) >= 3`
- PASS: `hasattr(new_game(), 'active_stockpile_bonuses')`
- PASS: `'active_stockpile_bonuses' in json.loads(new_game().to_json())`
- PASS: Serialization roundtrip verified

## PR URL
(to be filled after push)

## Status
success

## Notes
- Stockpile bonuses are evaluated each tick against current resource levels before production runs.
- `stockpile_all_mult` applies to all buildings (passive and worker-based); `stockpile_market_mult` stacks on top for Market gold output.
- Existing playtest strategies do not explicitly manage stockpile thresholds, but resources naturally accumulate past thresholds mid-run, activating bonuses organically.
