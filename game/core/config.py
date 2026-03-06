# =============================================================================
# config.py — All numeric balance constants in one place.
# Every game mechanic number lives here. Never hardcode values elsewhere.
# =============================================================================

# ---------------------------------------------------------------------------
# Window / Display
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_TITLE = "Kingdoms of the Forgotten — Colony Builder"
TARGET_FPS = 60

# ---------------------------------------------------------------------------
# Time / Speed
# ---------------------------------------------------------------------------
# How many real-world seconds per game tick at 1x speed
SECONDS_PER_TICK_1X = 1.0
# Speed multipliers the player can cycle through with spacebar
SPEED_MULTIPLIERS = [1, 5, 50]

# ---------------------------------------------------------------------------
# Starting Resources
# ---------------------------------------------------------------------------
STARTING_FOOD = 50
STARTING_WOOD = 20
STARTING_GOLD = 0

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
# Colonist Arrival
# ---------------------------------------------------------------------------
# A new colonist arrives every this many ticks if the food surplus condition is met
COLONIST_ARRIVAL_INTERVAL_TICKS = 100
# Minimum food surplus required for a new colonist to arrive
COLONIST_ARRIVAL_MIN_FOOD_SURPLUS = 10

# ---------------------------------------------------------------------------
# Building Production Rates (per worker per tick)
# ---------------------------------------------------------------------------
# Farm: food produced per assigned worker per tick
FARM_FOOD_PER_WORKER_PER_TICK = 1.5

# Lumber Mill: wood produced per assigned worker per tick
LUMBERMILL_WOOD_PER_WORKER_PER_TICK = 1.2

# Market: gold produced per assigned worker per tick
# (Wood is consumed at this rate too — see MARKET_WOOD_CONSUMED_PER_WORKER_PER_TICK)
MARKET_GOLD_PER_WORKER_PER_TICK = 0.8
# Wood consumed per market worker per tick to produce gold
MARKET_WOOD_PER_WORKER_PER_TICK = 0.6

# ---------------------------------------------------------------------------
# Building Construction Costs (Wood)
# ---------------------------------------------------------------------------
FARM_BUILD_COST_WOOD = 15
LUMBERMILL_BUILD_COST_WOOD = 20
MARKET_BUILD_COST_WOOD = 30

# ---------------------------------------------------------------------------
# Building Worker Capacity
# ---------------------------------------------------------------------------
# Maximum workers that can be assigned to a single building
FARM_MAX_WORKERS = 8
LUMBERMILL_MAX_WORKERS = 6
MARKET_MAX_WORKERS = 6

# ---------------------------------------------------------------------------
# Win / Lose Conditions
# ---------------------------------------------------------------------------
# Gold required to win
WIN_GOLD_TARGET = 500
# All colonists dead → lose (handled by colonist count reaching 0)

# ---------------------------------------------------------------------------
# Resource Caps (prevent runaway accumulation / integer overflow in long runs)
# ---------------------------------------------------------------------------
FOOD_CAP = 9999
WOOD_CAP = 9999
GOLD_CAP = 9999

# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
LEFT_PANEL_WIDTH = 320
RIGHT_PANEL_WIDTH = 400
BOTTOM_BAR_HEIGHT = 60
PANEL_PADDING = 16
FONT_SIZE_LARGE = 22
FONT_SIZE_MEDIUM = 17
FONT_SIZE_SMALL = 13

# Button dimensions for worker assignment +/-
WORKER_BTN_WIDTH = 28
WORKER_BTN_HEIGHT = 24

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
COLOR_BTN_NORMAL = (55, 45, 32)
COLOR_BTN_HOVER = (80, 65, 45)
COLOR_BTN_DISABLED = (35, 30, 22)
COLOR_BTN_BORDER = (100, 80, 55)
COLOR_WIN = (100, 220, 120)
COLOR_LOSE = (220, 60, 60)
COLOR_BOTTOM_BAR = (22, 18, 12)
COLOR_SPEED_HIGHLIGHT = (200, 170, 80)
