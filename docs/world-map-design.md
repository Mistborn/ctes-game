# World Map — Second Stage Design Brainstorm

**Status:** Draft brainstorm
**Game:** Kingdoms of the Forgotten
**Date:** 2026-03-06

---

## Context: Current Game State

The player starts with 5 colonists, 50 food, 20 wood, 0 gold. Buildings: Farm, Lumber Mill, Market. Win at 500 gold. New colonists arrive every 100 ticks if food surplus > 10. The game plays out on a single-screen colony view.

The implementation team is concurrently adding: **Stone** resource, **Quarry** building, **Sawmill** (wood to planks), **Planks** resource, and a **5-node research tech tree** (unlocked with gold).

The world map is a "second stage" feature — a new layer of gameplay that opens up after the player has established a functioning colony.

---

## 1. Milestone Trigger: What Unlocks the World Map?

### Option A: Research Unlock (Recommended)

A specific tech in the research tree, e.g. "Cartography" or "Frontier Scouting", unlocks the world map. Cost: 80-120 gold (so it competes with the 500-gold win condition).

- **Pros:** Integrates naturally with the new tech tree. Player makes a meaningful choice — spend gold on scouting vs. saving for victory. Gives the tech tree a high-impact unlock that feels rewarding.
- **Cons:** If the tech tree has only 5 nodes, one being "unlock world map" might feel mandatory rather than optional.

**Presentation:** When the tech is researched, a brief narrative popup appears: *"Your scouts have mapped the lands beyond the colony. Unknown territories await."* A new "World Map" button appears in the bottom bar, pulsing once to draw attention.

### Option B: Gold Threshold

Reaching 150 gold automatically unlocks the world map (no tech required). A popup announces it.

- **Pros:** Simple, no dependency on tech tree design. Every player hits it on the way to 500.
- **Cons:** Passive — the player didn't choose to unlock it. Less interesting than a deliberate research investment. Could feel arbitrary.

### Option C: Population Milestone

Reaching 10 colonists unlocks the world map (you now have "enough hands to spare for scouting").

- **Pros:** Thematic — you need people to explore. Ties colony growth to expansion.
- **Cons:** Population growth is somewhat random (depends on food surplus timing). Could be hit very early or very late depending on strategy.

### Option D: Combined Gate — Research + Population

Require both a tech unlock AND at least 8 colonists. The tech becomes available to research only once population hits 8.

- **Pros:** Ensures the colony is in a healthy state before the player gets distracted by exploration. Multiple progress axes feel satisfying.
- **Cons:** Two gates may feel restrictive. Harder to communicate clearly.

### Recommendation

**Option A (Research Unlock)** is the strongest. It gives the player agency, integrates with existing systems, and creates an interesting gold-spending decision. If combined with Option D's population check (tech only appears at 8+ colonists), it also prevents the edge case of a starving colony trying to explore.

---

## 2. World Map Structure

### Layout: Node-Based Map (Recommended for v1)

A hand-authored map with **12-18 named locations** connected by paths. The colony sits at the center. Locations are grouped into 3 concentric rings:

- **Ring 1 (Near, 4-5 locations):** Low risk, low reward. Forests, farms, streams.
- **Ring 2 (Mid, 5-6 locations):** Moderate challenge. Ruins, villages, quarries.
- **Ring 3 (Far, 4-6 locations):** High risk, high reward. Dungeons, rival colonies, ancient sites.

Each location is a clickable node with an icon and name. Paths between nodes are visible lines.

- **Pros:** Easy to design and balance. Each location can be hand-crafted with unique events. Low implementation cost (no procedural generation needed).
- **Cons:** Fixed content — replayability depends on random events within locations, not map variety.

### Alternative: Hex Grid (v2 Candidate)

A procedurally generated hex map (e.g., 15x15 hexes) with terrain types (forest, mountain, plains, swamp, ruins). Each hex can be explored. The colony occupies the center hex.

- **Pros:** High replayability. Emergent discovery. Feels like a "real" map.
- **Cons:** Significantly harder to implement. Needs procedural generation, terrain rendering, pathfinding. Hard to hand-tune balance.

### Alternative: Point-of-Interest Reveal

