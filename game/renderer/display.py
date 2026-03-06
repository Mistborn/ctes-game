"""
display.py — All Pygame code lives here.

Reads from GameState (via engine.get_state dict or directly).
Never imported by core/. Never writes to GameState — only emits Actions.
"""

from __future__ import annotations

import pygame
import sys
from typing import List, Optional, Any

from game.core import config
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionResearchTech,
    ActionSetSpeed,
    BuildingType,
    GameStatus,
)
from game.core.state import GameState


# ---------------------------------------------------------------------------
# Colour aliases
# ---------------------------------------------------------------------------
C = config  # short alias


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
                    elif result == "exit":
                        pygame.quit()
                        sys.exit()

            # Regular button clicks (ignored while paused or escape menu open)
            if not state.paused and not self._show_escape_menu:
                for btn in self._buttons:
                    result = btn.handle_event(event)
                    if result is not None:
                        actions.append(result)

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

        self._draw_left_panel(state)
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
        progress = min(state.gold / C.WIN_GOLD_TARGET, 1.0)
        bar_w    = C.LEFT_PANEL_WIDTH - x * 2
        bar_bg   = pygame.Rect(x, y, bar_w, C.PROGRESS_BAR_HEIGHT)
        bar_fill = pygame.Rect(x, y, int(bar_w * progress), C.PROGRESS_BAR_HEIGHT)
        pygame.draw.rect(self.screen, C.COLOR_BTN_NORMAL,    bar_bg,   border_radius=3)
        pygame.draw.rect(self.screen, C.COLOR_GOLD,          bar_fill, border_radius=3)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER,  bar_bg,   width=1, border_radius=3)
        y += C.PROGRESS_BAR_HEIGHT + 6
        self._blit(f"{state.gold:.0f} / {C.WIN_GOLD_TARGET} Gold", self.font_small, C.COLOR_GOLD, x, y)
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
        arrival_ticks = C.COLONIST_ARRIVAL_INTERVAL_TICKS - state.ticks_since_last_arrival_check
        food_ok = state.food > C.COLONIST_ARRIVAL_MIN_FOOD_SURPLUS
        self._blit(
            f"Next arrival: {arrival_ticks} ticks {'(food OK)' if food_ok else '(need food)'}",
            self.font_small,
            C.COLOR_POSITIVE if food_ok else C.COLOR_TEXT_DISABLED,
            x, y,
        )

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
    # Right panel — buildings + worker assignment + build buttons
    # ------------------------------------------------------------------

    def _draw_right_panel(self, state: GameState) -> None:
        panel_x = C.WINDOW_WIDTH - C.RIGHT_PANEL_WIDTH
        panel_rect = pygame.Rect(
            panel_x, 0, C.RIGHT_PANEL_WIDTH, C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT
        )
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, panel_rect)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, panel_rect, width=1)

        x = panel_x + C.PANEL_PADDING
        y = C.PANEL_PADDING

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
        cost       = self._build_cost(btype)
        can_afford = state.wood >= cost
        label      = f"Build {btype.value}  (cost: {cost:.0f} Wood)"
        btn_rect   = pygame.Rect(x, y, C.RIGHT_PANEL_WIDTH - C.PANEL_PADDING * 2, C.BUILD_BTN_HEIGHT)
        btn = Button(rect=btn_rect, label=label, action=ActionBuildBuilding(building_type=btype),
                     enabled=can_afford, font=self.font_small)
        self._buttons.append(btn)
        btn.draw(self.screen)
        return y + C.BUILD_BTN_HEIGHT + 4

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

        # Box
        box_w, box_h = 400, 280
        box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BG, box_rect, border_radius=8)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, box_rect, width=2, border_radius=8)

        # Title
        title_surf = self.font_large.render("MENU", True, C.COLOR_TEXT_PRIMARY)
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 90)))

        # Buttons
        btn_w, btn_h = 280, 56
        gap = 20
        btn_y_continue = cy - btn_h - gap // 2 + 30
        btn_y_exit     = cy + gap // 2 + 30

        btn_continue = Button(
            rect=pygame.Rect(cx - btn_w // 2, btn_y_continue, btn_w, btn_h),
            label="Continue",
            action="continue",
            font=self.font_med,
        )
        btn_exit = Button(
            rect=pygame.Rect(cx - btn_w // 2, btn_y_exit, btn_w, btn_h),
            label="Exit Game",
            action="exit",
            font=self.font_med,
        )
        self._menu_buttons = [btn_continue, btn_exit]
        btn_continue.draw(self.screen)
        btn_exit.draw(self.screen)

        hint_surf = self.font_small.render("ESC to resume", True, C.COLOR_TEXT_DISABLED)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(cx, cy + box_h // 2 - 20)))

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

        big_font   = pygame.font.SysFont("Consolas", 72, bold=True)
        sub_font   = pygame.font.SysFont("Consolas", 28)
        title_surf = big_font.render(title, True, color)
        sub_surf   = sub_font.render(subtitle, True, C.COLOR_TEXT_PRIMARY)
        hint_surf  = self.font_small.render("Close the window to exit.", True, C.COLOR_TEXT_DISABLED)

        cx, cy = C.WINDOW_WIDTH // 2, C.WINDOW_HEIGHT // 2
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 60)))
        self.screen.blit(sub_surf,   sub_surf.get_rect(center=(cx, cy + 14)))
        self.screen.blit(hint_surf,  hint_surf.get_rect(center=(cx, cy + 62)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
