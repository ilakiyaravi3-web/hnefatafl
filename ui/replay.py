# ui/replay.py
# Responsible: Person C
# Handles: loading saved match JSON, step-through replay controls,
#           move counter, last-move highlight passthrough to board

import json
import pygame
from ui.colors import (
    BACKGROUND, PANEL_COLOR, TEXT_PRIMARY, TEXT_SECONDARY,
    DIVIDER, LAST_MOVE, ATTACKER, DEFENDER
)

# Re-use the button widget from hud.py to keep the look consistent
from ui.hud import Button, _make_font

# ── Layout constants (shared with hud.py) ───────────────────────────────────
PANEL_X = 660
PANEL_W = 140
WINDOW_H = 660

BTN_W = 110
BTN_H = 34
BTN_X = PANEL_X + (PANEL_W - BTN_W) // 2


# ── Data class ───────────────────────────────────────────────────────────────

class ReplayData:
    """
    Holds one loaded match.

    JSON format expected:
    {
        "agent_attacker": "MCTS",
        "agent_defender": "Heuristic",
        "winner": "Defender",
        "moves": [
            {"from": [row, col], "to": [row, col], "board": [[...11 rows...]]},
            ...
        ]
    }

    Each "board" entry is the full 11×11 board state *after* that move.
    The initial board (move 0) is reconstructed from the game engine's
    starting position via the `initial_board` argument passed to ReplayViewer.
    """

    def __init__(self, path: str):
        with open(path, "r") as fh:
            raw = json.load(fh)

        self.agent_attacker: str = raw.get("agent_attacker", "Unknown")
        self.agent_defender: str = raw.get("agent_defender", "Unknown")
        self.winner: str         = raw.get("winner", "Unknown")
        self.moves: list[dict]   = raw.get("moves", [])

    @property
    def total_moves(self) -> int:
        return len(self.moves)

    def get_board_at(self, step: int, initial_board) -> list:
        """
        Return the board state at the given step index.
        step 0  → initial_board (before any move)
        step N  → board after move N
        """
        if step == 0:
            return initial_board
        return self.moves[step - 1]["board"]

    def get_last_move_at(self, step: int):
        """Return (from_pos, to_pos) for the move that produced step, or None."""
        if step == 0 or not self.moves:
            return None
        move = self.moves[step - 1]
        return (tuple(move["from"]), tuple(move["to"]))


# ── Replay viewer ─────────────────────────────────────────────────────────────