The map starts as a parchment with only the colony marked. As the player explores, nearby points of interest are revealed on the parchment with ink-drawing animations. No grid — just scattered points connected by trails.

- **Pros:** Beautiful thematic feel (medieval cartography). Progressive reveal is satisfying. No need for full grid rendering.
- **Cons:** Harder to convey distance/travel time without a grid. Mid-complexity implementation.

### Fog of War

Ring 1 locations are visible (names shown) but unexplored. Ring 2 shows as "?" markers — the player can see something is there but not what. Ring 3 is completely hidden until a Ring 2 neighbor is explored. This creates a natural progression: explore near, reveal far.

### Location Types

| Type | Ring | Description | Reward Category |
|------|------|-------------|-----------------|
| **Abandoned Farm** | 1 | Overgrown fields, some food salvageable | Food (50-100), chance of 1 colonist |
| **Forest Clearing** | 1 | Dense timber stands | Wood (40-80) |
| **Stream Crossing** | 1 | Fresh water source, good fishing | Passive food bonus (+0.1/tick for 200 ticks) |
| **Hermit's Hut** | 1 | Reclusive scholar | Tech discount (next research costs 20% less gold) |
| **Crumbling Ruins** | 2 | Old fortress, partially collapsed | Stone (30-60), chance of blueprint (new building type) |
| **Wandering Village** | 2 | Displaced settlers seeking a home | 2-3 colonists join, costs 30 food |
| **Forgotten Mine** | 2 | Abandoned mineral deposit | Gold (40-80), stone (20-40) |
| **Bandit Camp** | 2 | Hostile encampment | Combat event; win: gold (60-100), lose: colonist dies |
| **Ancient Library** | 2 | Shelves of rotting scrolls | Free tech unlock OR research speed boost |
| **Rival Colony** | 3 | Competing settlement | Trade or conflict event chain |
| **Dragon's Barrow** | 3 | Lair of a creature | High-risk combat; massive gold (150-250) |
| **Sunken Temple** | 3 | Half-submerged stone structure | Unique artifact (permanent colony buff) |
| **Trading Post** | 3 | Distant merchant outpost | Repeatable resource exchange (wood for gold, etc.) |
| **The Iron Spire** | 3 | Mysterious tower | Multi-stage quest, unlocks unique building |

---

## 3. Exploration Mechanics

### How Exploration Works

The player **sends an expedition** from the colony to a target location. An expedition requires:

1. **Colonists:** 1-3 colonists are removed from the colony workforce for the expedition's duration. More colonists = better outcomes (higher success chance, better loot rolls).
2. **Supplies:** Each expedition costs a flat resource fee depending on distance:
   - Ring 1: 10 food + 5 wood
   - Ring 2: 25 food + 15 wood + 5 planks
   - Ring 3: 50 food + 30 wood + 15 planks + 20 gold
3. **Travel time:** The expedition is "in transit" for a number of ticks:
   - Ring 1: 30 ticks outbound + 30 ticks return = 60 ticks total
   - Ring 2: 60 + 60 = 120 ticks total
   - Ring 3: 100 + 100 = 200 ticks total

While in transit, those colonists are unavailable for colony work. The player sees a small expedition tracker in the UI showing "Expedition to [location]: returning in X ticks."

### Success / Failure

Each location has a **difficulty rating** (1-5). When the expedition arrives, the outcome is resolved:

- **Success chance** = 50% + (15% per colonist sent) + (10% per relevant tech researched). Capped at 95%.
  - 1 colonist, no tech: 65%
  - 2 colonists, no tech: 80%
  - 3 colonists, 1 tech: 95% (cap)
- **On success:** Location-specific rewards are granted when the expedition returns home.
- **On failure:** Partial rewards (25-50% of full). One colonist may be lost (25% chance per failure, so risk is real but not devastating).

### Alternative: Instant Resolution

Instead of travel time, exploration is instant but costs more resources. The player clicks "Explore," pays the cost, and immediately gets an event popup.

- **Pros:** Simpler. No async tracking needed.
- **Cons:** Removes the tension of waiting and the strategic cost of tying up colonists. Feels less like a "real" expedition.

### Alternative: Expedition Camp Building

