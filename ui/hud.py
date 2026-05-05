
import pygame
from ui.colors import (BACKGROUND, TEXT_PRIMARY, TEXT_SECONDARY, ATTACKER, DEFENDER, KING, CELL_LIGHT, CELL_DARK, LEGAL_MOVE, LAST_MOVE
)
PANEL_X = 660   # HUD panel starts after the 11×11 board (11 * 60)
PANEL_W = 140   # remaining window width
WINDOW_H = 660   # full window height
PANEL_COLOR = (25, 25, 35)
DIVIDER = (60, 60, 80)
BTN_W = 110
BTN_H = 34
BTN_X = PANEL_X + (PANEL_W - BTN_W) // 2   # horizontally centred in panel
SPEED_OPTIONS = {
    "Slow": 1200,
    "Normal": 600,
    "Fast": 150,
}
DEFAULT_SPEED = "Normal"

def _make_font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont("segoeui", size)
class Button:
    def __init__(self, rect: pygame.Rect, label: str, color=(60, 60, 90), active_color=(100, 100, 160)):
        self.rect = rect
        self.label = label
        self.color = color
        self.active_color = active_color
        self.hovered = False
        self.active = False          # toggled state (e.g. speed button)
        self._font = _make_font(14)

    def draw(self, surface: pygame.Surface):
        if self.active:
            bg = self.active_color
        elif self.hovered:
            bg = tuple(min(c + 30, 255) for c in self.color)
        else:
            bg = self.color
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, DIVIDER, self.rect, 1, border_radius=6)
        text_surf = self._font.render(self.label, True, TEXT_PRIMARY)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

