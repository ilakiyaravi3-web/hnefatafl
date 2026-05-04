# ui/board.py
# Responsible: Person B (Ilakkiya)
# Handles: grid rendering, click handling, move highlights, last-move highlight

import pygame
from ui.colors import (
    CELL_LIGHT, CELL_DARK, THRONE, CORNER,
    LEGAL_MOVE, LAST_MOVE, GRID_LINE
)
from ui.pieces import draw_all_pieces

CELL = 60        # pixel size of each square
BOARD_SIZE = 11  # 11x11 grid

# Special squares
THRONE_POS  = (5, 5)
CORNER_POS  = [(0, 0), (0, 10), (10, 0), (10, 10)]

# Restricted squares — only king may land here
RESTRICTED  = set(CORNER_POS + [THRONE_POS])


class BoardScreen:
    def __init__(self, on_move_callback):
        """
        on_move_callback: function(from_pos, to_pos) — called when player makes a move
                          wired in main.py, not here
        """
        self.on_move = on_move_callback

        self.selected_pos   = None   # (row, col) of selected piece, or None
        self.legal_moves    = []     # list of (row, col) valid destinations
        self.last_move      = None   # (from_pos, to_pos) of last move made

        # Board surface — drawn once per frame
        self.surface = pygame.Surface((CELL * BOARD_SIZE, CELL * BOARD_SIZE))

    # ------------------------------------------------------------------
    # DRAWING
    # ------------------------------------------------------------------

    def draw_grid(self, board):
        """Draw the board grid, special squares, highlights, and pieces."""
        self._draw_cells()
        self._draw_last_move_highlight()
        self._draw_legal_move_highlights()
        draw_all_pieces(self.surface, board, selected_pos=self.selected_pos)

    def _draw_cells(self):
        """Draw the base grid with alternating colors and special squares."""
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                rect = pygame.Rect(col * CELL, row * CELL, CELL, CELL)

                # Pick base color
                if (row, col) == THRONE_POS:
                    color = THRONE
                elif (row, col) in CORNER_POS:
                    color = CORNER
                elif (row + col) % 2 == 0:
                    color = CELL_LIGHT
                else:
                    color = CELL_DARK

                pygame.draw.rect(self.surface, color, rect)
                pygame.draw.rect(self.surface, GRID_LINE, rect, 1)  # grid line

    def _draw_legal_move_highlights(self):
        """Draw semi-transparent green overlay on all valid destination squares."""
        highlight = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        highlight.fill((*LEGAL_MOVE, 140))  # 140 = alpha transparency

        for (row, col) in self.legal_moves:
            self.surface.blit(highlight, (col * CELL, row * CELL))

    def _draw_last_move_highlight(self):
        """Draw a subtle tint on the from and to squares of the last move."""
        if self.last_move is None:
            return

        tint = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
        tint.fill((*LAST_MOVE, 80))

        from_pos, to_pos = self.last_move
        for (row, col) in [from_pos, to_pos]:
            self.surface.blit(tint, (col * CELL, row * CELL))

    def render(self, window, board, offset=(0, 0)):
        """
        Full render call — call this every frame from main.py.
        window: the main pygame display surface
        board: current 11x11 game state array
        offset: (x, y) pixel offset if board is not at top-left of window
        """
        self.draw_grid(board)
        window.blit(self.surface, offset)

    # ------------------------------------------------------------------
    # INPUT HANDLING
    # ------------------------------------------------------------------

    def handle_click(self, mouse_pos, board, current_turn, get_legal_moves_fn, offset=(0, 0)):
        """
        Call this from main.py when pygame.MOUSEBUTTONDOWN fires.

        mouse_pos: (x, y) raw pixel from pygame event
        board: current 11x11 game state
        current_turn: ATTACKER_P or DEFENDER_P constant
        get_legal_moves_fn: engine function — get_legal_moves(board, pos) → list of (row,col)
        offset: board's top-left pixel position in the window
        """
        grid_pos = self._pixel_to_grid(mouse_pos, offset)

        # Click was outside the board
        if grid_pos is None:
            self._deselect()
            return

        row, col = grid_pos
        clicked_piece = board[row][col]

        # --- Case 1: a piece is already selected ---
        if self.selected_pos is not None:

            # Clicked a valid destination → make the move
            if grid_pos in self.legal_moves:
                self.last_move = (self.selected_pos, grid_pos)
                self.on_move(self.selected_pos, grid_pos)
                self._deselect()

            # Clicked own piece again → switch selection
            elif self._is_own_piece(clicked_piece, current_turn):
                self._select(grid_pos, board, get_legal_moves_fn)

            # Clicked elsewhere → deselect
            else:
                self._deselect()

        # --- Case 2: nothing selected yet ---
        else:
            if self._is_own_piece(clicked_piece, current_turn):
                self._select(grid_pos, board, get_legal_moves_fn)

    def handle_keydown(self, key):
        """Handle keyboard shortcuts."""
        if key == pygame.K_ESCAPE:
            self._deselect()

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _select(self, pos, board, get_legal_moves_fn):
        """Select a piece and fetch its legal moves from the engine."""
        self.selected_pos = pos
        self.legal_moves  = get_legal_moves_fn(board, pos)

    def _deselect(self):
        """Clear selection and highlights."""
        self.selected_pos = None
        self.legal_moves  = []

    def _pixel_to_grid(self, mouse_pos, offset):
        """
        Convert raw pixel (x, y) to board (row, col).
        Returns None if click is outside the board.
        """
        x = mouse_pos[0] - offset[0]
        y = mouse_pos[1] - offset[1]

        col = x // CELL
        row = y // CELL

        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            return (row, col)
        return None

    def _is_own_piece(self, piece_type, current_turn):
        """
        Check if a piece belongs to the current player.
        Defenders control both DEFENDER and KING pieces.
        """
        from ui.pieces import ATTACKER_P, DEFENDER_P, KING_P, EMPTY

        if piece_type == EMPTY:
            return False
        if current_turn == ATTACKER_P:
            return piece_type == ATTACKER_P
        if current_turn == DEFENDER_P:
            return piece_type in (DEFENDER_P, KING_P)
        return False