The player builds an "Expedition Camp" building (costs 40 wood + 20 planks). Assign workers to it like any other building. Every 50 ticks, the camp automatically explores the nearest unrevealed location.

- **Pros:** Fits the existing building/worker paradigm perfectly. Minimal new UI.
- **Cons:** Removes player choice about where to explore. Feels passive.

### Recommendation

The **manual expedition system with travel time** is the most engaging. It creates genuine strategic tension: do you pull 2 workers off the lumber mill for 120 ticks to explore those ruins? The resource cost plus opportunity cost makes each expedition a real decision.

---

## 4. Interactions and Events

### Event Structure

Each location, when explored, triggers one of several possible **events** drawn from a weighted pool. Events are presented as a text popup with 2-3 choices.

#### Sample Event: "Crumbling Ruins"

> *Your scouts push through the collapsed gateway into what was once a great hall. Faded banners hang from the walls. In the center, a sealed stone chest sits beside a deep shaft descending into darkness.*

**Choice A:** "Open the chest." (Safe — moderate reward: 30-50 stone, 10-20 gold)
**Choice B:** "Descend into the shaft." (Risky — high reward on success: 80 gold + blueprint for Watchtower building. On failure: lose 1 colonist, gain nothing.)
**Choice C:** "Mark the location and return." (No reward, but the location can be revisited later for reduced cost.)

#### Sample Event: "Wandering Village"

> *A ragged band of settlers emerges from the treeline, their carts laden with meager possessions. Their leader approaches your scouts.*
>
> *"We've been driven from our homes by raiders. We seek shelter."*

**Choice A:** "Welcome them." (Gain 3 colonists immediately. Costs 30 food from your stockpile upon return.)
**Choice B:** "Trade supplies for information." (Costs 20 food. Reveals 2 nearby hidden locations on the map.)
**Choice C:** "Turn them away." (No effect. Location becomes permanently empty.)

### Repeatable vs. One-Time Locations

- **One-time locations** (ruins, libraries, barrows): Once explored, they're "cleared" and marked with a checkmark on the map. Cannot be revisited.
- **Repeatable locations** (trading posts, rival colonies): Can be visited multiple times but with diminishing returns or different events each time. Trading posts offer resource exchange every visit. Rival colonies escalate through a relationship track (neutral, friendly, hostile).

### Random Events (Colony-Level)

Once the world map is unlocked, the colony occasionally receives **random events** triggered by the passage of time (not tied to exploration):

| Event | Trigger | Effect |
|-------|---------|--------|
| **Merchant Caravan** | Every 300 ticks (random variance +/-50) | Offers to buy/sell resources at a rate. Player chooses. |
| **Bandit Raid** | After exploring a Bandit Camp, 20% chance per 200 ticks | Lose 10-30 of a random resource unless you have a Watchtower. |
| **Plague Rumor** | After reaching 15+ colonists, one-time | Costs 20 food to "quarantine" or lose 1-2 colonists. |
| **Wandering Scholar** | After exploring Ancient Library, one-time | Offers a free tech unlock. |

---

## 5. Integration with the Colony

### Reward Types That Feed Back

| Reward | Mechanic |
|--------|----------|
| **Bulk resources** | Flat food/wood/gold/stone/planks added to stockpile upon expedition return. |
| **Colonist recruitment** | New colonists join (added to idle pool). |
| **Tech discounts** | Next research costs X% less gold. |
| **Free tech unlocks** | A specific tech is granted without spending gold. |
| **Blueprints** | Unlock new building types not in the base game (Watchtower, Chapel, Warehouse — see below). |
| **Temporary buffs** | "+20% farm output for 200 ticks" — stored as a buff on GameState with a tick countdown. |
| **Artifacts** | Permanent passive bonuses (e.g., "Stone Idol: +0.5 gold/tick from each Market"). |
| **Trade routes** | Repeatable resource conversion at a Trading Post (e.g., 20 wood for 15 gold, once per 100 ticks). |

### New Buildings Unlockable via Exploration

