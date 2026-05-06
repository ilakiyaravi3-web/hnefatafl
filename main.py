
"""
main.py — Hnefatafl entry point (UPDATED WITH MENU SYSTEM)
"""

import sys
import threading
import time
import pygame

# ── Engine ────────────────────────────────────────────────────────────────────
from game_interface import (
    HnefataflState, eval_state, best_move_heuristic,
    ATTACKER_P, DEFENDER_P, KING_P, EMPTY,
)

# ── UI ────────────────────────────────────────────────────────────────────────
from ui.board import BoardScreen
from ui.hud import HUDPanel, AIViewer
from ui.pieces import ATTACKER_P as UI_ATK, DEFENDER_P as UI_DEF

# --- PERSON A CHANGE: import screen manager ---
from ui.screen_manager import ScreenManager

# ── MCTS agent ────────────────────────────────────────────────────────────────
from agent_mcts_hnefatafl import get_mcts_move

# ── Config ────────────────────────────────────────────────────────────────────
WINDOW_W = 800
WINDOW_H = 660
FPS      = 60
BOARD_OFFSET = (0, 0)

ATTACKER_CTRL = "mcts"
DEFENDER_CTRL = "mcts"


class HUDState:
    def __init__(self):
        self.turn = "Attacker"
        self.captures = {"attacker": 0, "defender": 0}
        self.ai_mode = False
        self.agent_names = {"attacker": "Human", "defender": "Human"}


def main():
    pygame.init()
    window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Hnefatafl — Viking Chess")
    clock = pygame.time.Clock()

    # --- PERSON A CHANGE: screen manager setup ---
    screen_manager = ScreenManager()
    screen_manager.setup()

    in_game = False  # controls whether we are in menu or game

    # ── Game state (initialized later when game starts) ────────────────────────
    game_state = None
    hud_state = None
    winner_text = None
    attacker_ctrl = "mcts"
    defender_ctrl = "mcts"

    # --- PERSON A CHANGE: function to start game from setup screen ---
    def start_game_from_menu(config):
        nonlocal in_game, game_state, hud_state, winner_text, attacker_ctrl, defender_ctrl, replay_moves

        in_game = True
        winner_text = None
        replay_moves = []

        # Reset game state
        game_state = HnefataflState()
        hud_state = HUDState()
        
        # Handle AI vs AI mode: extract agent types from config
        if "attacker" in config and "defender" in config:
            attacker_ctrl = config["attacker"].lower()
            defender_ctrl = config["defender"].lower()
        elif "side" in config and "agent" in config:
            # Human vs AI mode: set up human vs agent
            if config["side"] == "Attacker":
                attacker_ctrl = "human"
                defender_ctrl = config["agent"].lower()
            else:
                attacker_ctrl = config["agent"].lower()
                defender_ctrl = "human"
        
        # Trigger first AI move if needed
        _start_ai_if_needed()

    # --- PERSON A CHANGE: register callback ---
    screen_manager.game_callback = start_game_from_menu

    # ── UI objects (created once) ─────────────────────────────────────────────
    board_screen = BoardScreen(on_move_callback=lambda *args: None)

    def on_resign():
        nonlocal winner_text
        w = "defender" if game_state.current_player() == "attacker" else "attacker"
        winner_text = f"{'Defenders win!' if w == 'defender' else 'Attackers win!'} (resign)"

    def on_save():
        pass

    hud = HUDPanel(on_resign=on_resign, on_save_replay=on_save)

    pygame.font.init()
    font_big = pygame.font.SysFont("segoeui", 40, bold=True)
    font_small = pygame.font.SysFont("segoeui", 22)

    replay_moves = []

    # ── AI threading (unchanged logic, guarded by in_game) ─────────────────────
    ai_thinking = False
    ai_result = [None]

    def _run_ai(state, player):
        nonlocal ai_thinking
        move = get_mcts_move(state, player)
        ai_result[0] = move
        ai_thinking = False

    def _start_ai_if_needed():
        nonlocal ai_thinking, attacker_ctrl, defender_ctrl
        if not in_game or winner_text:
            return

        turn = game_state.current_player()
        
        # Check if current player should be controlled by AI
        is_ai_turn = False
        if turn == "attacker" and attacker_ctrl != "human":
            is_ai_turn = True
        elif turn == "defender" and defender_ctrl != "human":
            is_ai_turn = True
        
        if not is_ai_turn:
            return
        
        if not ai_thinking:
            ai_thinking = True
            ai_result[0] = None
            t = threading.Thread(target=_run_ai, args=(game_state, turn), daemon=True)
            t.start()

    def _apply_move(move):
        nonlocal game_state, winner_text

        new_state = game_state.apply_move(move)
        game_state = new_state
        replay_moves.append(move)

        winner = game_state.get_winner()
        if winner:
            if winner == "attacker":
                winner_text = "Attackers Win!"
            elif winner == "defender":
                winner_text = "Defenders Win!"
            else:
                winner_text = "Draw"
        
        _start_ai_if_needed()

    def get_legal_moves_fn(board, pos):
        return game_state.get_legal_moves_for_pos(pos)

    # --- PERSON A CHANGE: updated on_move binding AFTER game starts ---
    def on_move(from_pos, to_pos):
        if not in_game or winner_text:
            return
        _apply_move((from_pos, to_pos))

    board_screen.on_move = on_move

    # ── Main loop ─────────────────────────────────────────────────────────────
    running = True
    while running:

        # AI move execution
        if in_game and not ai_thinking and ai_result[0] is not None:
            move = ai_result[0]
            ai_result[0] = None
            _apply_move(move)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # --- PERSON A CHANGE: route events ---
            if not in_game:
                screen_manager.handle_event(event)
            else:
                if event.type == pygame.MOUSEBUTTONDOWN and not winner_text:
                    board_screen.handle_click(
                        event.pos,
                        game_state.board,
                        ATTACKER_P,
                        get_legal_moves_fn,
                        offset=BOARD_OFFSET,
                    )

                board_screen.handle_keydown(event.key if event.type == pygame.KEYDOWN else -1)
                hud.handle_event(event, hud_state)

        window.fill((30, 30, 30))

        # --- PERSON A CHANGE: draw correct screen ---
        if not in_game:
            screen_manager.draw(window)
        else:
            board_screen.render(window, game_state.board, offset=BOARD_OFFSET)
            hud.draw(window, hud_state)

            # --- PERSON A CHANGE: transition to game over screen ---
            if winner_text:
                screen_manager.screens["game_over"].set_data(
                    winner_text,
                    f"Moves: {len(replay_moves)}"
                )
                screen_manager.go_to("game_over")
                in_game = False

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

