# =============================================================================
# config.py — All numeric balance constants in one place.
# Every game mechanic number lives here. Never hardcode values elsewhere.
# =============================================================================

# ---------------------------------------------------------------------------
# Window / Display
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1200
WINDOW_TITLE = "Kingdoms of the Forgotten — Colony Builder"
TARGET_FPS = 60

# ---------------------------------------------------------------------------
# Time / Speed
# ---------------------------------------------------------------------------
# How many real-world seconds per game tick at 1x speed
SECONDS_PER_TICK_1X = 1.0
# Speed multipliers the player can cycle through with spacebar
SPEED_MULTIPLIERS = [1, 5, 10]
# Autosave every N ticks
AUTOSAVE_INTERVAL_TICKS = 1000

# ---------------------------------------------------------------------------
# Starting Resources
# ---------------------------------------------------------------------------
STARTING_FOOD = 35
STARTING_WOOD = 8
STARTING_GOLD = 0
STARTING_STONE = 0
STARTING_PLANKS = 0

# ---------------------------------------------------------------------------
# Starting Colonists
# ---------------------------------------------------------------------------
STARTING_COLONISTS = 5

# ---------------------------------------------------------------------------
# Colonist Consumption
# ---------------------------------------------------------------------------
# Food consumed per colonist per tick
FOOD_PER_COLONIST_PER_TICK = 0.5

# ---------------------------------------------------------------------------
# Colonist Recruitment
# ---------------------------------------------------------------------------
# Food cost to manually recruit a citizen via the button (base, for the first colonist)
RECRUIT_CITIZEN_FOOD_COST = 100
# Each additional colonist costs this much more than the previous one
COLONIST_COST_SCALE = 1.1

# ---------------------------------------------------------------------------
# Building Production Rates (per worker per tick)
# ---------------------------------------------------------------------------
# Farm: food produced per assigned worker per tick
FARM_FOOD_PER_WORKER_PER_TICK = 1.2

# Lumber Mill: wood produced per assigned worker per tick
LUMBERMILL_WOOD_PER_WORKER_PER_TICK = 0.8

# Passive income (produced with 0 workers, per building, per tick)
FARM_PASSIVE_FOOD_PER_TICK = 0.3
LUMBERMILL_PASSIVE_WOOD_PER_TICK = 0.2

# Market: gold produced per assigned worker per tick
# (Wood is consumed at this rate too — see MARKET_WOOD_CONSUMED_PER_WORKER_PER_TICK)
MARKET_GOLD_PER_WORKER_PER_TICK = 0.8
# Wood consumed per market worker per tick to produce gold
MARKET_WOOD_PER_WORKER_PER_TICK = 0.6
# Market with Planks (preferred over Wood): higher efficiency
MARKET_GOLD_WITH_PLANKS_PER_WORKER_PER_TICK = 1.0
MARKET_PLANKS_PER_WORKER_PER_TICK = 0.4

# Quarry: stone produced per worker per tick (+ passive)
QUARRY_STONE_PER_WORKER_PER_TICK = 0.8
QUARRY_PASSIVE_STONE_PER_TICK = 0.1

# Sawmill: converts Wood → Planks per worker per tick
SAWMILL_WOOD_PER_WORKER_PER_TICK = 0.6
SAWMILL_PLANKS_PER_WORKER_PER_TICK = 0.5

# ---------------------------------------------------------------------------
# Building Construction Costs (Wood)
# ---------------------------------------------------------------------------
FARM_BUILD_COST_WOOD = 15
LUMBERMILL_BUILD_COST_WOOD = 20
MARKET_BUILD_COST_WOOD = 50
QUARRY_BUILD_COST_WOOD = 30
SAWMILL_BUILD_COST_WOOD = 40

# ---------------------------------------------------------------------------
# Building Worker Capacity
# ---------------------------------------------------------------------------
# Maximum workers that can be assigned to a single building
FARM_MAX_WORKERS = 8
LUMBERMILL_MAX_WORKERS = 6
MARKET_MAX_WORKERS = 6
QUARRY_MAX_WORKERS = 6
SAWMILL_MAX_WORKERS = 4

# ---------------------------------------------------------------------------
# Win / Lose Conditions
# ---------------------------------------------------------------------------
# Gold required to win — scales up each run
WIN_GOLD_TARGET_BASE = 500
WIN_GOLD_TARGET_RUN2 = 2000
WIN_GOLD_TARGET_RUN_MULTIPLIER = 3.0  # applied each run after run 2
# All colonists dead → lose (handled by colonist count reaching 0)

