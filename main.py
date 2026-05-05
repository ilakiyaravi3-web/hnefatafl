import pygame
from ui.board import BoardScreen
from ui.hud import HUDPanel, AIViewer
from ui.pieces import ATTACKER_P, DEFENDER_P, KING_P, EMPTY

pygame.init()
window = pygame.display.set_mode((800, 660))
pygame.display.set_caption("Hnefatafl")

# Minimal fake game state
class GameState:
    turn = "Attacker"
    captures = {"attacker": 0, "defender": 0}
    ai_mode = False
    agent_names = {"attacker": "MCTS", "defender": "Heuristic"}

# Flat starting board (simplified — replace with real engine setup)
board = [[EMPTY] * 11 for _ in range(11)]
board[5][5] = KING_P          # king on throne
board[0][0] = ATTACKER_P      # sample attacker

game_state = GameState()

def on_move(from_pos, to_pos):
    r1, c1 = from_pos
    r2, c2 = to_pos
    board[r2][c2] = board[r1][c1]
    board[r1][c1] = EMPTY

def on_resign():     print("Resigned")
def on_save():       print("Save replay")
def fake_legal_moves(board, pos): return []   # replace with engine call

board_screen = BoardScreen(on_move_callback=on_move)
hud          = HUDPanel(on_resign=on_resign, on_save_replay=on_save)

clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        board_screen.handle_click(
            event.pos if event.type == pygame.MOUSEBUTTONDOWN else (0, 0),
            board, ATTACKER_P, fake_legal_moves
        )
        hud.handle_event(event, game_state)

    window.fill((30, 30, 30))
    board_screen.render(window, board, offset=(0, 0))
    hud.draw(window, game_state)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()