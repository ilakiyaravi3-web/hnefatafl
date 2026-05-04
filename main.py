# main.py
# Temporary test file — runs the board with a fake game state
# Fake board will be replaced later with real engine call ,fake_legal_moves replaced by real engine calls

import pygame
from ui.board import BoardScreen
from ui.pieces import ATTACKER_P, DEFENDER_P, KING_P, EMPTY

pygame.init()

CELL        = 60
BOARD_PX    = CELL * 11        # 660px board
PANEL_W     = 260              # right side panel
PADDING     = 20               # gap around board
WINDOW_W    = BOARD_PX + PANEL_W + PADDING * 3
WINDOW_H    = BOARD_PX + PADDING * 2

WIN = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
pygame.display.set_caption("Hnefatafl AI – Group 6")
clock = pygame.time.Clock()

# FAKE GAME STATE — replaced with real engine later
def make_starting_board():
    """
    Standard Hnefatafl 11x11 starting positions.
    0 = empty, 1 = attacker, 2 = defender, 3 = king
    """
    b = [[EMPTY] * 11 for _ in range(11)]

    # Attackers — edges
    attacker_positions = [
        (0,3),(0,4),(0,5),(0,6),(0,7),
        (1,5),
        (3,0),(4,0),(5,0),(6,0),(7,0),
        (5,1),
        (3,10),(4,10),(5,10),(6,10),(7,10),
        (5,9),
        (10,3),(10,4),(10,5),(10,6),(10,7),
        (9,5),
    ]
    for (r, c) in attacker_positions:
        b[r][c] = ATTACKER_P

    # Defenders — around center
    defender_positions = [
        (3,5),(4,4),(4,5),(4,6),
        (5,3),(5,4),(5,6),(5,7),
        (6,4),(6,5),(6,6),(7,5),
    ]
    for (r, c) in defender_positions:
        b[r][c] = DEFENDER_P

    # King — center
    b[5][5] = KING_P

    return b


def fake_legal_moves(board, pos):
    """
    Placeholder until engine is ready.
    Returns all squares in the same row/col that are empty (basic rook movement).
    Does NOT check for blocked paths — engine will handle that properly.
    """
    row, col = pos
    moves = []

    # Up
    for r in range(row - 1, -1, -1):
        if board[r][col] == EMPTY:
            moves.append((r, col))
        else:
            break
    # Down
    for r in range(row + 1, 11):
        if board[r][col] == EMPTY:
            moves.append((r, col))
        else:
            break
    # Left
    for c in range(col - 1, -1, -1):
        if board[row][c] == EMPTY:
            moves.append((row, c))
        else:
            break
    # Right
    for c in range(col + 1, 11):
        if board[row][c] == EMPTY:
            moves.append((row, c))
        else:
            break

    return moves


# GAME STATE
board = make_starting_board()
current_turn = ATTACKER_P  # attackers go first

def on_move(from_pos, to_pos):
    """Called by BoardScreen when a valid move is made."""
    global board, current_turn

    fr, fc = from_pos
    tr, tc = to_pos

    # Move the piece
    board[tr][tc] = board[fr][fc]
    board[fr][fc] = EMPTY

    # Switch turn
    current_turn = DEFENDER_P if current_turn == ATTACKER_P else ATTACKER_P

    print(f"Move: {from_pos} → {to_pos} | Now: {'Defender' if current_turn == DEFENDER_P else 'Attacker'}")

# INIT BOARD SCREEN
board_screen = BoardScreen(on_move_callback=on_move)

# FONTS
font_title  = pygame.font.SysFont("Georgia", 22, bold=True)
font_label  = pygame.font.SysFont("Arial", 17, bold=True)
font_small  = pygame.font.SysFont("Arial", 13)