# ---------------------------------------------------------------------------
# Resource Caps (prevent runaway accumulation / integer overflow in long runs)
# ---------------------------------------------------------------------------
FOOD_CAP = 9999
WOOD_CAP = 9999
GOLD_CAP = 9999
STONE_CAP = 9999
PLANKS_CAP = 9999

# ---------------------------------------------------------------------------
# Research — tech definitions and effect multipliers
# ---------------------------------------------------------------------------
# Each entry: tech_id, name, description, gold_cost
RESEARCH_TECHS = [
    {
        "tech_id": "crop_rotation",
        "name": "Crop Rotation",
        "description": "Farms produce 25% more food",
        "gold_cost": 80,
    },
    {
        "tech_id": "reinforced_tools",
        "name": "Reinforced Tools",
        "description": "Lumber Mills and Quarries produce 20% more",
        "gold_cost": 100,
    },
    {
        "tech_id": "trade_routes",
        "name": "Trade Routes",
        "description": "Markets produce 30% more gold",
        "gold_cost": 120,
    },
    {
        "tech_id": "guild_halls",
        "name": "Guild Halls",
        "description": "All buildings gain +50% passive income",
        "gold_cost": 150,
    },
    {
        "tech_id": "stone_masonry",
        "name": "Stone Masonry",
        "description": "Sawmills produce 30% more planks",
        "gold_cost": 200,
    },
    {
        "tech_id": "cartography",
        "name": "Cartography",
        "description": "Unlocks the World Map — explore hexes for one-time rewards",
        "gold_cost": 150,
    },
]

# Multipliers applied per tech
RESEARCH_CROP_ROTATION_FARM_MULT = 1.25
RESEARCH_REINFORCED_TOOLS_MULT = 1.20
RESEARCH_TRADE_ROUTES_MARKET_MULT = 1.30
RESEARCH_GUILD_HALLS_PASSIVE_MULT = 1.50
RESEARCH_STONE_MASONRY_SAWMILL_MULT = 1.30

# ---------------------------------------------------------------------------
# UI Layout — panels, fonts, buttons
# ---------------------------------------------------------------------------
LEFT_PANEL_WIDTH = 480  # was 320 at 1280×720
RIGHT_PANEL_WIDTH = 600  # was 400
BOTTOM_BAR_HEIGHT = 80  # was 60
PANEL_PADDING = 24  # was 16
FONT_SIZE_LARGE = 32  # was 22
FONT_SIZE_MEDIUM = 24  # was 17
FONT_SIZE_SMALL = 18  # was 13

# Worker assignment +/- buttons
WORKER_BTN_WIDTH = 40  # was 28
WORKER_BTN_HEIGHT = 34  # was 24

# ---------------------------------------------------------------------------
# Layout spacing — every pixel offset lives here.
# To retarget a different resolution, only touch this section + the window
# dimensions above.
# ---------------------------------------------------------------------------

# Vertical line-height gaps after headings / data rows
LINE_HEIGHT_LARGE = 48  # gap after a FONT_SIZE_LARGE heading
LINE_HEIGHT_MED = 30  # gap after a FONT_SIZE_MEDIUM label or heading
LINE_HEIGHT_SMALL = 24  # gap after a FONT_SIZE_SMALL data row

# Gaps around horizontal divider lines
DIVIDER_PADDING = 16  # vertical space after a divider
SECTION_GAP = 18  # extra breathing room between major sections

# Win-target progress bar
PROGRESS_BAR_HEIGHT = 20  # was 14

# Resource rows (left panel)
RESOURCE_VALUE_X = 120  # x-offset from row origin to value column  (was 80)
RESOURCE_RATE_X = 280  # x-offset from row origin to rate column   (was 180)
RESOURCE_ROW_HEIGHT = 34  # total height consumed per resource row    (was 26)

# Building rows (right panel)
WORKER_PIP_SIZE = 14  # side length of each worker-slot pip       (was 10)
WORKER_PIP_GAP = 3  # gap between pips                          (was 2)
BUILDING_HINT_Y = 20  # y-offset from pip row to production hint  (was 14)
BUILDING_ROW_HEIGHT = 82  # total height consumed per building row    (was 56)
BUILDING_ROW_GAP = 6  # extra gap between buildings               (was 4)

# Build buttons (right panel construct section)
BUILD_BTN_HEIGHT = 40  # rect height of a 'Build X' button         (was 28)
BUILD_BTN_GAP = 8  # gap between consecutive build buttons     (was 6)

# Bottom bar layout (all x-positions relative to bar left edge)
BOTTOM_BAR_TICK_W = 270  # width of tick counter column         (was 180)
BOTTOM_BAR_SPEED_LABEL_W = 100  # width of "Speed:" label              (was 68)
BOTTOM_BAR_SPEED_ITEM_W = 68  # width per speed option ("1x" etc.)   (was 46)
BOTTOM_BAR_COLONIST_GAP = 30  # gap before colonist count            (was 20)
BOTTOM_BAR_STARVE_GAP = 200  # gap before starvation count          (was 200)