| Building | Source | Cost | Effect |
|----------|--------|------|--------|
| **Watchtower** | Blueprint from Crumbling Ruins | 25 wood + 15 stone | Prevents bandit raids. No workers needed. |
| **Chapel** | Blueprint from Sunken Temple | 30 wood + 20 stone + 10 planks | Passive morale: colonist arrival interval reduced by 20% (80 ticks instead of 100). |
| **Warehouse** | Blueprint from Forgotten Mine | 40 wood + 10 planks | Doubles resource caps (9999 to 19998 — or more meaningfully, could introduce lower default caps that the Warehouse raises). |
| **Tavern** | Blueprint from Trading Post | 25 wood + 15 planks | Assign workers to passively generate gold (0.3/worker/tick) without consuming wood (unlike Market). Max 3 workers. |

### Expedition Return Mechanic

Expeditions physically "return" to the colony after the travel time elapses. Rewards are only granted upon return. This means:

- If the colony falls (all colonists die) while an expedition is out, those colonists are lost too (game over stands).
- The player must plan: can the colony survive with fewer workers for 120 ticks?
- A "Recall Expedition" button could allow aborting early (colonists return in half the remaining time, no rewards).

### Rival Colony Raids (Optional Threat)

After the player explores a **Rival Colony** location and chooses a hostile option, that rival can launch raids:

- Every 200-400 ticks, a raid event fires: "Raiders from [Rival Colony Name] approach!"
- Without a Watchtower: lose 15-40 of a random resource.
- With a Watchtower: raid is repelled, no loss.
- With a Watchtower + 2 garrison colonists: raid is repelled AND the player captures 10-20 gold from the raiders.

This creates a reason to invest in defense and adds risk to aggressive exploration choices.

---

## 6. Narrative and Theme

### Lore Hook

The colony exists because the settlers fled a catastrophe — a magical cataclysm, a war, or a plague that destroyed the old kingdoms. The world beyond the colony is the remnants of that fallen civilization: ruined cities, displaced peoples, corrupted forests, and lingering magical dangers.

The world map represents the settlers' first steps toward understanding what happened and whether the land can be reclaimed.

### Tone: Hopeful Expansion with Dark Fantasy Undertones

The core loop is optimistic — you're building, growing, and reaching out. But the world map reveals that the surrounding lands are scarred and dangerous. Events should balance **wonder** (discovering a beautiful ancient library) with **menace** (something lurks in the depths beneath it). The player should feel like a small light in a vast darkness — expanding cautiously.

### Suggested Region Names and Flavor Text

**Ring 1 — The Near Marches**
- *Greenhollow Farm* — "Overgrown but fertile. Someone tended these fields not long ago."
- *Ashwood Stand* — "The oaks here grow tall and straight. Good timber, if you can haul it back."
- *Millbrook Crossing* — "A clear stream, untouched. The fish practically leap into your hands."
- *Old Pella's Cabin* — "Smoke rises from the chimney. Someone still lives here."

**Ring 2 — The Broken Lands**
- *Fort Duskwall* — "The outer walls still stand. Inside, something has been nesting."
- *Thornfield Refugees* — "Campfires flicker between the wagons. They've been here a while."
- *The Sinkhole Mines* — "The entrance is half-collapsed, but the glint of ore is unmistakable."
- *Blackthorn Camp* — "Sharpened stakes ring the perimeter. These aren't friendly."
- *The Athenaeum* — "Rows upon rows of shelves. Most have rotted, but some volumes survive."

**Ring 3 — The Deep Wastes**
- *Ironspire Reach* — "A tower of black metal rises above the fog. It should not exist."
- *The Sunken Nave* — "Half-drowned in marsh water. The stone carvings move when you aren't looking."
- *Kaelmont Settlement* — "Another colony. Larger than yours. They don't look welcoming."
- *The Wyrm Barrow* — "Bones the size of tree trunks line the entrance. The air shimmers with heat."
- *Far Haven Trading Post* — "A ramshackle bazaar at the crossroads. Merchants from lands you've never heard of."

---

## 7. UI/UX Design

### World Map View

The world map is a **full-screen overlay** toggled by a "World Map" button in the bottom bar (next to the speed controls). Pressing the button (or a hotkey, e.g., `M`) switches from the colony view to the map view. Pressing it again (or `ESC`) returns to the colony.

**Map view layout:**

