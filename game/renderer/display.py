"""
display.py — All Pygame code lives here.

Reads from GameState (via engine.get_state dict or directly).
Never imported by core/. Never writes to GameState — only emits Actions.
"""

from __future__ import annotations

import math
import pygame
import sys
from pathlib import Path
from typing import List, Optional, Any

from game.core import config
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionExploreHex,
    ActionRecruitCitizen,
    ActionResearchTech,
    ActionSetSpeed,
    BuildingType,
    GameStatus,
)
from game.core.state import GameState
from game.core.engine import get_season
from game.meta.progression import compute_lp_earned


# ---------------------------------------------------------------------------
# Colour aliases
# ---------------------------------------------------------------------------
C = config  # short alias


# ---------------------------------------------------------------------------
# Hex map helpers (module-level, no Pygame, no state mutation)
# ---------------------------------------------------------------------------

def _axial_to_pixel(q: int, r: int, center_x: int, center_y: int, hex_size: float) -> tuple:
    """Flat-top axial → pixel."""
    x = hex_size * 1.5 * q
    y = hex_size * (math.sqrt(3) / 2 * q + math.sqrt(3) * r)
    return int(x + center_x), int(y + center_y)


def _pixel_to_axial(px: int, py: int, center_x: int, center_y: int, hex_size: float) -> tuple:
    """Flat-top pixel → nearest axial hex (cube rounding)."""
    x = px - center_x
    y = py - center_y
    q = (2.0 / 3.0 * x) / hex_size
    r = (-1.0 / 3.0 * x + math.sqrt(3) / 3.0 * y) / hex_size
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    if abs(rq - q) > abs(rr - r) and abs(rq - q) > abs(rs - s):
        rq = -rr - rs
    elif abs(rr - r) > abs(rs - s):
        rr = -rq - rs
    return int(rq), int(rr)


def _hex_polygon(cx: int, cy: int, size: float) -> list:
    """6 vertices of a flat-top hex."""
    return [
        (cx + size * math.cos(math.radians(60 * i)),
         cy + size * math.sin(math.radians(60 * i)))
        for i in range(6)
    ]


def _hex_has_explored_neighbor(hex_tiles: dict, q: int, r: int) -> bool:
    for dq, dr in [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]:
        tile = hex_tiles.get(f"{q + dq},{r + dr}")
        if tile and tile.get("explored"):
            return True
    return False


# ---------------------------------------------------------------------------
# Button helper
# ---------------------------------------------------------------------------

class Button:
    """A simple clickable rect that emits an action when clicked."""

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        action: Any,
        enabled: bool = True,
        font: Optional[pygame.font.Font] = None,
    ):
        self.rect = rect
        self.label = label
        self.action = action
        self.enabled = enabled
        self.font = font
        self._hovered = False

    def handle_event(self, event: pygame.event.Event) -> Optional[Any]:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.enabled
            and self.rect.collidepoint(event.pos)
        ):
            return self.action
        return None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.enabled:
            bg = C.COLOR_BTN_DISABLED
            text_color = C.COLOR_TEXT_DISABLED
        elif self._hovered:
            bg = C.COLOR_BTN_HOVER
            text_color = C.COLOR_TEXT_PRIMARY
        else:
            bg = C.COLOR_BTN_NORMAL
            text_color = C.COLOR_TEXT_SECONDARY

        pygame.draw.rect(surface, bg, self.rect, border_radius=3)
        pygame.draw.rect(surface, C.COLOR_BTN_BORDER, self.rect, width=1, border_radius=3)

        if self.font:
            text_surf = self.font.render(self.label, True, text_color)
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)


# ---------------------------------------------------------------------------
# Main Renderer
# ---------------------------------------------------------------------------

