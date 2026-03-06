# Kingdoms of the Forgotten — Medieval Colony Builder

A medieval fantasy colony management game built with Python and Pygame.
Accumulate **500 Gold** before your colonists starve to win.

---

## Project Structure

```
ctes-game/
├── main.py                  # Entry point (normal + headless modes)
├── requirements.txt
├── README.md
└── game/
    ├── core/
    │   ├── config.py        # ALL numeric constants — rates, costs, caps
    │   ├── entities.py      # Colonist, Building, Resource dataclasses + Action types
    │   ├── state.py         # GameState — single source of truth, JSON-serialisable
    │   └── engine.py        # tick(), apply_action(), get_state() — zero Pygame
    ├── renderer/
    │   └── display.py       # All Pygame code; reads GameState, emits Actions
    └── agent/
        └── playtest.py      # Headless runner + 4 named strategies + balance report
```

**Hard rule:** `core/` never imports from `renderer/`. The engine runs fully headless.

---

## Installation

```bash
pip install -r requirements.txt
```

Python 3.11+ recommended (uses `X | Y` union syntax).

---

## Normal Mode (Interactive)

```bash
python main.py
```

Opens a **1280×720** Pygame window.

### Controls

| Input | Action |
|---|---|
| **Spacebar** | Cycle simulation speed: 1× → 5× → 50× → 1× |
| **+ / − buttons** | Assign or remove one worker from a building |
| **Build buttons** | Construct a new building (greyed out if insufficient Wood) |

### UI Layout

| Panel | Contents |
|---|---|
| **Left** | Food / Wood / Gold totals with ±/tick rates, win-target progress bar, colonist details |
| **Right** | Building list (worker pips + +/− buttons), construct-new-building buttons |
| **Bottom bar** | Tick counter · Speed indicator · Colonist count · Starvation events · Game status |

### Win / Lose

- **Win:** Accumulate **500 Gold**.
- **Lose:** All colonists starve (reach 0 population).

---

## Headless / Agent Mode

Runs with no display. Useful for balance testing and CI.

```bash
# Full balance report (all 4 strategies × 20 runs × 1000 ticks)
python main.py --headless

# Custom run count and tick limit
python main.py --headless --runs 50 --ticks 2000

# Single strategy
python main.py --headless --strategy gold_rush

# Run the agent module directly
python -m game.agent.playtest --runs 10 --ticks 500 --strategy balanced
```

The headless runner returns (and prints) a `metrics` dict per run:

| Metric | Description |
|---|---|
| `ticks_survived` | How many ticks the colony lasted |
| `gold_earned` | Final gold amount |
| `peak_colonists` | Maximum simultaneous colonists |
| `starvation_events` | Cumulative colonist deaths from starvation |
| `final_food` / `final_wood` | Resources at end of run |
| `won` | 1.0 = victory, 0.0 = defeat |

---

## Agent Strategies

Four named strategies are implemented in `game/agent/playtest.py`:

| Strategy | Description |
|---|---|
| `food_first` | Maximise farmers until ≥20 food surplus, then diversify into wood and gold |
| `production_rush` | Build 2 Lumber Mills early for high wood output, then pivot to Markets |
| `balanced` | Evenly distribute workers across all building types as they're constructed |
| `gold_rush` | Rush to a Market with minimal food safety net; maximise Gold/tick ASAP |

Each strategy demonstrates a different answer to the **core design tension**:

> *Wood can be spent to build new buildings (increasing future capacity) **or** sold at the Market for immediate Gold. Which path wins?*

---

## Game Mechanics Reference

### Resources

| Resource | Source | Sink |
|---|---|---|
| Food | Farm workers | Colonist consumption (0.5/tick each) |
| Wood | Lumber Mill workers | Building construction + Market conversion |
| Gold | Market workers (consumes Wood) | Win target (500) |

### Buildings

| Building | Build Cost | Production | Worker Cap |
|---|---|---|---|
| Farm | 15 Wood | 1.5 Food/worker/tick | 8 |
| Lumber Mill | 20 Wood | 1.2 Wood/worker/tick | 6 |
| Market | 30 Wood | 0.8 Gold/worker/tick (−0.6 Wood/worker/tick) | 6 |

### Population

- **Consumption:** 0.5 Food per colonist per tick.
- **Growth:** Every 100 ticks, if `food > 10`, one new colonist arrives.
- **Starvation:** If food runs out, colonists die (idle ones first).

### Starting State

- 5 colonists (3 on Farm, 2 on Lumber Mill)
- 50 Food · 20 Wood · 0 Gold
- 1 Farm + 1 Lumber Mill pre-built

### Speed

Spacebar cycles: **1×** (1 tick/sec) → **5×** (5 ticks/sec) → **50×** (50 ticks/sec).

---

## Running the Balance Report

```bash
python main.py --headless
```

Sample output:

```
========================================================================
  KINGDOMS OF THE FORGOTTEN — Agent Balance Report
  20 runs per strategy, up to 1000 ticks each
========================================================================

  Strategy: FOOD_FIRST
  ------------------------------------------------------------
  Metric                       Mean              Min              Max
  ------------------------------------------------------------------
  Ticks survived              847.30           632.00          1000.00
  Win rate (0/1)                0.65             0.00             1.00
  ...
```

Strategies with a win rate near 0 indicate a need for rebalancing — adjust constants in `game/core/config.py` and re-run.

---

## Architecture Notes

- `GameState` is a plain dataclass. Call `state.to_json()` at any tick to snapshot it.
- `engine.tick()` mutates state in-place. Pass `copy.deepcopy(state)` if you need immutability.
- The renderer never writes to state — it only reads from it and returns `Action` objects that the main loop feeds to `engine.apply_action()`.
- All balance tuning lives in `config.py`. No magic numbers elsewhere.