```
+-------------------------------------------------------+
|  [Back to Colony]                    [Expedition Log]  |
|                                                        |
|            * Ironspire                                 |
|           /                                            |
|      * Kaelmont --- * Wyrm Barrow                      |
|       |                  |                             |
|   * Athenaeum      * Sinkhole Mines                    |
|       |           /       |                            |
|  * Fort Duskwall *   * Blackthorn                      |
|       |         |         |                            |
|  * Greenhollow  |    * Thornfield                      |
|       \         |   /                                  |
|        * Millbrook *                                   |
|              |                                         |
|         [YOUR COLONY]                                  |
|              |                                         |
|        * Ashwood Stand                                 |
|              |                                         |
|        * Old Pella's Cabin                             |
|                                                        |
+-------------------------------------------------------+
| Food: 234  Wood: 156  Gold: 89  | Active Expeditions: 1|
+-------------------------------------------------------+
```

**Visual design:**
- Parchment/map background texture (tan, aged paper look).
- Locations rendered as icons: a house for settlements, a pickaxe for mines, a skull for dangerous areas, a "?" for unrevealed spots.
- Explored locations glow faintly. Cleared (one-time) locations are dimmed with a checkmark.
- The colony node pulses gently.
- Paths between nodes are drawn as dotted lines. Active expedition routes show a small moving dot along the path.

### Clicking a Location

Clicking an unexplored location opens a **side panel** (right side, 400px wide) with:

1. Location name and type icon.
2. Brief flavor text (1-2 sentences).
3. Difficulty rating (1-5 skulls).
4. Distance/ring indicator.
5. Expedition cost (food, wood, planks, gold listed).
6. Travel time estimate.
7. Colonist selector: choose 1, 2, or 3 colonists to send (shows current idle count).
8. "Send Expedition" button.
9. Success chance percentage (updates as you adjust colonist count).

Clicking an explored/cleared location shows its completion summary and any ongoing effects (e.g., "Trade route active: 20 wood for 15 gold every 100 ticks").

### Expedition Tracker

A small persistent widget in the colony view (not just the map view) shows active expeditions:

```
Expedition to Fort Duskwall  [##########------]  68/120 ticks
  Scouts: 2 colonists | Returns in 52 ticks
```

This appears in the left panel, below the resource display. It collapses if no expeditions are active.

### Existing UI Changes Needed