# ---------------------------------------------------------------------------
# Colors (R, G, B)
# ---------------------------------------------------------------------------
COLOR_BG = (18, 14, 10)
COLOR_PANEL_BG = (30, 24, 18)
COLOR_PANEL_BORDER = (80, 65, 45)
COLOR_TEXT_PRIMARY = (230, 210, 170)
COLOR_TEXT_SECONDARY = (160, 140, 100)
COLOR_TEXT_DISABLED = (80, 70, 55)
COLOR_POSITIVE = (100, 200, 100)
COLOR_NEGATIVE = (220, 80, 80)
COLOR_GOLD = (255, 200, 50)
COLOR_FOOD = (100, 200, 80)
COLOR_WOOD = (160, 120, 70)
COLOR_STONE = (180, 170, 160)
COLOR_PLANKS = (190, 150, 80)
COLOR_IRON = (160, 130, 180)
COLOR_BTN_NORMAL = (55, 45, 32)
COLOR_BTN_HOVER = (80, 65, 45)
COLOR_BTN_DISABLED = (35, 30, 22)
COLOR_BTN_BORDER = (100, 80, 55)
COLOR_WIN = (100, 220, 120)
COLOR_LOSE = (220, 60, 60)
COLOR_BOTTOM_BAR = (22, 18, 12)
COLOR_SPEED_HIGHLIGHT = (200, 170, 80)
COLOR_WINTER = (150, 200, 255)  # icy blue for winter label
COLOR_LP = (180, 120, 255)  # purple for LP
COLOR_SEASON_NORMAL = (120, 160, 100)  # muted green for non-winter seasons
COLOR_UNLOCK = (200, 170, 80)  # gold-ish for unlocked upgrades

# ---------------------------------------------------------------------------
# Hex World Map
# ---------------------------------------------------------------------------
HEX_MAP_RADIUS = 4

# Exploration cost per ring (resource name -> amount)
HEX_EXPLORE_COST_BY_RING = {
    1: {"wood": 20},
    2: {"wood": 30, "stone": 15},
    3: {"wood": 40, "stone": 25, "gold": 30},
    4: {"wood": 50, "stone": 30, "gold": 60, "planks": 20},
}

# Weighted random terrain generation (terrain -> weight)
HEX_TERRAIN_WEIGHTS = {
    "plains": 30,
    "forest": 25,
    "hills": 20,
    "mountains": 10,
    "swamp": 10,
    "ruins": 5,
}

# One-time resource rewards per terrain type (resource name -> amount)
HEX_TERRAIN_REWARDS = {
    "plains": {"food": 80},
    "forest": {"wood": 60, "planks": 15},
    "hills": {"stone": 50},
    "mountains": {"stone": 80, "gold": 20},
    "swamp": {"food": 30, "wood": 30},
    "ruins": {"gold": 80, "planks": 30},
    "colony": {},
}

# Hex rendering
HEX_SIZE = 60
HEX_TERRAIN_COLORS = {
    "plains": (100, 160, 70),
    "forest": (30, 90, 30),
    "hills": (130, 110, 70),
    "mountains": (120, 120, 130),
    "swamp": (60, 90, 70),
    "ruins": (110, 80, 55),
    "colony": (190, 140, 45),
}
HEX_FOG_COLOR = (25, 25, 35)
HEX_FOG_BORDER_COLOR = (60, 60, 85)
HEX_EXPLORABLE_COLOR = (40, 40, 58)
HEX_BOSS_BORDER_COLOR = (200, 40, 40)

# Probability that a non-colony hex has a boss monster (rings 2+ only)
# (No longer used — boss placement is now deterministic; kept as a tombstone.)
# HEX_BOSS_CHANCE = 0.15

# ---------------------------------------------------------------------------
# Iron resource
# ---------------------------------------------------------------------------
STARTING_IRON = 0
IRON_CAP = 9999

# Iron Mine building
IRON_MINE_BUILD_COST = {"stone": 30}
IRON_MINE_MAX_WORKERS = 6
IRON_MINE_PRODUCTION = 0.5  # iron per worker per tick

# Barracks building
BARRACKS_BUILD_COST = {"wood": 60, "iron": 20}
BARRACKS_MAX_SOLDIERS = 20

# Soldier training
TRAIN_SOLDIER_COST = {"food": 10, "iron": 5}