class Renderer:
    """
    Owns the Pygame window, draws the UI, and collects player actions.

    Usage:
        renderer = Renderer()
        state = renderer.show_start_screen()   # blocking; returns initial GameState
        while True:
            actions = renderer.handle_events(state)
            for a in actions:
                engine.apply_action(state, a)
            renderer.draw(state)
    """

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(C.WINDOW_TITLE)
        self.screen = pygame.display.set_mode(
            (C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.FULLSCREEN
        )
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_large = pygame.font.SysFont("Consolas", C.FONT_SIZE_LARGE, bold=True)
        self.font_med   = pygame.font.SysFont("Consolas", C.FONT_SIZE_MEDIUM)
        self.font_small = pygame.font.SysFont("Consolas", C.FONT_SIZE_SMALL)

        # Button registry — rebuilt each frame
        self._buttons: List[Button] = []

        # Escape menu
        self._show_escape_menu: bool = False
        self._was_paused_before_menu: bool = False
        self._menu_buttons: List[Button] = []

        # Accumulated real time for tick scheduling
        self._tick_accumulator: float = 0.0

        # Right panel scroll state
        self._right_panel_scroll: int = 0
        self._right_panel_content_height: int = 0

        # World map view state
        self._current_view: str = "colony"  # "colony" | "world_map"
        self._hex_scroll_offset: List[int] = [0, 0]
        self._hex_drag_start: Optional[List[int]] = None

    # ------------------------------------------------------------------
    # Public: reset between runs
    # ------------------------------------------------------------------

    def reset_for_new_run(self) -> None:
        """Reset per-run renderer state ready for a fresh run."""
        self._tick_accumulator = 0.0
        self._show_escape_menu = False
        self._was_paused_before_menu = False
        self._buttons = []
        self._menu_buttons = []
        self._right_panel_scroll = 0
        self._current_view = "colony"
        self._hex_scroll_offset = [0, 0]
        self._hex_drag_start = None

    # ------------------------------------------------------------------
    # Public: start screen — blocks until the player picks an option
    # ------------------------------------------------------------------

    def show_start_screen(self, saves: list, meta=None) -> "GameState":
        """
        Display the main-menu / start screen and return the initial GameState.

        *saves* is the list returned by ``game.core.save.list_saves()``.
        *meta* is an optional MetaState; passed to new_game() when starting fresh.
        """
        from game.core import engine
        from game.core.save import load_game

        most_recent_path = saves[0]["path"] if saves else None

        while True:
            self.clock.tick(C.TARGET_FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                for btn in self._menu_buttons:
                    result = btn.handle_event(event)
                    if result == "new_game":
                        if meta is not None:
                            meta.reset()
                            meta.save()
                        return engine.new_game(meta)
                    elif result == "continue" and most_recent_path:
                        return load_game(most_recent_path)
                    elif result == "load_game":
                        loaded = self.show_load_screen(saves)
                        if loaded is not None:
                            return loaded
                        # User pressed Back — fall through to redraw start screen

            self._draw_start_screen(saves)
            pygame.display.flip()

    def show_load_screen(self, saves: list) -> Optional["GameState"]:
        """
        Display the save-selection screen.  Returns a loaded GameState, or
        None if the player pressed Back without choosing.
        """
        from game.core.save import load_game

        while True:
            self.clock.tick(C.TARGET_FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None

                for btn in self._menu_buttons:
                    result = btn.handle_event(event)
                    if result == "back":
                        return None
                    elif isinstance(result, Path):
                        return load_game(result)

            self._draw_load_screen(saves)
            pygame.display.flip()

    # ------------------------------------------------------------------
    # Public: event handling → returns list of actions to apply
    # ------------------------------------------------------------------

    def handle_events(self, state: GameState) -> List[Any]:
        actions: List[Any] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                # Escape → open/close escape menu (only while playing)
                if event.key == pygame.K_ESCAPE and state.status == GameStatus.PLAYING:
                    if self._show_escape_menu:
                        self._show_escape_menu = False
                        state.paused = self._was_paused_before_menu
                    else:
                        self._was_paused_before_menu = state.paused
                        state.paused = True
                        self._show_escape_menu = True

                # Space → pause / unpause (not while escape menu is open)
                elif event.key == pygame.K_SPACE and state.status == GameStatus.PLAYING and not self._show_escape_menu:
                    state.paused = not state.paused

                # Tab → cycle speed (only while playing and not paused)
                elif event.key == pygame.K_TAB and state.status == GameStatus.PLAYING and not state.paused and not self._show_escape_menu:
                    idx = C.SPEED_MULTIPLIERS.index(state.speed_multiplier)
                    next_idx = (idx + 1) % len(C.SPEED_MULTIPLIERS)
                    actions.append(ActionSetSpeed(C.SPEED_MULTIPLIERS[next_idx]))


            # Escape menu buttons (always active when menu is open)
            if self._show_escape_menu:
                for btn in self._menu_buttons:
                    result = btn.handle_event(event)
                    if result == "continue":
                        self._show_escape_menu = False
                        state.paused = self._was_paused_before_menu
                    elif result in ("save_and_exit", "exit_no_save"):
                        actions.append(result)

            # Regular button clicks (ignored while paused or escape menu open)
            if not state.paused and not self._show_escape_menu:
                for btn in self._buttons:
                    result = btn.handle_event(event)
                    if result == "toggle_view":
                        self._current_view = "world_map" if self._current_view == "colony" else "colony"
                    elif result is not None:
                        actions.append(result)

            # World map: right-click drag to pan
            if self._current_view == "world_map":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    self._hex_drag_start = list(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                    self._hex_drag_start = None
                elif event.type == pygame.MOUSEMOTION and self._hex_drag_start is not None:
                    self._hex_scroll_offset[0] += event.pos[0] - self._hex_drag_start[0]
                    self._hex_scroll_offset[1] += event.pos[1] - self._hex_drag_start[1]
                    self._hex_drag_start = list(event.pos)

            # World map: left-click to explore hex
            _RESOURCE_BAR_H = 40
            if (self._current_view == "world_map" and not state.paused
                    and not self._show_escape_menu
                    and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and _RESOURCE_BAR_H <= event.pos[1] < C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT):
                map_base_x = C.WINDOW_WIDTH // 2
                map_base_y = (_RESOURCE_BAR_H + C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT) // 2
                cx = map_base_x + self._hex_scroll_offset[0]
                cy = map_base_y + self._hex_scroll_offset[1]
                q, r = _pixel_to_axial(event.pos[0], event.pos[1], cx, cy, C.HEX_SIZE)
                key = f"{q},{r}"
                if key in state.hex_tiles:
                    tile = state.hex_tiles[key]
                    if not tile.get("explored") and _hex_has_explored_neighbor(state.hex_tiles, q, r):
                        actions.append(ActionExploreHex(q=q, r=r))

            # Mouse wheel scrolls the right panel (colony view only)
            if event.type == pygame.MOUSEWHEEL and self._current_view == "colony":
                panel_x = C.WINDOW_WIDTH - C.RIGHT_PANEL_WIDTH
                panel_rect = pygame.Rect(
                    panel_x, 0, C.RIGHT_PANEL_WIDTH, C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT
                )
                if panel_rect.collidepoint(pygame.mouse.get_pos()):
                    self._right_panel_scroll -= event.y * 30
                    panel_height = C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT
                    max_scroll = max(0, self._right_panel_content_height - panel_height)
                    self._right_panel_scroll = max(0, min(self._right_panel_scroll, max_scroll))

        return actions


    # ------------------------------------------------------------------
    # Public: tick accumulator
    # ------------------------------------------------------------------

    def should_tick(self, state: GameState, dt_seconds: float) -> bool:
        """
        Returns True (and resets accumulator) when enough real time has
        passed to advance one game tick at the current speed multiplier.
        """
        if state.status != GameStatus.PLAYING or state.paused:
            return False
        seconds_per_tick = C.SECONDS_PER_TICK_1X / state.speed_multiplier
        self._tick_accumulator += dt_seconds
        if self._tick_accumulator >= seconds_per_tick:
            self._tick_accumulator -= seconds_per_tick
            return True
        return False

    def tick_dt(self) -> float:
        """Advance Pygame clock and return elapsed seconds."""
        return self.clock.tick(C.TARGET_FPS) / 1000.0

    # ------------------------------------------------------------------
    # Public: draw
    # ------------------------------------------------------------------

    def draw(self, state: GameState) -> None:
        self._buttons = []       # reset each frame
        self._menu_buttons = []  # reset each frame
        self.screen.fill(C.COLOR_BG)

        if self._current_view == "world_map" and state.hex_map_unlocked:
            self._draw_world_map(state)
        else:
            # Auto-correct stale view (e.g. loaded save without cartography)
            if self._current_view == "world_map":
                self._current_view = "colony"
            self._draw_left_panel(state)
            self._draw_middle_panel(state)
            self._draw_right_panel(state)

        self._draw_bottom_bar(state)

        if state.status != GameStatus.PLAYING:
            self._draw_endgame_overlay(state)
        elif self._show_escape_menu:
            self._draw_escape_menu()
        elif state.paused:
            self._draw_pause_overlay()

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Left panel — resources + rates
    # ------------------------------------------------------------------

    def _draw_left_panel(self, state: GameState) -> None:
        panel_rect = pygame.Rect(
            0, 0, C.LEFT_PANEL_WIDTH, C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT
        )
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, panel_rect)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, panel_rect, width=1)

        x = C.PANEL_PADDING
        y = C.PANEL_PADDING

        self._blit("RESOURCES", self.font_large, C.COLOR_TEXT_PRIMARY, x, y)
        y += C.LINE_HEIGHT_LARGE
        self._divider(x, y, C.LEFT_PANEL_WIDTH - x)
        y += C.DIVIDER_PADDING

        y = self._draw_resource_row("Food",   state.food,   state.food_rate,   C.COLOR_FOOD,   x, y)
        y = self._draw_resource_row("Wood",   state.wood,   state.wood_rate,   C.COLOR_WOOD,   x, y)
        y = self._draw_resource_row("Gold",   state.gold,   state.gold_rate,   C.COLOR_GOLD,   x, y)
        y = self._draw_resource_row("Stone",  state.stone,  state.stone_rate,  C.COLOR_STONE,  x, y)
        y = self._draw_resource_row("Planks", state.planks, state.planks_rate, C.COLOR_PLANKS, x, y)

        y += C.SECTION_GAP
        self._divider(x, y, C.LEFT_PANEL_WIDTH - x)
        y += C.DIVIDER_PADDING

        # Win target progress bar
        self._blit("WIN TARGET", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += C.LINE_HEIGHT_MED
        progress = min(state.gold / state.win_gold_target, 1.0)
        bar_w    = C.LEFT_PANEL_WIDTH - x * 2
        bar_bg   = pygame.Rect(x, y, bar_w, C.PROGRESS_BAR_HEIGHT)
        bar_fill = pygame.Rect(x, y, int(bar_w * progress), C.PROGRESS_BAR_HEIGHT)
        pygame.draw.rect(self.screen, C.COLOR_BTN_NORMAL,    bar_bg,   border_radius=3)
        pygame.draw.rect(self.screen, C.COLOR_GOLD,          bar_fill, border_radius=3)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER,  bar_bg,   width=1, border_radius=3)
        y += C.PROGRESS_BAR_HEIGHT + 6
        self._blit(f"{state.gold:.0f} / {state.win_gold_target} Gold", self.font_small, C.COLOR_GOLD, x, y)
        y += C.LINE_HEIGHT_MED

        y += C.SECTION_GAP
        self._divider(x, y, C.LEFT_PANEL_WIDTH - x)
        y += C.DIVIDER_PADDING

        # Colonists
        self._blit("COLONISTS", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += C.LINE_HEIGHT_MED
        self._blit(f"Total:  {state.colonist_count}", self.font_small, C.COLOR_TEXT_PRIMARY, x, y)
        y += C.LINE_HEIGHT_SMALL
        idle_color = C.COLOR_POSITIVE if state.idle_colonists > 0 else C.COLOR_TEXT_SECONDARY
        self._blit(f"Idle:   {state.idle_colonists}", self.font_small, idle_color, x, y)
        y += C.LINE_HEIGHT_SMALL
        self._blit(
            f"Consumption: {state.colonist_count * C.FOOD_PER_COLONIST_PER_TICK:.1f}/tick",
            self.font_small, C.COLOR_TEXT_SECONDARY, x, y,
        )
        y += C.LINE_HEIGHT_SMALL
        recruit_cost = round(C.RECRUIT_CITIZEN_FOOD_COST * (C.COLONIST_COST_SCALE ** state.colonist_count))
        can_recruit = state.food >= recruit_cost
        recruit_btn = Button(
            rect=pygame.Rect(x, y, C.LEFT_PANEL_WIDTH - x * 2, C.BUILD_BTN_HEIGHT),
            label=f"Recruit Citizen  (cost: {recruit_cost} Food)",
            action=ActionRecruitCitizen(),
            enabled=can_recruit,
            font=self.font_small,
        )
        recruit_btn.draw(self.screen)
        self._buttons.append(recruit_btn)
        y += C.BUILD_BTN_HEIGHT + C.BUILD_BTN_GAP

        # Season
        y += C.SECTION_GAP
        self._divider(x, y, C.LEFT_PANEL_WIDTH - x)
        y += C.DIVIDER_PADDING

        season = get_season(state.tick)
        season_color = C.COLOR_WINTER if season == "Winter" else C.COLOR_SEASON_NORMAL
        is_winter = season == "Winter"
        food_mult_str = f" (food ×{C.WINTER_FOOD_MULT:.0f})" if is_winter else ""
        self._blit(f"Season: {season}{food_mult_str}", self.font_small, season_color, x, y)

    def _draw_resource_row(
        self, label: str, value: float, rate: float, color: tuple, x: int, y: int
    ) -> int:
        self._blit(f"{label}:", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        self._blit(f"{value:>7.1f}", self.font_med, color, x + C.RESOURCE_VALUE_X, y)
        rate_color = (
            C.COLOR_POSITIVE if rate > 0 else
            C.COLOR_NEGATIVE if rate < 0 else
            C.COLOR_TEXT_SECONDARY
        )
        self._blit(f"{rate:+.2f}/tick", self.font_small, rate_color, x + C.RESOURCE_RATE_X, y + 3)
        return y + C.RESOURCE_ROW_HEIGHT

    # ------------------------------------------------------------------
    # Middle panel — automation toggles (only when upgrades are unlocked)
    # ------------------------------------------------------------------

    def _draw_middle_panel(self, state: GameState) -> None:
        if not (state.auto_hire_unlocked or state.auto_assign_unlocked):
            return

        mid_area_x = C.LEFT_PANEL_WIDTH
        mid_area_w = C.WINDOW_WIDTH - C.RIGHT_PANEL_WIDTH - C.LEFT_PANEL_WIDTH
        panel_w = 380
        panel_x = mid_area_x + (mid_area_w - panel_w) // 2
        panel_y = C.PANEL_PADDING

        num_buttons = int(state.auto_hire_unlocked) + int(state.auto_assign_unlocked)
        panel_h = (C.PANEL_PADDING * 2 + C.LINE_HEIGHT_LARGE + C.DIVIDER_PADDING
                   + num_buttons * (C.BUILD_BTN_HEIGHT + C.BUILD_BTN_GAP))

        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, panel_rect)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, panel_rect, width=1)

        x = panel_x + C.PANEL_PADDING
        y = panel_y + C.PANEL_PADDING
        btn_w = panel_w - C.PANEL_PADDING * 2

        self._blit("AUTOMATION", self.font_large, C.COLOR_TEXT_PRIMARY, x, y)
        y += C.LINE_HEIGHT_LARGE
        self._divider(x, y, panel_x + panel_w - C.PANEL_PADDING)
        y += C.DIVIDER_PADDING

        if state.auto_hire_unlocked:
            on_off = "ON" if state.auto_hire_enabled else "OFF"
            btn = Button(
                rect=pygame.Rect(x, y, btn_w, C.BUILD_BTN_HEIGHT),
                label=f"Auto-Hire  [{on_off}]",
                action="toggle_auto_hire",
                font=self.font_small,
            )
            btn.draw(self.screen)
            self._buttons.append(btn)
            y += C.BUILD_BTN_HEIGHT + C.BUILD_BTN_GAP

        if state.auto_assign_unlocked:
            on_off = "ON" if state.auto_assign_enabled else "OFF"
            btn = Button(
                rect=pygame.Rect(x, y, btn_w, C.BUILD_BTN_HEIGHT),
                label=f"Auto-Assign  [{on_off}]",
                action="toggle_auto_assign",
                font=self.font_small,
            )
            btn.draw(self.screen)
            self._buttons.append(btn)

    # ------------------------------------------------------------------
    # Right panel — buildings + worker assignment + build buttons
    # ------------------------------------------------------------------

    def _draw_right_panel(self, state: GameState) -> None:
        panel_x = C.WINDOW_WIDTH - C.RIGHT_PANEL_WIDTH
        panel_height = C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT
        panel_rect = pygame.Rect(panel_x, 0, C.RIGHT_PANEL_WIDTH, panel_height)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, panel_rect)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, panel_rect, width=1)

        x = panel_x + C.PANEL_PADDING
        y = C.PANEL_PADDING - self._right_panel_scroll

        self.screen.set_clip(panel_rect)

        self._blit("BUILDINGS", self.font_large, C.COLOR_TEXT_PRIMARY, x, y)
        y += C.LINE_HEIGHT_LARGE
        self._divider(x, y, C.WINDOW_WIDTH - C.PANEL_PADDING)
        y += C.DIVIDER_PADDING

        for building in state.buildings:
            y = self._draw_building_row(state, building, x, y)
            y += C.BUILDING_ROW_GAP

        y += C.SECTION_GAP
        self._divider(x, y, C.WINDOW_WIDTH - C.PANEL_PADDING)
        y += C.DIVIDER_PADDING
        self._blit("CONSTRUCT", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += C.LINE_HEIGHT_MED

        for btype in [BuildingType.FARM, BuildingType.LUMBER_MILL, BuildingType.MARKET,
                      BuildingType.QUARRY, BuildingType.SAWMILL]:
            y = self._draw_build_button(state, btype, x, y)
            y += C.BUILD_BTN_GAP

        y += C.SECTION_GAP
        self._divider(x, y, C.WINDOW_WIDTH - C.PANEL_PADDING)
        y += C.DIVIDER_PADDING
        self._blit("RESEARCH", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += C.LINE_HEIGHT_MED

        for tech in C.RESEARCH_TECHS:
            y = self._draw_research_row(state, tech, x, y)
            y += C.BUILD_BTN_GAP

        # Track total content height (y is already offset by scroll)
        self._right_panel_content_height = y + self._right_panel_scroll

        self.screen.set_clip(None)

        # Draw scrollbar if content exceeds panel
        if self._right_panel_content_height > panel_height:
            self._draw_right_scrollbar(panel_x, panel_height)

    def _draw_building_row(self, state: GameState, building, x: int, y: int) -> int:
        btype   = building.building_type
        workers = building.workers_assigned
        max_w   = self._max_workers(btype)
        idle    = state.idle_colonists

        self._blit(f"[{building.id}] {btype.value}", self.font_med, C.COLOR_TEXT_PRIMARY, x, y)

        # Worker pips
        pip_y = y + C.LINE_HEIGHT_MED
        for i in range(max_w):
            pip_rect = pygame.Rect(
                x + i * (C.WORKER_PIP_SIZE + C.WORKER_PIP_GAP),
                pip_y,
                C.WORKER_PIP_SIZE,
                C.WORKER_PIP_SIZE,
            )
            pip_color = C.COLOR_POSITIVE if i < workers else C.COLOR_BTN_NORMAL
            pygame.draw.rect(self.screen, pip_color, pip_rect, border_radius=2)
            pygame.draw.rect(self.screen, C.COLOR_BTN_BORDER, pip_rect, width=1, border_radius=2)

        count_x = x + max_w * (C.WORKER_PIP_SIZE + C.WORKER_PIP_GAP) + 8
        self._blit(f"{workers}/{max_w} workers", self.font_small, C.COLOR_TEXT_SECONDARY, count_x, pip_y)

        hint = self._production_hint(btype, workers, state)
        self._blit(hint, self.font_small, C.COLOR_TEXT_SECONDARY, x, pip_y + C.BUILDING_HINT_Y)

        # +/- buttons (right-aligned)
        btn_right_x = C.WINDOW_WIDTH - C.PANEL_PADDING - C.WORKER_BTN_WIDTH
        btn_add = Button(
            rect=pygame.Rect(btn_right_x, y, C.WORKER_BTN_WIDTH, C.WORKER_BTN_HEIGHT),
            label="+",
            action=ActionAssignWorker(building_id=building.id, delta=1),
            enabled=idle > 0 and workers < max_w,
            font=self.font_med,
        )
        btn_remove = Button(
            rect=pygame.Rect(btn_right_x - C.WORKER_BTN_WIDTH - 4, y, C.WORKER_BTN_WIDTH, C.WORKER_BTN_HEIGHT),
            label="-",
            action=ActionAssignWorker(building_id=building.id, delta=-1),
            enabled=workers > 0,
            font=self.font_med,
        )
        self._buttons += [btn_add, btn_remove]
        btn_add.draw(self.screen)
        btn_remove.draw(self.screen)

        return y + C.BUILDING_ROW_HEIGHT

    def _draw_build_button(self, state: GameState, btype: BuildingType, x: int, y: int) -> int:
        existing   = sum(1 for b in state.buildings if b.building_type == btype)
        cost       = self._build_cost(btype) * (2 ** existing)
        can_afford = state.wood >= cost
        label      = f"Build {btype.value}  (cost: {cost:.0f} Wood)"
        btn_rect   = pygame.Rect(x, y, C.RIGHT_PANEL_WIDTH - C.PANEL_PADDING * 2, C.BUILD_BTN_HEIGHT)
        btn = Button(rect=btn_rect, label=label, action=ActionBuildBuilding(building_type=btype),
                     enabled=can_afford, font=self.font_small)
        self._buttons.append(btn)
        btn.draw(self.screen)
        return y + C.BUILD_BTN_HEIGHT + 4

    # ------------------------------------------------------------------
    # World map view
    # ------------------------------------------------------------------

    def _draw_world_map(self, state: GameState) -> None:
        _RESOURCE_BAR_H = 40
        map_area_top    = _RESOURCE_BAR_H
        map_area_bottom = C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT

        # --- Compact resource bar at top ---
        bar_rect = pygame.Rect(0, 0, C.WINDOW_WIDTH, _RESOURCE_BAR_H)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, bar_rect)
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER,
                         (0, _RESOURCE_BAR_H), (C.WINDOW_WIDTH, _RESOURCE_BAR_H))
        res_y = (_RESOURCE_BAR_H - C.FONT_SIZE_SMALL) // 2
        rx = C.PANEL_PADDING
        for text, color in [
            (f"Food: {state.food:.0f}",   C.COLOR_FOOD),
            (f"Wood: {state.wood:.0f}",   C.COLOR_WOOD),
            (f"Gold: {state.gold:.0f}",   C.COLOR_GOLD),
            (f"Stone: {state.stone:.0f}", C.COLOR_STONE),
            (f"Planks: {state.planks:.0f}", C.COLOR_PLANKS),
        ]:
            surf = self.font_small.render(text, True, color)
            self.screen.blit(surf, (rx, res_y))
            rx += surf.get_width() + 40

        # Win target label (right side of resource bar)
        wt_text = f"Win target: {state.gold:.0f} / {state.win_gold_target} Gold"
        wt_surf = self.font_small.render(wt_text, True, C.COLOR_GOLD)
        self.screen.blit(wt_surf, (C.WINDOW_WIDTH - wt_surf.get_width() - C.PANEL_PADDING, res_y))

        # --- Hex grid ---
        map_base_x = C.WINDOW_WIDTH // 2
        map_base_y = (map_area_top + map_area_bottom) // 2
        cx = map_base_x + self._hex_scroll_offset[0]
        cy = map_base_y + self._hex_scroll_offset[1]
        hex_size = C.HEX_SIZE

        # Determine hovered hex
        mouse_pos = pygame.mouse.get_pos()
        hq, hr = _pixel_to_axial(mouse_pos[0], mouse_pos[1], cx, cy, hex_size)
        hovered_key = f"{hq},{hr}"
        hovered_hex = (hq, hr) if hovered_key in state.hex_tiles else None

        # Clip to map area so hexes don't overdraw resource bar or bottom bar
        map_clip = pygame.Rect(0, map_area_top, C.WINDOW_WIDTH, map_area_bottom - map_area_top)
        self.screen.set_clip(map_clip)

        for key, tile in state.hex_tiles.items():
            q, r = map(int, key.split(","))
            px, py = _axial_to_pixel(q, r, cx, cy, hex_size)
            vertices = _hex_polygon(px, py, hex_size - 2)
            explored = tile.get("explored", False)
            terrain  = tile.get("terrain", "plains")

            is_explorable = not explored and _hex_has_explored_neighbor(state.hex_tiles, q, r)

            if explored:
                color = C.HEX_TERRAIN_COLORS.get(terrain, C.HEX_FOG_COLOR)
            elif is_explorable:
                color = C.HEX_EXPLORABLE_COLOR
            else:
                color = C.HEX_FOG_COLOR

            # Hover highlight
            if hovered_hex == (q, r) and (explored or is_explorable):
                color = tuple(min(255, c + 40) for c in color)

            pygame.draw.polygon(self.screen, color, vertices)

            has_boss = tile.get("has_boss", False)
            if explored and has_boss:
                border_color = C.HEX_BOSS_BORDER_COLOR
                pygame.draw.polygon(self.screen, border_color, vertices, 2)
            else:
                border_color = C.HEX_FOG_BORDER_COLOR if is_explorable else C.COLOR_PANEL_BORDER
                pygame.draw.polygon(self.screen, border_color, vertices, 1)

            # Label
            if explored:
                if terrain == "colony":
                    lbl_surf = self.font_small.render("HOME", True, C.COLOR_GOLD)
                elif has_boss:
                    lbl_surf = self.font_small.render("BOSS", True, C.HEX_BOSS_BORDER_COLOR)
                else:
                    lbl_surf = self.font_small.render(terrain[:4].upper(), True, C.COLOR_TEXT_SECONDARY)
                self.screen.blit(lbl_surf, lbl_surf.get_rect(center=(px, py)))

        self.screen.set_clip(None)

        # Tooltip
        if hovered_hex:
            tile = state.hex_tiles.get(f"{hovered_hex[0]},{hovered_hex[1]}")
            if tile:
                self._draw_hex_tooltip(state, tile, hovered_hex[0], hovered_hex[1], mouse_pos)

        # Hint
        hint_surf = self.font_small.render(
            "Left-click to explore  |  Right-drag to pan", True, C.COLOR_TEXT_DISABLED
        )
        self.screen.blit(hint_surf, (C.PANEL_PADDING, map_area_bottom - C.LINE_HEIGHT_SMALL - 4))

    def _draw_hex_tooltip(self, state: GameState, tile: dict, q: int, r: int, mouse_pos: tuple) -> None:
        terrain  = tile.get("terrain", "unknown")
        explored = tile.get("explored", False)
        ring = max(abs(q), abs(r), abs(q + r))

        lines: list = []
        if terrain == "colony":
            lines.append(("Colony (Home)", C.COLOR_GOLD))
            lines.append(("Starting location", C.COLOR_TEXT_SECONDARY))
        elif explored:
            has_boss = tile.get("has_boss", False)
            lines.append((terrain.title(), C.COLOR_TEXT_PRIMARY))
            if has_boss:
                lines.append(("Boss Monster", C.HEX_BOSS_BORDER_COLOR))
                lines.append(("(Cannot interact yet)", C.COLOR_TEXT_DISABLED))
            rewards = C.HEX_TERRAIN_REWARDS.get(terrain, {})
            if rewards:
                reward_str = "  ".join(f"+{v} {k.title()}" for k, v in rewards.items())
                lines.append((f"Reward: {reward_str}", C.COLOR_POSITIVE))
            else:
                lines.append(("No reward", C.COLOR_TEXT_DISABLED))
        else:
            is_explorable = _hex_has_explored_neighbor(state.hex_tiles, q, r)
            lines.append((f"Ring {ring} — Unexplored", C.COLOR_TEXT_SECONDARY))
            if is_explorable:
                cost = C.HEX_EXPLORE_COST_BY_RING.get(ring, {})
                if cost:
                    cost_items = [f"{v} {k.title()}" for k, v in cost.items()]
                    for i in range(0, len(cost_items), 2):
                        chunk = "  ".join(cost_items[i:i + 2])
                        prefix = "Cost: " if i == 0 else "      "
                        lines.append((prefix + chunk, C.COLOR_TEXT_PRIMARY))
                can_afford = (
                    state.wood   >= cost.get("wood", 0)
                    and state.stone  >= cost.get("stone", 0)
                    and state.gold   >= cost.get("gold", 0)
                    and state.planks >= cost.get("planks", 0)
                )
                lines.append(("Click to explore" if can_afford else "Not enough resources",
                               C.COLOR_POSITIVE if can_afford else C.COLOR_NEGATIVE))
            else:
                lines.append(("Not yet reachable", C.COLOR_TEXT_DISABLED))

        pad    = 8
        line_h = C.LINE_HEIGHT_SMALL
        box_w  = 260
        box_h  = pad * 2 + len(lines) * line_h

        tx = mouse_pos[0] + 16
        ty = mouse_pos[1] - box_h // 2
        tx = min(tx, C.WINDOW_WIDTH - box_w - 4)
        ty = max(ty, 40)
        ty = min(ty, C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT - box_h - 4)

        box_rect = pygame.Rect(tx, ty, box_w, box_h)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, box_rect, border_radius=4)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, box_rect, width=1, border_radius=4)
        for i, (text, color) in enumerate(lines):
            self._blit(text, self.font_small, color, tx + pad, ty + pad + i * line_h)

    # ------------------------------------------------------------------
    # Bottom bar
    # ------------------------------------------------------------------

    def _draw_bottom_bar(self, state: GameState) -> None:
        bar_y    = C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT
        bar_rect = pygame.Rect(0, bar_y, C.WINDOW_WIDTH, C.BOTTOM_BAR_HEIGHT)
        pygame.draw.rect(self.screen, C.COLOR_BOTTOM_BAR, bar_rect)
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (0, bar_y), (C.WINDOW_WIDTH, bar_y))

        # Vertically centre text in bar
        cy = bar_y + (C.BOTTOM_BAR_HEIGHT - C.FONT_SIZE_MEDIUM) // 2

        # Tick counter
        self._blit(f"Tick: {state.tick:>6}", self.font_med, C.COLOR_TEXT_SECONDARY, C.PANEL_PADDING, cy)

        # Speed indicator
        sx = C.BOTTOM_BAR_TICK_W
        self._blit("Speed:", self.font_med, C.COLOR_TEXT_SECONDARY, sx, cy)
        sx += C.BOTTOM_BAR_SPEED_LABEL_W
        for mult in C.SPEED_MULTIPLIERS:
            color = C.COLOR_SPEED_HIGHLIGHT if mult == state.speed_multiplier else C.COLOR_TEXT_DISABLED
            self._blit(f"{mult}x", self.font_med, color, sx, cy)
            sx += C.BOTTOM_BAR_SPEED_ITEM_W

        # Colonist count
        self._blit(f"Colonists: {state.colonist_count}", self.font_med, C.COLOR_TEXT_PRIMARY,
                   sx + C.BOTTOM_BAR_COLONIST_GAP, cy)

        # Starvation count
        starve_color = C.COLOR_NEGATIVE if state.starvation_events > 0 else C.COLOR_TEXT_SECONDARY
        self._blit(f"Starvations: {state.starvation_events}", self.font_med, starve_color,
                   sx + C.BOTTOM_BAR_COLONIST_GAP + C.BOTTOM_BAR_STARVE_GAP, cy)

        # World Map toggle button (only when cartography is researched)
        if state.hex_map_unlocked:
            toggle_label = "Colony View" if self._current_view == "world_map" else "World Map"
            toggle_btn_h = 44
            toggle_btn_y = bar_y + (C.BOTTOM_BAR_HEIGHT - toggle_btn_h) // 2
            toggle_btn = Button(
                rect=pygame.Rect(1020, toggle_btn_y, 210, toggle_btn_h),
                label=toggle_label,
                action="toggle_view",
                font=self.font_small,
            )
            self._buttons.append(toggle_btn)
            toggle_btn.draw(self.screen)

        # Status / keybind hint (right-aligned)
        if state.status == GameStatus.PLAYING:
            status_text  = "PAUSED  [SPACE = resume]" if state.paused else "SPACE = pause  |  TAB = speed  |  ESC = menu"
            status_color = C.COLOR_SPEED_HIGHLIGHT if state.paused else C.COLOR_TEXT_SECONDARY
        elif state.status == GameStatus.WIN:
            status_text, status_color = "YOU WIN!", C.COLOR_WIN
        else:
            status_text, status_color = "GAME OVER", C.COLOR_LOSE

        surf = self.font_med.render(status_text, True, status_color)
        self.screen.blit(surf, (C.WINDOW_WIDTH - surf.get_width() - C.PANEL_PADDING, cy))

    # ------------------------------------------------------------------
    # Pause overlay
    # ------------------------------------------------------------------

    def _draw_pause_overlay(self) -> None:
        overlay = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))

        big_font   = pygame.font.SysFont("Consolas", 72, bold=True)
        title_surf = big_font.render("PAUSED", True, C.COLOR_TEXT_PRIMARY)
        hint_surf  = self.font_small.render(
            "SPACE to resume  |  TAB to change speed  |  ESC for menu",
            True, C.COLOR_TEXT_DISABLED,
        )
        cx, cy = C.WINDOW_WIDTH // 2, C.WINDOW_HEIGHT // 2
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 24)))
        self.screen.blit(hint_surf,  hint_surf.get_rect(center=(cx, cy + 44)))

    # ------------------------------------------------------------------
    # Escape menu overlay
    # ------------------------------------------------------------------

    def _draw_escape_menu(self) -> None:
        overlay = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        cx, cy = C.WINDOW_WIDTH // 2, C.WINDOW_HEIGHT // 2

        # Box — tall enough for 3 buttons
        btn_w, btn_h = 300, 52
        gap = 16
        box_w  = btn_w + 80
        box_h  = 60 + 3 * btn_h + 2 * gap + 50  # title + buttons + hint
        box_top = cy - box_h // 2
        box_rect = pygame.Rect(cx - box_w // 2, box_top, box_w, box_h)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, box_rect, border_radius=8)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, box_rect, width=2, border_radius=8)

        # Title
        title_surf = self.font_large.render("MENU", True, C.COLOR_TEXT_PRIMARY)
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, box_top + 28)))

        # Buttons — stacked vertically
        btn_x   = cx - btn_w // 2
        first_y = box_top + 60

        btn_continue = Button(
            rect=pygame.Rect(btn_x, first_y, btn_w, btn_h),
            label="Continue",
            action="continue",
            font=self.font_med,
        )
        btn_save_exit = Button(
            rect=pygame.Rect(btn_x, first_y + btn_h + gap, btn_w, btn_h),
            label="Save & Exit",
            action="save_and_exit",
            font=self.font_med,
        )
        btn_exit = Button(
            rect=pygame.Rect(btn_x, first_y + 2 * (btn_h + gap), btn_w, btn_h),
            label="Exit without saving",
            action="exit_no_save",
            font=self.font_med,
        )
        self._menu_buttons = [btn_continue, btn_save_exit, btn_exit]
        btn_continue.draw(self.screen)
        btn_save_exit.draw(self.screen)
        btn_exit.draw(self.screen)

        hint_surf = self.font_small.render("ESC to resume", True, C.COLOR_TEXT_DISABLED)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(cx, box_top + box_h - 18)))

    # ------------------------------------------------------------------
    # Start screen
    # ------------------------------------------------------------------

    def _draw_start_screen(self, saves: list) -> None:
        self._menu_buttons = []
        self.screen.fill(C.COLOR_BG)

        cx, cy = C.WINDOW_WIDTH // 2, C.WINDOW_HEIGHT // 2
        has_saves = len(saves) > 0

        # Title
        title_font = pygame.font.SysFont("Consolas", 64, bold=True)
        sub_font   = pygame.font.SysFont("Consolas", 28)
        t_surf = title_font.render("KINGDOMS OF THE FORGOTTEN", True, C.COLOR_TEXT_PRIMARY)
        s_surf = sub_font.render("Medieval Fantasy Colony Builder", True, C.COLOR_TEXT_SECONDARY)
        self.screen.blit(t_surf, t_surf.get_rect(center=(cx, cy - 200)))
        self.screen.blit(s_surf, s_surf.get_rect(center=(cx, cy - 136)))

        # Three stacked buttons
        btn_w, btn_h = 340, 60
        gap = 20
        total_h = 3 * btn_h + 2 * gap
        first_y = cy - total_h // 2

        btn_new = Button(
            rect=pygame.Rect(cx - btn_w // 2, first_y, btn_w, btn_h),
            label="New Game",
            action="new_game",
            font=self.font_large,
        )
        btn_cont = Button(
            rect=pygame.Rect(cx - btn_w // 2, first_y + btn_h + gap, btn_w, btn_h),
            label="Continue",
            action="continue",
            enabled=has_saves,
            font=self.font_large,
        )
        btn_load = Button(
            rect=pygame.Rect(cx - btn_w // 2, first_y + 2 * (btn_h + gap), btn_w, btn_h),
            label="Load Game",
            action="load_game",
            enabled=has_saves,
            font=self.font_large,
        )
        self._menu_buttons = [btn_new, btn_cont, btn_load]
        btn_new.draw(self.screen)
        btn_cont.draw(self.screen)
        btn_load.draw(self.screen)

        # Most-recent save info beneath the Continue button
        info_y = first_y + btn_h + gap + btn_h + 10
        if has_saves:
            s = saves[0]
            info_text = (
                f"{s['name']}  \u2014  {s['datetime_str']}  \u2014  "
                f"Tick {s['tick']}  |  {s['gold']:.0f} Gold  |  {s['colonists']} Colonists"
            )
            info_surf = self.font_small.render(info_text, True, C.COLOR_TEXT_DISABLED)
            self.screen.blit(info_surf, info_surf.get_rect(center=(cx, info_y)))
        else:
            no_save_surf = self.font_small.render("(no saved games)", True, C.COLOR_TEXT_DISABLED)
            self.screen.blit(no_save_surf, no_save_surf.get_rect(center=(cx, info_y)))

        hint_surf = self.font_small.render("ESC to quit", True, C.COLOR_TEXT_DISABLED)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(cx, C.WINDOW_HEIGHT - 40)))

    # ------------------------------------------------------------------
    # Load-game screen
    # ------------------------------------------------------------------

    def _draw_load_screen(self, saves: list) -> None:
        self._menu_buttons = []
        self.screen.fill(C.COLOR_BG)

        cx = C.WINDOW_WIDTH // 2

        # Title
        title_surf = self.font_large.render("LOAD GAME", True, C.COLOR_TEXT_PRIMARY)
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, 60)))

        # Column layout
        row_h      = 64
        row_w      = 1200
        row_x      = cx - row_w // 2
        list_top   = 120
        max_rows   = min(len(saves), 12)

        for i in range(max_rows):
            s    = saves[i]
            rect = pygame.Rect(row_x, list_top + i * (row_h + 6), row_w, row_h)
            btn  = Button(
                rect=rect,
                label="",          # drawn manually below
                action=s["path"],
                font=self.font_small,
            )
            self._menu_buttons.append(btn)

            # Draw background
            hover_bg = C.COLOR_BTN_HOVER if btn._hovered else C.COLOR_BTN_NORMAL
            pygame.draw.rect(self.screen, hover_bg, rect, border_radius=4)
            pygame.draw.rect(self.screen, C.COLOR_BTN_BORDER, rect, width=1, border_radius=4)

            # Columns: name + date | tick | gold | colonists
            pad  = 16
            cy_r = rect.centery
            name_col  = row_x + pad
            date_col  = row_x + 220
            tick_col  = row_x + 560
            gold_col  = row_x + 760
            pop_col   = row_x + 980

            name_surf = self.font_med.render(s["name"], True, C.COLOR_TEXT_PRIMARY)
            date_surf = self.font_small.render(s["datetime_str"], True, C.COLOR_TEXT_SECONDARY)
            tick_surf = self.font_small.render(f"Tick {s['tick']}", True, C.COLOR_TEXT_SECONDARY)
            gold_surf = self.font_small.render(f"{s['gold']:.0f} Gold", True, C.COLOR_GOLD)
            pop_surf  = self.font_small.render(f"{s['colonists']} Colonists", True, C.COLOR_TEXT_SECONDARY)

            self.screen.blit(name_surf, name_surf.get_rect(midleft=(name_col, cy_r)))
            self.screen.blit(date_surf, date_surf.get_rect(midleft=(date_col, cy_r)))
            self.screen.blit(tick_surf, tick_surf.get_rect(midleft=(tick_col, cy_r)))
            self.screen.blit(gold_surf, gold_surf.get_rect(midleft=(gold_col, cy_r)))
            self.screen.blit(pop_surf,  pop_surf.get_rect(midleft=(pop_col,  cy_r)))

        # Back button
        btn_back = Button(
            rect=pygame.Rect(cx - 140, C.WINDOW_HEIGHT - 100, 280, 54),
            label="Back",
            action="back",
            font=self.font_med,
        )
        self._menu_buttons.append(btn_back)
        btn_back.draw(self.screen)

        hint_surf = self.font_small.render("ESC to go back", True, C.COLOR_TEXT_DISABLED)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(cx, C.WINDOW_HEIGHT - 32)))

    # ------------------------------------------------------------------
    # Endgame overlay
    # ------------------------------------------------------------------

    def _draw_endgame_overlay(self, state: GameState) -> None:
        overlay = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        if state.status == GameStatus.WIN:
            title    = "VICTORY!"
            subtitle = f"You accumulated {state.gold:.0f} Gold in {state.tick} ticks!"
            color    = C.COLOR_WIN
        else:
            title    = "DEFEAT"
            subtitle = f"All colonists perished on tick {state.tick}."
            color    = C.COLOR_LOSE

        lp_earned = compute_lp_earned(state)

        big_font   = pygame.font.SysFont("Consolas", 72, bold=True)
        sub_font   = pygame.font.SysFont("Consolas", 28)
        title_surf = big_font.render(title, True, color)
        sub_surf   = sub_font.render(subtitle, True, C.COLOR_TEXT_PRIMARY)
        lp_surf    = sub_font.render(f"Legacy Points earned: +{lp_earned}", True, C.COLOR_LP)

        cx, cy = C.WINDOW_WIDTH // 2, C.WINDOW_HEIGHT // 2
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 80)))
        self.screen.blit(sub_surf,   sub_surf.get_rect(center=(cx, cy - 10)))
        self.screen.blit(lp_surf,    lp_surf.get_rect(center=(cx, cy + 46)))

        # "Start Next Run" button
        btn_w, btn_h = 300, 54
        btn = Button(
            rect=pygame.Rect(cx - btn_w // 2, cy + 100, btn_w, btn_h),
            label="Start Next Run",
            action="start_next_run",
            font=self.font_large,
        )
        self._buttons.append(btn)
        btn.draw(self.screen)

    # ------------------------------------------------------------------
    # Between-runs screen — blocking mini-loop
    # ------------------------------------------------------------------

    def show_between_runs_screen(self, meta, state: GameState, lp_earned: int) -> None:
        """
        Show run summary + upgrade shop. Blocks until the player clicks
        "Start Next Run". Directly mutates meta for upgrade purchases.
        """
        while True:
            self.clock.tick(C.TARGET_FPS)

            # Draw first so buttons exist when we process events next frame
            self._menu_buttons = []
            self._draw_between_runs_screen(meta, state, lp_earned)
            pygame.display.flip()

            # Process events against the buttons built during this draw
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                for btn in self._menu_buttons:
                    result = btn.handle_event(event)
                    if result == "start_next_run":
                        return
                    elif isinstance(result, str) and result.startswith("buy:"):
                        upgrade_id = result[4:]
                        meta.buy_upgrade(upgrade_id)
                        meta.save()

    def _draw_between_runs_screen(self, meta, state: GameState, lp_earned: int) -> None:
        """Render the between-runs summary and upgrade shop."""
        self.screen.fill(C.COLOR_BG)

        cx = C.WINDOW_WIDTH // 2

        # Title
        run_label = f"RUN {state.run_number} COMPLETE"
        title_surf = self.font_large.render(run_label, True, C.COLOR_TEXT_PRIMARY)
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, 44)))
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (100, 80), (C.WINDOW_WIDTH - 100, 80))

        # ---------------------------------------------------------------
        # Left: Run summary
        # ---------------------------------------------------------------
        lx, ly = 80, 110
        self._blit("RUN SUMMARY", self.font_med, C.COLOR_TEXT_SECONDARY, lx, ly)
        ly += C.LINE_HEIGHT_MED
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (lx, ly), (lx + 520, ly))
        ly += C.DIVIDER_PADDING

        if state.status == GameStatus.WIN:
            outcome_text, outcome_color = "VICTORY", C.COLOR_WIN
        else:
            outcome_text, outcome_color = "DEFEAT", C.COLOR_LOSE

        rows = [
            ("Outcome",        outcome_text,                                outcome_color),
            ("Ticks survived", str(state.tick),                             C.COLOR_TEXT_PRIMARY),
            ("Gold produced",  f"{state.total_gold_earned:.0f}",            C.COLOR_GOLD),
            ("Starvations",    str(state.starvation_events),                C.COLOR_TEXT_PRIMARY),
        ]
        for label, value, color in rows:
            self._blit(f"{label}:", self.font_small, C.COLOR_TEXT_SECONDARY, lx, ly)
            self._blit(value, self.font_small, color, lx + 240, ly)
            ly += C.LINE_HEIGHT_SMALL + 6

        ly += C.SECTION_GAP
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (lx, ly), (lx + 560, ly))
        ly += C.DIVIDER_PADDING

        self._blit(f"LP earned this run:", self.font_med, C.COLOR_TEXT_SECONDARY, lx, ly)
        self._blit(f"+{lp_earned}", self.font_med, C.COLOR_LP, lx + 300, ly)
        ly += C.LINE_HEIGHT_MED + 6
        self._blit(f"Total LP:", self.font_med, C.COLOR_TEXT_SECONDARY, lx, ly)
        self._blit(str(meta.legacy_points), self.font_med, C.COLOR_LP, lx + 300, ly)
        ly += C.LINE_HEIGHT_MED + 6

        if "veteran_memory" in meta.unlocked_upgrades and meta.carried_tech_id:
            from game.core import config as _cfg
            tech_def = next((t for t in _cfg.RESEARCH_TECHS if t["tech_id"] == meta.carried_tech_id), None)
            tech_name = tech_def["name"] if tech_def else meta.carried_tech_id
            self._blit(f"Carrying tech: {tech_name}", self.font_small, C.COLOR_TEXT_SECONDARY, lx, ly)
            ly += C.LINE_HEIGHT_SMALL

        ly += C.SECTION_GAP
        self._blit(f"Total runs: {meta.total_runs}  Wins: {meta.total_wins}", self.font_small, C.COLOR_TEXT_DISABLED, lx, ly)

        # ---------------------------------------------------------------
        # Middle: Automation upgrades
        # ---------------------------------------------------------------
        _automation_ids = {"auto_hire", "auto_assign"}
        mx, my = 700, 110
        self._blit("AUTOMATION", self.font_med, C.COLOR_TEXT_SECONDARY, mx, my)
        my += C.LINE_HEIGHT_MED
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (mx, my), (mx + 420, my))
        my += C.DIVIDER_PADDING

        for upgrade in C.UPGRADES:
            if upgrade["id"] not in _automation_ids:
                continue
            uid       = upgrade["id"]
            name      = upgrade["name"]
            desc      = upgrade["description"]
            cost      = upgrade["lp_cost"]
            is_unlocked = uid in meta.unlocked_upgrades
            can_afford  = meta.legacy_points >= cost

            if is_unlocked:
                self._blit(f"[✓] {name}", self.font_small, C.COLOR_UNLOCK, mx, my)
                self._blit(f"    {desc}", self.font_small, C.COLOR_TEXT_DISABLED, mx, my + C.LINE_HEIGHT_SMALL)
                my += C.LINE_HEIGHT_SMALL * 2 + 10
            else:
                btn_rect = pygame.Rect(mx, my, 420, C.BUILD_BTN_HEIGHT)
                lp_label = f"[{cost} LP]  {name} — {desc}"
                btn = Button(
                    rect=btn_rect,
                    label=lp_label,
                    action=f"buy:{uid}",
                    enabled=can_afford,
                    font=self.font_small,
                )
                self._menu_buttons.append(btn)
                btn.draw(self.screen)
                my += C.BUILD_BTN_HEIGHT + 10

        # ---------------------------------------------------------------
        # Right: General upgrade shop
        # ---------------------------------------------------------------
        rx, ry = 1180, 110
        self._blit("UPGRADES", self.font_med, C.COLOR_TEXT_SECONDARY, rx, ry)
        lp_surf = self.font_med.render(f"LP: {meta.legacy_points}", True, C.COLOR_LP)
        self.screen.blit(lp_surf, (rx + 680 - lp_surf.get_width(), ry))
        ry += C.LINE_HEIGHT_MED
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (rx, ry), (rx + 680, ry))
        ry += C.DIVIDER_PADDING

        for upgrade in C.UPGRADES:
            if upgrade["id"] in _automation_ids:
                continue
            uid      = upgrade["id"]
            name     = upgrade["name"]
            desc     = upgrade["description"]
            cost     = upgrade["lp_cost"]
            requires = upgrade["requires"]

            is_unlocked   = uid in meta.unlocked_upgrades
            req_met       = requires is None or requires in meta.unlocked_upgrades
            can_afford    = meta.legacy_points >= cost
            req_name      = None
            if requires:
                req_def  = next((u for u in C.UPGRADES if u["id"] == requires), None)
                req_name = req_def["name"] if req_def else requires

            if is_unlocked:
                self._blit(f"[✓] {name}", self.font_small, C.COLOR_UNLOCK, rx, ry)
                self._blit(f"    {desc}", self.font_small, C.COLOR_TEXT_DISABLED, rx, ry + C.LINE_HEIGHT_SMALL)
                ry += C.LINE_HEIGHT_SMALL * 2 + 10
            elif not req_met:
                self._blit(f"[?] {name}  ({cost} LP)", self.font_small, C.COLOR_TEXT_DISABLED, rx, ry)
                self._blit(f"    Requires: {req_name}", self.font_small, C.COLOR_TEXT_DISABLED, rx, ry + C.LINE_HEIGHT_SMALL)
                ry += C.LINE_HEIGHT_SMALL * 2 + 10
            else:
                btn_rect = pygame.Rect(rx, ry, 680, C.BUILD_BTN_HEIGHT)
                lp_label = f"[{cost} LP]  {name} — {desc}"
                btn = Button(
                    rect=btn_rect,
                    label=lp_label,
                    action=f"buy:{uid}",
                    enabled=can_afford,
                    font=self.font_small,
                )
                self._menu_buttons.append(btn)
                btn.draw(self.screen)
                ry += C.BUILD_BTN_HEIGHT + 10

        # ---------------------------------------------------------------
        # "Start Next Run" button — bottom-centre
        # ---------------------------------------------------------------
        btn_w, btn_h = 340, 60
        start_btn = Button(
            rect=pygame.Rect(cx - btn_w // 2, C.WINDOW_HEIGHT - 110, btn_w, btn_h),
            label="Start Next Run",
            action="start_next_run",
            font=self.font_large,
        )
        self._menu_buttons.append(start_btn)
        start_btn.draw(self.screen)

        hint = self.font_small.render("Buy upgrades above, then start the next run", True, C.COLOR_TEXT_DISABLED)
        self.screen.blit(hint, hint.get_rect(center=(cx, C.WINDOW_HEIGHT - 40)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _draw_right_scrollbar(self, panel_x: int, panel_height: int) -> None:
        scrollbar_w = 8
        scrollbar_x = C.WINDOW_WIDTH - scrollbar_w - 3
        track_rect = pygame.Rect(scrollbar_x, 4, scrollbar_w, panel_height - 8)
        pygame.draw.rect(self.screen, C.COLOR_BTN_NORMAL, track_rect, border_radius=4)
        thumb_h = max(20, int(panel_height * panel_height / self._right_panel_content_height))
        thumb_y = int(self._right_panel_scroll / self._right_panel_content_height * panel_height)
        thumb_rect = pygame.Rect(scrollbar_x, 4 + thumb_y, scrollbar_w, thumb_h)
        pygame.draw.rect(self.screen, C.COLOR_TEXT_SECONDARY, thumb_rect, border_radius=4)

    def _blit(self, text: str, font: pygame.font.Font, color: tuple, x: int, y: int) -> None:
        self.screen.blit(font.render(text, True, color), (x, y))

    def _divider(self, x1: int, y: int, x2: int) -> None:
        pygame.draw.line(self.screen, C.COLOR_PANEL_BORDER, (x1, y), (x2, y))

    @staticmethod
    def _max_workers(btype: BuildingType) -> int:
        return {
            BuildingType.FARM:        C.FARM_MAX_WORKERS,
            BuildingType.LUMBER_MILL: C.LUMBERMILL_MAX_WORKERS,
            BuildingType.MARKET:      C.MARKET_MAX_WORKERS,
            BuildingType.QUARRY:      C.QUARRY_MAX_WORKERS,
            BuildingType.SAWMILL:     C.SAWMILL_MAX_WORKERS,
        }[btype]

    @staticmethod
    def _build_cost(btype: BuildingType) -> float:
        return {
            BuildingType.FARM:        C.FARM_BUILD_COST_WOOD,
            BuildingType.LUMBER_MILL: C.LUMBERMILL_BUILD_COST_WOOD,
            BuildingType.MARKET:      C.MARKET_BUILD_COST_WOOD,
            BuildingType.QUARRY:      C.QUARRY_BUILD_COST_WOOD,
            BuildingType.SAWMILL:     C.SAWMILL_BUILD_COST_WOOD,
        }[btype]

    @staticmethod
    def _production_hint(btype: BuildingType, workers: int, state: GameState) -> str:
        if btype == BuildingType.FARM:
            passive = C.FARM_PASSIVE_FOOD_PER_TICK
            total = workers * C.FARM_FOOD_PER_WORKER_PER_TICK + passive
            if workers == 0:
                return f"+{passive:.2f} Food/tick (passive)"
            return f"+{total:.2f} Food/tick (+{passive:.1f} passive)"
        elif btype == BuildingType.LUMBER_MILL:
            passive = C.LUMBERMILL_PASSIVE_WOOD_PER_TICK
            total = workers * C.LUMBERMILL_WOOD_PER_WORKER_PER_TICK + passive
            if workers == 0:
                return f"+{passive:.2f} Wood/tick (passive)"
            return f"+{total:.2f} Wood/tick (+{passive:.1f} passive)"
        elif btype == BuildingType.QUARRY:
            passive = C.QUARRY_PASSIVE_STONE_PER_TICK
            total = workers * C.QUARRY_STONE_PER_WORKER_PER_TICK + passive
            if workers == 0:
                return f"+{passive:.2f} Stone/tick (passive)"
            return f"+{total:.2f} Stone/tick (+{passive:.1f} passive)"
        elif btype == BuildingType.SAWMILL:
            if workers == 0:
                return "(no workers)"
            planks = workers * C.SAWMILL_PLANKS_PER_WORKER_PER_TICK
            wood   = workers * C.SAWMILL_WOOD_PER_WORKER_PER_TICK
            return f"+{planks:.2f} Planks/tick  (-{wood:.2f} Wood/tick)"
        elif btype == BuildingType.MARKET:
            if workers == 0:
                return "(no workers)"
            gold_w  = workers * C.MARKET_GOLD_PER_WORKER_PER_TICK
            gold_p  = workers * C.MARKET_GOLD_WITH_PLANKS_PER_WORKER_PER_TICK
            wood    = workers * C.MARKET_WOOD_PER_WORKER_PER_TICK
            planks  = workers * C.MARKET_PLANKS_PER_WORKER_PER_TICK
            return f"+{gold_w:.2f} Gold (-{wood:.2f} Wood) | +{gold_p:.2f} Gold (-{planks:.2f} Planks)"
        return ""

    def _draw_research_row(self, state: GameState, tech: dict, x: int, y: int) -> int:
        tech_id    = tech["tech_id"]
        name       = tech["name"]
        desc       = tech["description"]
        cost       = tech["gold_cost"]
        researched = tech_id in state.researched_tech_ids
        can_afford = state.gold >= cost

        if researched:
            self._blit(f"[✓] {name}", self.font_small, C.COLOR_POSITIVE, x, y)
            self._blit(desc, self.font_small, C.COLOR_TEXT_DISABLED, x + 20, y + C.LINE_HEIGHT_SMALL)
            return y + C.LINE_HEIGHT_SMALL * 2
        else:
            label    = f"Research {name}  ({cost}g)"
            btn_rect = pygame.Rect(x, y, C.RIGHT_PANEL_WIDTH - C.PANEL_PADDING * 2, C.BUILD_BTN_HEIGHT)
            btn = Button(
                rect=btn_rect,
                label=label,
                action=ActionResearchTech(tech_id=tech_id),
                enabled=can_afford,
                font=self.font_small,
            )
            self._buttons.append(btn)
            btn.draw(self.screen)
            self._blit(desc, self.font_small, C.COLOR_TEXT_DISABLED, x + 4, y + C.BUILD_BTN_HEIGHT + 2)
            return y + C.BUILD_BTN_HEIGHT + C.LINE_HEIGHT_SMALL + 2