1. **Bottom bar:** Add "World Map" button (only visible after unlock). Shift colonist/starvation counters if needed.
2. **Left panel:** Add expedition tracker section below resources.
3. **Right panel:** No changes unless new exploration-unlocked buildings are added (they'd appear in the build menu like existing buildings).
4. **Event popups:** A new popup/modal system for exploration events with choice buttons. The game auto-pauses when an event popup appears.

### Managing Expeditions vs. Colony

The key UX challenge: the player needs to manage their colony while expeditions are running. Design principles:

- The colony view is always the "home" view. The map is an overlay you dip into.
- The expedition tracker on the colony view keeps the player informed without switching views.
- When an expedition returns, a brief notification appears in the colony view: "Expedition returned from Fort Duskwall! +50 stone, +20 gold."
- Event popups (choices) only appear when the expedition arrives at its destination. The game pauses and shows the event regardless of which view the player is on.

---

## 8. Phased Implementation Roadmap

### Phase 1 (v1): Minimal Viable World Map

**Goal:** A working world map with exploration that provides meaningful rewards. The simplest version that "feels like a real feature."

**Scope:**
- World map toggle (full-screen overlay with hardcoded node positions).
- 6-8 locations (Ring 1 and Ring 2 only). No Ring 3 yet.
- Expedition system: select colonists, pay resources, wait for return.
- 4-5 hand-written events with 2 choices each (no branching chains).
- Rewards: bulk resources and colonist recruitment only (no blueprints, no artifacts, no buffs).
- Simple fog of war: Ring 1 visible, Ring 2 revealed after exploring any Ring 1 neighbor.
- Expedition tracker in colony view.
- Event popup system (game pauses, 2 choices, immediate resolution text).

**Data model additions:**
- `GameState` gets: `world_map_unlocked: bool`, `expeditions: List[Expedition]`, `explored_locations: List[str]`, `revealed_locations: List[str]`.
- New dataclass `Expedition`: `target_location: str`, `colonist_ids: List[int]`, `ticks_remaining: int`, `total_ticks: int`.
- New module: `game/core/world_map.py` — location data, event definitions, expedition logic.
- Engine `tick()` calls `_process_expeditions(state)` to decrement expedition timers and trigger arrival events.

**Config additions (~15 new constants):**
- `WORLD_MAP_UNLOCK_TECH` (or gold threshold)
- `EXPEDITION_COST_RING1_FOOD`, `_WOOD`, etc.
- `EXPEDITION_TRAVEL_TICKS_RING1`, `_RING2`
- `EXPEDITION_BASE_SUCCESS_CHANCE`, `EXPEDITION_SUCCESS_PER_COLONIST`

**Estimated complexity:** Medium. The map rendering is straightforward (draw circles and lines on a background). The expedition system is essentially a timer + event trigger. Events are data-driven (dict/JSON). The biggest piece is the new UI overlay.

**Risk:** Low-medium. Core game loop is unchanged. World map is additive. The main risk is event popups interrupting gameplay flow — needs careful UX testing.

### Phase 2 (v2): Full World Map

**Goal:** Rich, replayable exploration with lasting colony impact.

**New in v2:**
- Ring 3 locations (4-6 more nodes, including Rival Colony and Dragon's Barrow).
- Blueprints: unlock 3-4 new building types through exploration.
- Artifacts: permanent passive buffs stored on GameState.
- Temporary buffs with tick countdowns.
- Rival colony raid events (requires Watchtower building).
- Trading Post repeatable interaction.
- Multi-stage quest at The Iron Spire (3 visits, escalating difficulty, unique reward).
- Random colony-level events (Merchant Caravan, Bandit Raid, Plague Rumor).
- Event branching: some events have consequences that affect future events at other locations.
- Visual polish: parchment texture, animated expedition dots, location icons, sound effects for events.

**Data model additions:**
- `GameState` gets: `artifacts: List[str]`, `active_buffs: List[Buff]`, `rival_relations: Dict[str, str]`, `trade_routes: List[TradeRoute]`.
- Buff dataclass: `buff_type: str`, `magnitude: float`, `ticks_remaining: int`.
- Event outcome flags on GameState for cross-event consequences.

**Estimated complexity:** High. Event chains, buff system, new buildings, rival AI behavior, and UI polish all add up. This is a 2-3x multiplier over Phase 1.

**Risk:** Medium. Buff stacking could break balance. Rival raids could punish exploration too harshly. Needs extensive headless playtesting with agent strategies that incorporate exploration decisions.

### Phase 3 (v3 / Future): Procedural Map + Endgame

**Speculative scope — only if v2 is successful:**
- Procedural hex-grid map generation (replaces hand-authored nodes).
- Outpost system: claim explored locations as satellite colonies with their own buildings.
- Diplomatic system with rival colonies (trade agreements, non-aggression pacts, war).
- Alternative win condition: "Unite 3 colonies under your banner" (diplomacy/conquest victory alongside gold victory).
- Narrative arc: discovering the cause of the cataclysm through exploration, leading to a "final quest."

**Complexity:** Very high. This is essentially a second game layered on top of the first. Only worth pursuing if the game finds an audience.

---

## Summary of Recommendations

| Decision | Recommendation |
|----------|----------------|
| Unlock trigger | Research tech ("Cartography"), available at 8+ colonists |
| Map structure | Node-based, hand-authored, 12-18 locations in 3 rings |
| Exploration | Manual expeditions with colonist + resource cost + travel time |
| Events | Text popups with 2-3 choices, game auto-pauses |
| Rewards | Resources, colonists, blueprints, artifacts, buffs |
| Colony integration | Expedition tracker in colony view; event popups interrupt both views |
| Threats | Rival colony raids (post-v1), preventable with Watchtower |
| Tone | Hopeful expansion with dark fantasy undertones |
| v1 scope | 6-8 nodes, basic expeditions, bulk rewards only |
| v2 scope | Full 14+ nodes, blueprints, artifacts, buffs, raids, trading |
