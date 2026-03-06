"""
display.py — All Pygame code lives here.

Reads from GameState (via engine.get_state dict or directly).
Never imported by core/. Never writes to GameState — only emits Actions.
"""

from __future__ import annotations

import pygame
import sys
from typing import List, Optional, Callable, Any

from game.core import config
from game.core.entities import (
    ActionAssignWorker,
    ActionBuildBuilding,
    ActionSetSpeed,
    BuildingType,
    GameStatus,
)
from game.core.state import GameState


# ---------------------------------------------------------------------------
# Colour aliases (pulled from config so we only change values in one place)
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
        self.screen = pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_large = pygame.font.SysFont("Consolas", C.FONT_SIZE_LARGE, bold=True)
        self.font_med = pygame.font.SysFont("Consolas", C.FONT_SIZE_MEDIUM)
        self.font_small = pygame.font.SysFont("Consolas", C.FONT_SIZE_SMALL)

        # Button registry — rebuilt each frame
        self._buttons: List[Button] = []

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

            # Spacebar cycles speed
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if state.status == GameStatus.PLAYING:
                    idx = C.SPEED_MULTIPLIERS.index(state.speed_multiplier)
                    next_idx = (idx + 1) % len(C.SPEED_MULTIPLIERS)
                    actions.append(ActionSetSpeed(C.SPEED_MULTIPLIERS[next_idx]))

            # Button clicks
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
        if state.status != GameStatus.PLAYING:
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
        self._buttons = []  # reset each frame
        self.screen.fill(C.COLOR_BG)

        self._draw_left_panel(state)
        self._draw_right_panel(state)
        self._draw_bottom_bar(state)

        if state.status != GameStatus.PLAYING:
            self._draw_endgame_overlay(state)

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

        # Title
        self._blit(
            "RESOURCES",
            self.font_large,
            C.COLOR_TEXT_PRIMARY,
            x,
            y,
        )
        y += 34

        # Divider
        pygame.draw.line(
            self.screen,
            C.COLOR_PANEL_BORDER,
            (x, y),
            (C.LEFT_PANEL_WIDTH - x, y),
        )
        y += 12

        # Food
        y = self._draw_resource_row(
            surface=self.screen,
            label="Food",
            value=state.food,
            rate=state.food_rate,
            color=C.COLOR_FOOD,
            x=x,
            y=y,
        )

        # Wood
        y = self._draw_resource_row(
            surface=self.screen,
            label="Wood",
            value=state.wood,
            rate=state.wood_rate,
            color=C.COLOR_WOOD,
            x=x,
            y=y,
        )

        # Gold
        y = self._draw_resource_row(
            surface=self.screen,
            label="Gold",
            value=state.gold,
            rate=state.gold_rate,
            color=C.COLOR_GOLD,
            x=x,
            y=y,
        )

        y += 16
        pygame.draw.line(
            self.screen,
            C.COLOR_PANEL_BORDER,
            (x, y),
            (C.LEFT_PANEL_WIDTH - x, y),
        )
        y += 12

        # Win target progress
        self._blit("WIN TARGET", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += 22
        progress = min(state.gold / C.WIN_GOLD_TARGET, 1.0)
        bar_w = C.LEFT_PANEL_WIDTH - x * 2
        bar_h = 14
        bar_bg = pygame.Rect(x, y, bar_w, bar_h)
        bar_fill = pygame.Rect(x, y, int(bar_w * progress), bar_h)
        pygame.draw.rect(self.screen, C.COLOR_BTN_NORMAL, bar_bg, border_radius=3)
        pygame.draw.rect(self.screen, C.COLOR_GOLD, bar_fill, border_radius=3)
        pygame.draw.rect(self.screen, C.COLOR_PANEL_BORDER, bar_bg, width=1, border_radius=3)
        y += bar_h + 4
        self._blit(
            f"{state.gold:.0f} / {C.WIN_GOLD_TARGET} Gold",
            self.font_small,
            C.COLOR_GOLD,
            x,
            y,
        )
        y += 22

        # Colonist details
        y += 10
        pygame.draw.line(
            self.screen,
            C.COLOR_PANEL_BORDER,
            (x, y),
            (C.LEFT_PANEL_WIDTH - x, y),
        )
        y += 12
        self._blit("COLONISTS", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += 22
        self._blit(
            f"Total:  {state.colonist_count}",
            self.font_small,
            C.COLOR_TEXT_PRIMARY,
            x,
            y,
        )
        y += 18
        self._blit(
            f"Idle:   {state.idle_colonists}",
            self.font_small,
            C.COLOR_POSITIVE if state.idle_colonists > 0 else C.COLOR_TEXT_SECONDARY,
            x,
            y,
        )
        y += 18
        self._blit(
            f"Consumption: {state.colonist_count * C.FOOD_PER_COLONIST_PER_TICK:.1f}/tick",
            self.font_small,
            C.COLOR_TEXT_SECONDARY,
            x,
            y,
        )
        y += 18
        arrival_ticks = C.COLONIST_ARRIVAL_INTERVAL_TICKS - state.ticks_since_last_arrival_check
        food_ok = state.food > C.COLONIST_ARRIVAL_MIN_FOOD_SURPLUS
        arrival_color = C.COLOR_POSITIVE if food_ok else C.COLOR_TEXT_DISABLED
        self._blit(
            f"Next arrival: {arrival_ticks} ticks {'(food OK)' if food_ok else '(need food)'}",
            self.font_small,
            arrival_color,
            x,
            y,
        )

    def _draw_resource_row(
        self,
        surface: pygame.Surface,
        label: str,
        value: float,
        rate: float,
        color: tuple,
        x: int,
        y: int,
    ) -> int:
        # Label
        self._blit(f"{label}:", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        # Value
        self._blit(f"{value:>7.1f}", self.font_med, color, x + 80, y)
        # Rate
        rate_str = f"{rate:+.2f}/tick"
        rate_color = (
            C.COLOR_POSITIVE
            if rate > 0
            else C.COLOR_NEGATIVE
            if rate < 0
            else C.COLOR_TEXT_SECONDARY
        )
        self._blit(rate_str, self.font_small, rate_color, x + 180, y + 2)
        return y + 26

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
        y += 34
        pygame.draw.line(
            self.screen,
            C.COLOR_PANEL_BORDER,
            (x, y),
            (C.WINDOW_WIDTH - C.PANEL_PADDING, y),
        )
        y += 12

        # Existing buildings
        for building in state.buildings:
            y = self._draw_building_row(state, building, x, y)
            y += 4

        # Build-new-building section
        y += 12
        pygame.draw.line(
            self.screen,
            C.COLOR_PANEL_BORDER,
            (x, y),
            (C.WINDOW_WIDTH - C.PANEL_PADDING, y),
        )
        y += 10
        self._blit("CONSTRUCT", self.font_med, C.COLOR_TEXT_SECONDARY, x, y)
        y += 24

        for btype in [BuildingType.FARM, BuildingType.LUMBER_MILL, BuildingType.MARKET]:
            y = self._draw_build_button(state, btype, x, y)
            y += 6

    def _draw_building_row(
        self, state: GameState, building, x: int, y: int
    ) -> int:
        """Draw one building row with worker +/- controls. Returns new y."""
        btype = building.building_type
        workers = building.workers_assigned
        max_workers = self._max_workers(btype)
        idle = state.idle_colonists

        # Building name
        label = f"[{building.id}] {btype.value}"
        self._blit(label, self.font_med, C.COLOR_TEXT_PRIMARY, x, y)

        # Worker bar visual
        bar_x = x
        bar_y = y + 22
        pip_size = 10
        pip_gap = 2
        for i in range(max_workers):
            pip_rect = pygame.Rect(bar_x + i * (pip_size + pip_gap), bar_y, pip_size, pip_size)
            pip_color = C.COLOR_POSITIVE if i < workers else C.COLOR_BTN_NORMAL
            pygame.draw.rect(self.screen, pip_color, pip_rect, border_radius=2)
            pygame.draw.rect(self.screen, C.COLOR_BTN_BORDER, pip_rect, width=1, border_radius=2)

        # Worker count label
        self._blit(
            f"{workers}/{max_workers} workers",
            self.font_small,
            C.COLOR_TEXT_SECONDARY,
            x + max_workers * (pip_size + pip_gap) + 6,
            bar_y,
        )

        # Production rate hint
        rate_hint = self._production_hint(btype, workers, state)
        self._blit(rate_hint, self.font_small, C.COLOR_TEXT_SECONDARY, x, bar_y + 14)

        # +/- buttons (right-aligned within panel)
        btn_right_x = C.WINDOW_WIDTH - C.PANEL_PADDING - C.WORKER_BTN_WIDTH
        btn_y = y

        # + button
        can_add = idle > 0 and workers < max_workers
        btn_add = Button(
            rect=pygame.Rect(btn_right_x, btn_y, C.WORKER_BTN_WIDTH, C.WORKER_BTN_HEIGHT),
            label="+",
            action=ActionAssignWorker(building_id=building.id, delta=1),
            enabled=can_add,
            font=self.font_med,
        )
        self._buttons.append(btn_add)
        btn_add.draw(self.screen)

        # - button
        can_remove = workers > 0
        btn_remove = Button(
            rect=pygame.Rect(
                btn_right_x - C.WORKER_BTN_WIDTH - 4, btn_y, C.WORKER_BTN_WIDTH, C.WORKER_BTN_HEIGHT
            ),
            label="-",
            action=ActionAssignWorker(building_id=building.id, delta=-1),
            enabled=can_remove,
            font=self.font_med,
        )
        self._buttons.append(btn_remove)
        btn_remove.draw(self.screen)

        return y + 56

    def _draw_build_button(
        self, state: GameState, btype: BuildingType, x: int, y: int
    ) -> int:
        """Draw a 'build X' button. Returns new y."""
        cost = self._build_cost(btype)
        can_afford = state.wood >= cost

        label = f"Build {btype.value}  (cost: {cost:.0f} Wood)"
        btn_rect = pygame.Rect(
            x, y, C.RIGHT_PANEL_WIDTH - C.PANEL_PADDING * 2, 28
        )
        btn = Button(
            rect=btn_rect,
            label=label,
            action=ActionBuildBuilding(building_type=btype),
            enabled=can_afford,
            font=self.font_small,
        )
        self._buttons.append(btn)
        btn.draw(self.screen)
        return y + 32

    # ------------------------------------------------------------------
    # Bottom bar
    # ------------------------------------------------------------------

    def _draw_bottom_bar(self, state: GameState) -> None:
        bar_rect = pygame.Rect(
            0,
            C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT,
            C.WINDOW_WIDTH,
            C.BOTTOM_BAR_HEIGHT,
        )
        pygame.draw.rect(self.screen, C.COLOR_BOTTOM_BAR, bar_rect)
        pygame.draw.line(
            self.screen,
            C.COLOR_PANEL_BORDER,
            (0, C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT),
            (C.WINDOW_WIDTH, C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT),
        )

        cy = C.WINDOW_HEIGHT - C.BOTTOM_BAR_HEIGHT + C.BOTTOM_BAR_HEIGHT // 2 - 8

        # Tick counter
        self._blit(
            f"Tick: {state.tick:>6}",
            self.font_med,
            C.COLOR_TEXT_SECONDARY,
            C.PANEL_PADDING,
            cy,
        )

        # Speed indicator (each multiplier shown, active one highlighted)
        sx = 180
        self._blit("Speed:", self.font_med, C.COLOR_TEXT_SECONDARY, sx, cy)
        sx += 68
        for mult in C.SPEED_MULTIPLIERS:
            is_active = mult == state.speed_multiplier
            color = C.COLOR_SPEED_HIGHLIGHT if is_active else C.COLOR_TEXT_DISABLED
            self._blit(f"{mult}x", self.font_med, color, sx, cy)
            sx += 46

        # Colonist count
        self._blit(
            f"Colonists: {state.colonist_count}",
            self.font_med,
            C.COLOR_TEXT_PRIMARY,
            sx + 20,
            cy,
        )

        # Starvation events
        self._blit(
            f"Starvations: {state.starvation_events}",
            self.font_med,
            C.COLOR_NEGATIVE if state.starvation_events > 0 else C.COLOR_TEXT_SECONDARY,
            sx + 200,
            cy,
        )

        # Status
        status_text = {
            GameStatus.PLAYING: "PLAYING  [SPACE = speed]",
            GameStatus.WIN: "YOU WIN!",
            GameStatus.LOSE: "GAME OVER",
        }[state.status]
        status_color = {
            GameStatus.PLAYING: C.COLOR_TEXT_SECONDARY,
            GameStatus.WIN: C.COLOR_WIN,
            GameStatus.LOSE: C.COLOR_LOSE,
        }[state.status]
        surf = self.font_med.render(status_text, True, status_color)
        self.screen.blit(surf, (C.WINDOW_WIDTH - surf.get_width() - C.PANEL_PADDING, cy))

    # ------------------------------------------------------------------
    # Endgame overlay
    # ------------------------------------------------------------------

    def _draw_endgame_overlay(self, state: GameState) -> None:
        overlay = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        if state.status == GameStatus.WIN:
            title = "VICTORY!"
            subtitle = f"You accumulated {state.gold:.0f} Gold in {state.tick} ticks!"
            color = C.COLOR_WIN
        else:
            title = "DEFEAT"
            subtitle = f"All colonists perished on tick {state.tick}."
            color = C.COLOR_LOSE

        big_font = pygame.font.SysFont("Consolas", 54, bold=True)
        sub_font = pygame.font.SysFont("Consolas", 22)

        title_surf = big_font.render(title, True, color)
        sub_surf = sub_font.render(subtitle, True, C.COLOR_TEXT_PRIMARY)
        hint_surf = self.font_small.render("Close the window to exit.", True, C.COLOR_TEXT_DISABLED)

        cx = C.WINDOW_WIDTH // 2
        cy = C.WINDOW_HEIGHT // 2

        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 50)))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(cx, cy + 10)))
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(cx, cy + 50)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _blit(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple,
        x: int,
        y: int,
    ) -> None:
        surf = font.render(text, True, color)
        self.screen.blit(surf, (x, y))

    @staticmethod
    def _max_workers(btype: BuildingType) -> int:
        return {
            BuildingType.FARM: C.FARM_MAX_WORKERS,
            BuildingType.LUMBER_MILL: C.LUMBERMILL_MAX_WORKERS,
            BuildingType.MARKET: C.MARKET_MAX_WORKERS,
        }[btype]

    @staticmethod
    def _build_cost(btype: BuildingType) -> float:
        return {
            BuildingType.FARM: C.FARM_BUILD_COST_WOOD,
            BuildingType.LUMBER_MILL: C.LUMBERMILL_BUILD_COST_WOOD,
            BuildingType.MARKET: C.MARKET_BUILD_COST_WOOD,
        }[btype]

    @staticmethod
    def _production_hint(btype: BuildingType, workers: int, state: GameState) -> str:
        if workers == 0:
            return "(no workers)"
        if btype == BuildingType.FARM:
            rate = workers * C.FARM_FOOD_PER_WORKER_PER_TICK
            return f"+{rate:.2f} Food/tick"
        elif btype == BuildingType.LUMBER_MILL:
            rate = workers * C.LUMBERMILL_WOOD_PER_WORKER_PER_TICK
            return f"+{rate:.2f} Wood/tick"
        elif btype == BuildingType.MARKET:
            gold = workers * C.MARKET_GOLD_PER_WORKER_PER_TICK
            wood_cost = workers * C.MARKET_WOOD_PER_WORKER_PER_TICK
            return f"+{gold:.2f} Gold/tick  (-{wood_cost:.2f} Wood/tick)"
        return ""