# Boss fight
BOSS_MIN_SOLDIERS = 5  # minimum soldiers required to attempt
BOSS_STRENGTH = 8  # lower = easier; win_prob = soldiers / (soldiers + BOSS_STRENGTH)
BOSS_WIN_REWARDS = {"gold": 100, "stone": 50}
BOSS_SOLDIERS_LOST_WIN = 2  # soldiers consumed on victory
BOSS_SOLDIERS_LOST_LOSE = 5  # soldiers consumed on defeat
# Legacy Point bonus awarded the *first time ever* a boss tier is cleared (across all runs)
BOSS_LP_REWARD = 1

# ---------------------------------------------------------------------------
# Boss tier design notes
# ---------------------------------------------------------------------------
# Tier 1 — Ring 2 (current): one guaranteed boss.
#   Requirements: Iron Mine → Barracks → soldiers.
#   Reward: gold + stone + 1 LP (first kill only).
#
# Tier 2 — Ring 4 (outermost ring, placeholder ideas):
#   A harder boss requiring a larger or better-equipped army.
#   Possible mechanics to consider:
#     • Require a "Forge" building (upgrades soldiers to knights, higher combat power)
#     • Require N knights instead of N soldiers (knights = iron + planks cost)
#     • Stronger base difficulty: BOSS2_STRENGTH = 20 (vs 8 for tier 1)
#     • Steeper soldier losses on defeat: BOSS2_SOLDIERS_LOST_LOSE = 8
#     • Richer rewards: gold + planks + iron (rare post-game resources)
#     • Unlock a special meta upgrade slot instead of LP (unique one-time reward)
#     • Could have a "mini-boss escort" mechanic: 2–3 ring-4 tiles have guards
#       that must be cleared before the boss hex becomes fightable
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------
SEASON_CYCLE_TICKS = 400
WINTER_LENGTH_TICKS = 60
# In winter, farms produce food at this fraction of normal (0.5 = half)
WINTER_FOOD_PRODUCTION_MULT = 0.5
# Maximum number of entries kept in the info log
INFO_LOG_MAX_ENTRIES = 8

# ---------------------------------------------------------------------------
# Tutorial hints
# ---------------------------------------------------------------------------
# Each entry: hint_id, condition_description (human-readable), message
TUTORIAL_HINTS = [
    {
        "hint_id": "assign_workers",
        "condition_description": "tick <= 3",
        "message": "Assign colonists to the Farm and Lumber Mill to produce resources.",
    },
    {
        "hint_id": "build_market",
        "condition_description": "wood > 50 and no market exists",
        "message": "Build a Market to convert wood into gold.",
    },
    {
        "hint_id": "research_tech",
        "condition_description": "gold > 80 and no research done",
        "message": "Research a technology to boost production.",
    },
    {
        "hint_id": "explore_hexes",
        "condition_description": "cartography researched and no hex explored beyond colony",
        "message": "Explore hexes on the World Map for one-time resource rewards.",
    },
    {
        "hint_id": "train_soldiers",
        "condition_description": "boss hex explored and soldiers == 0",
        "message": "Train soldiers at the Barracks to fight the boss.",
    },
    {
        "hint_id": "gold_target_close",
        "condition_description": "gold > 0.8 * win_gold_target",
        "message": "You are close to your gold target — keep producing!",
    },
]

# ---------------------------------------------------------------------------
# Legacy Points
# ---------------------------------------------------------------------------
LP_PER_WIN = 1

# ---------------------------------------------------------------------------
# Meta upgrades
# ---------------------------------------------------------------------------
UPGRADES = [
    {
        "id": "extra_colonists_2",
        "name": "Growing Community",
        "description": "Start with 7 colonists",
        "lp_cost": 3,
        "requires": None,
    },
    {
        "id": "hearty_colonists",
        "name": "Hearty Colonists",
        "description": "Food consumption -10%",
        "lp_cost": 2,
        "requires": None,
    },
    {
        "id": "free_sawmill",
        "name": "Pre-built Workshop",
        "description": "Start with a free Sawmill",
        "lp_cost": 2,
        "requires": None,
    },
    {
        "id": "trade_connections",
        "name": "Trade Connections",
        "description": "Markets +15% gold",
        "lp_cost": 2,
        "requires": None,
    },
    {
        "id": "veteran_memory",
        "name": "Veteran Memory",
        "description": "Carry last researched tech into next run",
        "lp_cost": 3,
        "requires": None,
    },
    {
        "id": "auto_hire",
        "name": "Auto-Hire",
        "description": "Toggle: hire a worker whenever food > 100",
        "lp_cost": 2,
        "requires": None,
    },
    {
        "id": "auto_assign",
        "name": "Auto-Assign",
        "description": "Toggle: assign new workers to open building slots",
        "lp_cost": 2,
        "requires": None,
    },
]