class ReplayViewer:
    """
    Manages replay state and draws replay controls in the HUD panel.

    Usage in main.py
    ─────────────────
        viewer = ReplayViewer(initial_board, on_load_file=open_file_dialog)

        # Load a file:
        viewer.load("path/to/match.json")

        # In the event loop:
        viewer.handle_event(event)

        # In the draw loop:
        board_to_draw   = viewer.current_board
        last_move_hint  = viewer.current_last_move   # pass to BoardScreen
        viewer.draw(window)

    The viewer does NOT touch BoardScreen directly; instead main.py reads
    `viewer.current_board` and `viewer.current_last_move` and passes them
    to BoardScreen.render() each frame.
    """

    def __init__(self, initial_board, on_load_file=None):
        """
        initial_board  : the engine's starting 11×11 board (list or ndarray)
        on_load_file   : optional callback() → str  that opens a file dialog
                         and returns the chosen path (or None if cancelled).
                         If omitted, the Load button will not appear.
        """
        self._initial_board = initial_board
        self._on_load_file  = on_load_file

        self._replay: ReplayData | None = None
        self._step  : int = 0             # 0 = initial position

        self._font_large  = _make_font(18)
        self._font_medium = _make_font(15)
        self._font_small  = _make_font(13)

        # Build buttons
        self._btn_prev = Button(
            pygame.Rect(BTN_X, 190, (BTN_W - 6) // 2, BTN_H),
            "◀ Prev",
            color=(50, 60, 100),
        )
        self._btn_next = Button(
            pygame.Rect(BTN_X + (BTN_W + 6) // 2, 190, (BTN_W - 6) // 2, BTN_H),
            "Next ▶",
            color=(50, 60, 100),
        )
        self._btn_first = Button(
            pygame.Rect(BTN_X, 232, (BTN_W - 6) // 2, BTN_H),
            "|◀ First",
            color=(40, 50, 80),
        )
        self._btn_last = Button(
            pygame.Rect(BTN_X + (BTN_W + 6) // 2, 232, (BTN_W - 6) // 2, BTN_H),
            "Last ▶|",
            color=(40, 50, 80),
        )
        self._btn_load = Button(
            pygame.Rect(BTN_X, 140, BTN_W, BTN_H),
            "Load File",
            color=(40, 80, 60),
            active_color=(60, 120, 90),
        ) if on_load_file else None

    # ── Public API ───────────────────────────────────────────────────────────

    def load(self, path: str):
        """Load a saved match JSON file and reset to step 0."""
        self._replay = ReplayData(path)
        self._step   = 0

    @property
    def is_loaded(self) -> bool:
        return self._replay is not None

    @property
    def current_board(self):
        """Board state at the current replay step — pass this to BoardScreen."""
        if self._replay is None:
            return self._initial_board
        return self._replay.get_board_at(self._step, self._initial_board)

    @property
    def current_last_move(self):
        """(from_pos, to_pos) or None — pass as last_move to BoardScreen."""
        if self._replay is None:
            return None
        return self._replay.get_last_move_at(self._step)

    @property
    def total_moves(self) -> int:
        return self._replay.total_moves if self._replay else 0

    @property
    def current_step(self) -> int:
        return self._step

    # ── Navigation ───────────────────────────────────────────────────────────

    def step_forward(self):
        if self._replay and self._step < self._replay.total_moves:
            self._step += 1

    def step_backward(self):
        if self._step > 0:
            self._step -= 1

    def go_first(self):
        self._step = 0

    def go_last(self):
        if self._replay:
            self._step = self._replay.total_moves

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self, window: pygame.Surface):
        """
        Draw replay controls inside the right HUD panel.
        Call every frame from main.py.
        """
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_W, WINDOW_H)
        pygame.draw.rect(window, PANEL_COLOR, panel_rect)
        pygame.draw.line(window, DIVIDER, (PANEL_X, 0), (PANEL_X, WINDOW_H), 2)

        self._draw_title(window)
        self._draw_match_info(window)
        self._draw_move_counter(window)

        if self._btn_load:
            self._btn_load.draw(window)

        self._btn_prev.draw(window)
        self._btn_next.draw(window)
        self._btn_first.draw(window)
        self._btn_last.draw(window)

        self._draw_keyboard_hint(window)

    def _draw_title(self, window: pygame.Surface):
        title = self._font_large.render("Replay", True, TEXT_PRIMARY)
        title_rect = title.get_rect(center=(PANEL_X + PANEL_W // 2, 20))
        window.blit(title, title_rect)
        pygame.draw.line(window, DIVIDER, (PANEL_X + 8, 38), (PANEL_X + PANEL_W - 8, 38), 1)

    def _draw_match_info(self, window: pygame.Surface):
        """Show agent names and winner when a file is loaded."""
        if self._replay is None:
            msg = self._font_small.render("No file loaded", True, TEXT_SECONDARY)
            window.blit(msg, (PANEL_X + 10, 50))
            return

        atk = self._font_small.render(
            f"ATK: {self._replay.agent_attacker}", True, ATTACKER
        )
        def_ = self._font_small.render(
            f"DEF: {self._replay.agent_defender}", True, DEFENDER
        )
        winner_color = (
            ATTACKER if self._replay.winner == "Attacker"
            else DEFENDER if self._replay.winner == "Defender"
            else TEXT_SECONDARY
        )
        win_surf = self._font_small.render(
            f"Winner: {self._replay.winner}", True, winner_color
        )

        window.blit(atk,      (PANEL_X + 10, 48))
        window.blit(def_,     (PANEL_X + 10, 68))
        window.blit(win_surf, (PANEL_X + 10, 88))

        pygame.draw.line(window, DIVIDER, (PANEL_X + 8, 112), (PANEL_X + PANEL_W - 8, 112), 1)

    def _draw_move_counter(self, window: pygame.Surface):
        """Prominent step / total display."""
        total = self.total_moves
        counter_text = f"{self._step} / {total}"
        counter = self._font_large.render(counter_text, True, TEXT_PRIMARY)
        counter_rect = counter.get_rect(center=(PANEL_X + PANEL_W // 2, 128))
        window.blit(counter, counter_rect)

    def _draw_keyboard_hint(self, window: pygame.Surface):
        hint = self._font_small.render("← → keys also work", True, TEXT_SECONDARY)
        hint_rect = hint.get_rect(center=(PANEL_X + PANEL_W // 2, 290))
        window.blit(hint, hint_rect)

    # ── Events ───────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event):
        """
        Call from main.py inside the event loop.
        Handles button clicks and left/right arrow keys.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.step_backward()
            elif event.key == pygame.K_RIGHT:
                self.step_forward()
            elif event.key == pygame.K_HOME:
                self.go_first()
            elif event.key == pygame.K_END:
                self.go_last()

        if self._btn_load and self._btn_load.handle_event(event):
            path = self._on_load_file()
            if path:
                self.load(path)

        if self._btn_prev.handle_event(event):
            self.step_backward()

        if self._btn_next.handle_event(event):
            self.step_forward()

        if self._btn_first.handle_event(event):
            self.go_first()

        if self._btn_last.handle_event(event):
            self.go_last()

        # Hover state sync
        if event.type == pygame.MOUSEMOTION:
            for btn in filter(None, [
                self._btn_load, self._btn_prev, self._btn_next,
                self._btn_first, self._btn_last,
            ]):
                btn.hovered = btn.rect.collidepoint(event.pos)