class HUDPanel:
    def __init__(self, on_resign, on_save_replay):
        self.on_resign = on_resign
        self.on_save_replay = on_save_replay
        self._font_large = _make_font(20)
        self._font_medium = _make_font(15)
        self._font_small = _make_font(13)

        self._btn_resign = Button(
            pygame.Rect(BTN_X, 560, BTN_W, BTN_H),
            "Resign",
            color=(120, 40, 40),
            active_color = (180, 60, 60),
        )
        self._btn_save = Button(pygame.Rect(BTN_X, 610, BTN_W, BTN_H), "Save Replay", color=(40, 80, 120), active_color=(60, 120, 180))

    def draw(self, window: pygame.Surface, game_state):
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_W, WINDOW_H)
        pygame.draw.rect(window, PANEL_COLOR, panel_rect)
        pygame.draw.line(window, DIVIDER, (PANEL_X, 0), (PANEL_X, WINDOW_H), 2)
        self.draw_indicator(window, game_state)
        self.draw_captures(window, game_state)
        if getattr(game_state, "ai_mode", False):
            self._draw_agent_names(window, game_state)
        else:
            self._btn_resign.draw(window)
        self._btn_save.draw(window)

    def draw_indicator(self, window: pygame.Surface, game_state):
        turn = getattr(game_state, "turn", "Attacker")
        color = ATTACKER if turn == "Attacker" else DEFENDER
        bar = pygame.Rect(PANEL_X + 8, 10, PANEL_W - 16, 48)
        pygame.draw.rect(window, color, bar, border_radius=8)
        pygame.draw.rect(window, DIVIDER, bar, 1, border_radius=8)
        label = self._font_large.render(turn, True, TEXT_PRIMARY)
        label_rect = label.get_rect(center=(PANEL_X + PANEL_W // 2, 26))
        window.blit(label, label_rect)
        sub = self._font_small.render("to move", True, TEXT_SECONDARY)
        sub_rect = sub.get_rect(center=(PANEL_X + PANEL_W // 2, 46))
        window.blit(sub, sub_rect)

    def draw_captures(self, window: pygame.Surface, game_state):
        captures = getattr(game_state, "captures", {"attacker": 0, "defender": 0})
        pygame.draw.line(window, DIVIDER, (PANEL_X + 8, 76), (PANEL_X + PANEL_W - 8, 76), 1)
        title = self._font_medium.render("Captured", True, TEXT_SECONDARY)
        window.blit(title, (PANEL_X + 10, 84))
        pygame.draw.circle(window, ATTACKER, (PANEL_X + 22, 118), 10)
        atk_text = self._font_medium.render(f"Attackers: {captures.get('attacker', 0)}", True, TEXT_PRIMARY)
        window.blit(atk_text, (PANEL_X + 36, 110))
        pygame.draw.circle(window, DEFENDER, (PANEL_X + 22, 148), 10)
        def_text = self._font_medium.render(f"Defenders: {captures.get('defender', 0)}", True, TEXT_PRIMARY)
        window.blit(def_text, (PANEL_X + 36, 140))
        pygame.draw.line(window, DIVIDER, (PANEL_X + 8, 172), (PANEL_X + PANEL_W - 8, 172), 1)

    def _draw_agent_names(self, window: pygame.Surface, game_state):
        agent_names = getattr(game_state, "agent_names", {})
        title = self._font_small.render("Agents", True, TEXT_SECONDARY)
        window.blit(title, (PANEL_X + 10, 180))
        atk = agent_names.get("attacker", "?")
        def_ = agent_names.get("defender", "?")
        atk_surf = self._font_medium.render(f"ATK: {atk}", True, ATTACKER)
        def_surf = self._font_medium.render(f"DEF: {def_}", True, DEFENDER)
        window.blit(atk_surf, (PANEL_X + 10, 200))
        window.blit(def_surf, (PANEL_X + 10, 224))

    def handle_event(self, event: pygame.event.Event, game_state):
        ai_mode = getattr(game_state, "ai_mode", False)
        if not ai_mode and self._btn_resign.handle_event(event):
            self.on_resign()
        if self._btn_save.handle_event(event):
            self.on_save_replay()
        if event.type == pygame.MOUSEMOTION:
            self._btn_resign.hovered = self._btn_resign.rect.collidepoint(event.pos)
            self._btn_save.hovered   = self._btn_save.rect.collidepoint(event.pos)

class AIViewer:
    STRIP_H = 40   # height of the control strip drawn below the board area
    STRIP_Y = 620  # y-position (window is 660 tall; board is 660, strip is overlay)

    def __init__(self):
        self._paused = False
        self._speed_label = DEFAULT_SPEED
        self._interval_ms = SPEED_OPTIONS[DEFAULT_SPEED]
        self._last_move_ms = 0              # pygame.time.get_ticks() snapshot
        self._font = _make_font(14)
        self._btn_pause = Button(pygame.Rect(PANEL_X + 10, 200, BTN_W, BTN_H), "⏸  Pause", color=(50, 100, 80), active_color=(80, 160, 120))
        # Speed buttons — one per option, share the same row in the HUD
        self._speed_buttons: dict[str, Button] = {}
        for i, label in enumerate(SPEED_OPTIONS):
            btn = Button(pygame.Rect(PANEL_X + 10, 250 + i * 42, BTN_W, BTN_H), label, color=(50, 60, 100), active_color=(80, 100, 160))
            btn.active = label == DEFAULT_SPEED
            self._speed_buttons[label] = btn

    def should_move(self) -> bool:
        if self._paused:
            return False
        now = pygame.time.get_ticks()
        if now - self._last_move_ms >= self._interval_ms:
            self._last_move_ms = now
            return True
        return False

    def reset_timer(self):
        self._last_move_ms = pygame.time.get_ticks()

    @property
    def paused(self) -> bool:
        return self._paused

    def draw(self, window: pygame.Surface, game_state):
        self._btn_pause.label = "▶  Resume" if self._paused else "⏸  Pause"
        self._btn_pause.draw(window)
        spd_label = self._font.render("Speed", True, TEXT_SECONDARY)
        window.blit(spd_label, (PANEL_X + 10, 236))
        for btn in self._speed_buttons.values():
            btn.draw(window)

    def handle_event(self, event: pygame.event.Event):
        if self._btn_pause.handle_event(event):
            self._paused = not self._paused
        for label, btn in self._speed_buttons.items():
            if btn.handle_event(event):
                self._speed_label = label
                self._interval_ms = SPEED_OPTIONS[label]
                for b in self._speed_buttons.values():
                    b.active = False
                self._speed_buttons[label].active = True
        if event.type == pygame.MOUSEMOTION:
            self._btn_pause.hovered = self._btn_pause.rect.collidepoint(event.pos)
            for btn in self._speed_buttons.values():
                btn.hovered = btn.rect.collidepoint(event.pos)