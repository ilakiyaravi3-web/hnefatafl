# ui/pieces.py
# Responsible: Person B (Ilakkiya)
# Draws individual pieces on the board surface

import pygame
from ui.colors import (
    ATTACKER, ATTACKER_OUT,
    DEFENDER, DEFENDER_OUT,
    KING, KING_OUT,
    SELECTED_RING
)

# Piece type constants — must match what the engine uses
EMPTY    = 0
ATTACKER_P = 1
DEFENDER_P = 2
KING_P   = 3

CELL = 60  # cell size in pixels — must match board.py


def get_center(row, col):
    """Convert board grid position to pixel center of that cell."""
    x = col * CELL + CELL // 2
    y = row * CELL + CELL // 2
    return (x, y)


def draw_attacker(surface, row, col, selected=False):
    center = get_center(row, col)
    radius = CELL // 2 - 6

    # Outer ring if selected
    if selected:
        pygame.draw.circle(surface, SELECTED_RING, center, radius + 5, 3)

    pygame.draw.circle(surface, ATTACKER, center, radius)
    pygame.draw.circle(surface, ATTACKER_OUT, center, radius, 2)


def draw_defender(surface, row, col, selected=False):
    center = get_center(row, col)
    radius = CELL // 2 - 6

    if selected:
        pygame.draw.circle(surface, SELECTED_RING, center, radius + 5, 3)

    pygame.draw.circle(surface, DEFENDER, center, radius)
    pygame.draw.circle(surface, DEFENDER_OUT, center, radius, 2)


def draw_king(surface, row, col, selected=False):
    center = get_center(row, col)
    radius = CELL // 2 - 4
    cx, cy = center

    if selected:
        pygame.draw.circle(surface, SELECTED_RING, center, radius + 5, 3)

    # Gold circle base
    pygame.draw.circle(surface, KING, center, radius)
    pygame.draw.circle(surface, KING_OUT, center, radius, 3)

    # --- Crown shape drawn on top of the circle ---
    # Crown sits in the upper half of the circle
    crown_w  = radius - 4          # total width of crown
    crown_bottom_y = cy + 6        # bottom edge of crown
    crown_top_y    = cy - radius + 8  # top edge of crown (tips)
    crown_mid_y    = cy - 2        # middle height of crown base

    # Crown base — a filled rectangle across the bottom
    base_rect = pygame.Rect(
        cx - crown_w, crown_mid_y,
        crown_w * 2, crown_bottom_y - crown_mid_y
    )
    pygame.draw.rect(surface, (255, 215, 0), base_rect)
    pygame.draw.rect(surface, (180, 140, 0), base_rect, 1)

    # Crown points — 3 triangular spikes pointing up
    # Left spike
    left_spike = [
        (cx - crown_w, crown_mid_y),
        (cx - crown_w + 6, crown_mid_y),
        (cx - crown_w + 3, crown_top_y + 4),
    ]
    # Middle spike (tallest)
    mid_spike = [
        (cx - 5, crown_mid_y),
        (cx + 5, crown_mid_y),
        (cx, crown_top_y),
    ]
    # Right spike
    right_spike = [
        (cx + crown_w - 6, crown_mid_y),
        (cx + crown_w, crown_mid_y),
        (cx + crown_w - 3, crown_top_y + 4),
    ]

    for spike in [left_spike, mid_spike, right_spike]:
        pygame.draw.polygon(surface, (255, 215, 0), spike)
        pygame.draw.polygon(surface, (180, 140, 0), spike, 1)

    # Three small jewel dots on the crown base
    jewel_y = crown_mid_y + (crown_bottom_y - crown_mid_y) // 2
    for jx in [cx - crown_w // 2, cx, cx + crown_w // 2]:
        pygame.draw.circle(surface, (255, 50, 50), (jx, jewel_y), 3)  # red jewels


def draw_piece(surface, piece_type, row, col, selected=False):
    """Main entry point — draw the correct piece type at (row, col)."""
    if piece_type == ATTACKER_P:
        draw_attacker(surface, row, col, selected)
    elif piece_type == DEFENDER_P:
        draw_defender(surface, row, col, selected)
    elif piece_type == KING_P:
        draw_king(surface, row, col, selected)


def draw_all_pieces(surface, board, selected_pos=None):
    """
    Draw all pieces on the board.
    board: 11x11 2D list or numpy array of piece type constants
    selected_pos: (row, col) of currently selected piece, or None
    """
    for row in range(11):
        for col in range(11):
            piece = board[row][col]
            if piece != EMPTY:
                is_selected = (selected_pos == (row, col))
                draw_piece(surface, piece, row, col, selected=is_selected)