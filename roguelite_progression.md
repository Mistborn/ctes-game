# Roguelite Progression — Future Ideas

## Run Modifiers / Curses
- Opt-in difficulty modifiers at run start for bonus LP multiplier
  - "Drought" — farms -25% food, +30% LP
  - "Heavy Tribute" — tributes +50% harder, +50% LP
  - "Hard Winter" — winter length doubled, +25% LP
  - "Plague Year" — colonist consumption +20%, +20% LP

## Upgrade Tree Expansions
- `granary` — food cap increased from 9999 to 30000
- `extra_market_1` — start with 1 free Market
- `fast_start` — begin at tick 50 with extra workers already assigned
- `gold_stockpile_1` — start with 50 gold
- `gold_stockpile_2` — start with 150 gold (requires gold_stockpile_1)
- `quarry_knowledge` — Quarry worker rate +20%
- `double_passive` — All passive income doubled (stacks with guild_halls research)

## Raiders / Barracks System
- Raiders arrive every N ticks (configurable by difficulty)
- Build a Barracks to train guards (consume food + wood)
- Insufficient guards → colonists lost or resources stolen
- Defeating raids gives bonus LP

## Daily Challenge (Seeded Runs)
- Seed determines: tribute schedule, raider timing, starting weather pattern
- Global leaderboard LP comparison for a given date seed

## Multiple Win Conditions
- Current: accumulate 500 gold
- "Colony Milestone" — reach 15 colonists
- "Research Victory" — research all 5 technologies
- "Tribute Marathon" — pay 10 tributes in a single run

## Granary Building
- Separate food storage building (like current buildings)
- Each Granary adds +5000 food cap
- Passive cooling effect: reduces winter food mult slightly

## Prestige / Legacy Tiers
- After 5 wins: unlock "Veteran" LP multiplier (+25% all LP earned)
- After 10 wins: unlock "Champion" tier — new harder tribute schedule
- Season-based LP bonuses: surviving every winter in a run gives +20 LP per winter

## UI Improvements
- Run history graph (LP earned per run)
- Upgrade dependency tree visualisation
- Season progress indicator (arc showing position in 400-tick cycle)
