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
# UI Layout — panels, fonts, buttons
# ---------------------------------------------------------------------------
LEFT_PANEL_WIDTH = 480       # was 320 at 1280×720
RIGHT_PANEL_WIDTH = 600      # was 400
BOTTOM_BAR_HEIGHT = 80       # was 60
PANEL_PADDING = 24           # was 16
FONT_SIZE_LARGE = 32         # was 22
FONT_SIZE_MEDIUM = 24        # was 17
FONT_SIZE_SMALL = 18         # was 13

# Worker assignment +/- buttons
WORKER_BTN_WIDTH = 40        # was 28
WORKER_BTN_HEIGHT = 34       # was 24

# ---------------------------------------------------------------------------
# Layout spacing — every pixel offset lives here.
# To retarget a different resolution, only touch this section + the window
# dimensions above.
# ---------------------------------------------------------------------------

# Vertical line-height gaps after headings / data rows
LINE_HEIGHT_LARGE = 48       # gap after a FONT_SIZE_LARGE heading
LINE_HEIGHT_MED   = 30       # gap after a FONT_SIZE_MEDIUM label or heading
LINE_HEIGHT_SMALL = 24       # gap after a FONT_SIZE_SMALL data row

# Gaps around horizontal divider lines
DIVIDER_PADDING = 16         # vertical space after a divider
SECTION_GAP     = 18         # extra breathing room between major sections

# Win-target progress bar
PROGRESS_BAR_HEIGHT = 20     # was 14

# Resource rows (left panel)
RESOURCE_VALUE_X   = 120     # x-offset from row origin to value column  (was 80)
RESOURCE_RATE_X    = 280     # x-offset from row origin to rate column   (was 180)
RESOURCE_ROW_HEIGHT = 34     # total height consumed per resource row    (was 26)

# Building rows (right panel)
WORKER_PIP_SIZE    = 14      # side length of each worker-slot pip       (was 10)
WORKER_PIP_GAP     = 3       # gap between pips                          (was 2)
BUILDING_HINT_Y    = 20      # y-offset from pip row to production hint  (was 14)
BUILDING_ROW_HEIGHT = 82     # total height consumed per building row    (was 56)
BUILDING_ROW_GAP   = 6       # extra gap between buildings               (was 4)

# Build buttons (right panel construct section)
BUILD_BTN_HEIGHT = 40        # rect height of a 'Build X' button         (was 28)
BUILD_BTN_GAP    = 8         # gap between consecutive build buttons     (was 6)

# Bottom bar layout (all x-positions relative to bar left edge)
BOTTOM_BAR_TICK_W        = 270   # width of tick counter column         (was 180)
BOTTOM_BAR_SPEED_LABEL_W = 100   # width of "Speed:" label              (was 68)
BOTTOM_BAR_SPEED_ITEM_W  = 68    # width per speed option ("1x" etc.)   (was 46)
BOTTOM_BAR_COLONIST_GAP  = 30    # gap before colonist count            (was 20)
BOTTOM_BAR_STARVE_GAP    = 300   # gap before starvation count          (was 200)

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