# PANEL DRAWING
def draw_panel(board_x, board_y):
    panel_x = board_x + BOARD_PX + PADDING
    panel_y = board_y
    panel_h = BOARD_PX

    # Panel background
    panel_rect = pygame.Rect(panel_x, panel_y, PANEL_W, panel_h)
    pygame.draw.rect(WIN, (45, 45, 45), panel_rect, border_radius=12)
    pygame.draw.rect(WIN, (80, 80, 80), panel_rect, 1, border_radius=12)

    # Title
    title = font_title.render("Hnefatafl", True, (212, 175, 55))
    WIN.blit(title, (panel_x + (PANEL_W - title.get_width()) // 2, panel_y + 20))
    subtitle = font_small.render("Viking Strategy Game", True, (150, 150, 150))
    WIN.blit(subtitle, (panel_x + (PANEL_W - subtitle.get_width()) // 2, panel_y + 50))

    pygame.draw.line(WIN, (80, 80, 80),
                     (panel_x + 15, panel_y + 75),
                     (panel_x + PANEL_W - 15, panel_y + 75), 1)

    # Turn indicator
    turn_label = "Attacker's Turn" if current_turn == ATTACKER_P else "Defender's Turn"
    turn_color = (220, 80, 80) if current_turn == ATTACKER_P else (80, 140, 220)
    turn_bg    = (60, 20, 20) if current_turn == ATTACKER_P else (20, 30, 60)

    turn_rect = pygame.Rect(panel_x + 15, panel_y + 90, PANEL_W - 30, 44)
    pygame.draw.rect(WIN, turn_bg, turn_rect, border_radius=8)
    pygame.draw.rect(WIN, turn_color, turn_rect, 2, border_radius=8)
    turn_text = font_label.render(turn_label, True, turn_color)
    WIN.blit(turn_text, (turn_rect.x + (turn_rect.w - turn_text.get_width()) // 2,
                         turn_rect.y + 12))

    pygame.draw.line(WIN, (80, 80, 80),
                     (panel_x + 15, panel_y + 150),
                     (panel_x + PANEL_W - 15, panel_y + 150), 1)

    # Pieces legend
    legend_y = panel_y + 165
    WIN.blit(font_label.render("Pieces", True, (200, 200, 200)), (panel_x + 20, legend_y))
    legend_y += 30
    for color, text in [
        ((180, 40, 40),  "Attacker  (24 pieces)"),
        ((60, 100, 180), "Defender  (12 pieces)"),
        ((212, 175, 55), "King       (1 piece)"),
    ]:
        pygame.draw.circle(WIN, color, (panel_x + 30, legend_y + 9), 9)
        WIN.blit(font_small.render(text, True, (200, 200, 200)), (panel_x + 48, legend_y))
        legend_y += 28

    pygame.draw.line(WIN, (80, 80, 80),
                     (panel_x + 15, legend_y + 8),
                     (panel_x + PANEL_W - 15, legend_y + 8), 1)

    # Controls
    ctrl_y = legend_y + 22
    WIN.blit(font_label.render("Controls", True, (200, 200, 200)), (panel_x + 20, ctrl_y))
    ctrl_y += 28
    for line in [
        "Click piece  →  select",
        "Click green  →  move",
        "ESC          →  deselect",
        "R            →  reset game",
    ]:
        WIN.blit(font_small.render(line, True, (150, 150, 150)), (panel_x + 20, ctrl_y))
        ctrl_y += 22

    # Group tag
    group = font_small.render("Group 6  ·  MGAIAL 2026", True, (80, 80, 80))
    WIN.blit(group, (panel_x + (PANEL_W - group.get_width()) // 2,
                     panel_y + panel_h - 30))


# GAME LOOP
running = True
while running:
    # Get current window size every frame — handles resizing
    win_w, win_h = WIN.get_size()

    # Total content width = board + gap + panel
    total_w = BOARD_PX + PADDING + PANEL_W
    total_h = BOARD_PX

    # Center the whole thing in the window
    board_x = (win_w - total_w) // 2
    board_y = (win_h - total_h) // 2

    # Keep board_x from going negative on small windows
    board_x = max(PADDING, board_x)
    board_y = max(PADDING, board_y)

    BOARD_OFFSET = (board_x, board_y)

    WIN.fill((20, 20, 20))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            board_screen.handle_click(
                mouse_pos=event.pos,
                board=board,
                current_turn=current_turn,
                get_legal_moves_fn=fake_legal_moves,
                offset=BOARD_OFFSET
            )

        elif event.type == pygame.KEYDOWN:
            board_screen.handle_keydown(event.key)
            if event.key == pygame.K_r:
                board = make_starting_board()
                current_turn = ATTACKER_P
                print("Game reset.")

    board_screen.render(WIN, board, offset=BOARD_OFFSET)
    draw_panel(board_x, board_y)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()