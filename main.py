"""
main.py — Hnefatafl entry point
================================
Modes (set at startup):
    PvP     : two human players
    PvAI    : human (attacker) vs MCTS defender
    AIvP    : MCTS attacker vs human defender
    AIvAI   : watch two MCTS agents play each other
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

# ── MCTS agent ────────────────────────────────────────────────────────────────
from agent_mcts_hnefatafl import get_mcts_move

# ── Config ────────────────────────────────────────────────────────────────────
WINDOW_W = 800   # 660 board + 140 HUD panel
WINDOW_H = 660
FPS      = 60
BOARD_OFFSET = (0, 0)

# Change these to switch game mode:
#   "human"  or  "mcts"
ATTACKER_CTRL = "mcts"
DEFENDER_CTRL = "mcts"


# ── Helper: thin GameState object the HUD expects ─────────────────────────────
class HUDState:
    """Tiny proxy so HUDPanel can read display fields without touching engine state."""
    def __init__(self):
        self.turn              = "Attacker"   # "Attacker" | "Defender" (capitalised for display)
        self.captures          = {"attacker": 0, "defender": 0}
        self.ai_mode           = False
        self.agent_names       = {"attacker": "Human", "defender": "Human"}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Hnefatafl — Viking Chess")
    clock  = pygame.time.Clock()

    # ── Game state ────────────────────────────────────────────────────────────
    game_state  = HnefataflState()           # full rules engine state
    hud_state   = HUDState()

    # Determine AI mode
    ai_plays_attacker = (ATTACKER_CTRL == "mcts")
    ai_plays_defender = (DEFENDER_CTRL == "mcts")
    hud_state.ai_mode = ai_plays_attacker or ai_plays_defender
    hud_state.agent_names = {
        "attacker": "MCTS" if ai_plays_attacker else "Human",
        "defender": "MCTS" if ai_plays_defender else "Human",
    }

    winner_text: str | None = None   # set when game ends

    # ── AI threading ─────────────────────────────────────────────────────────
    # AI moves run in a background thread so the UI stays responsive.
    ai_thinking  = False
    ai_result    = [None]   # [move] written by worker thread

    def _run_ai(state: HnefataflState, player: str):
        nonlocal ai_thinking
        move = get_mcts_move(state, player)
        ai_result[0] = move
        ai_thinking  = False

    def _start_ai_if_needed():
        nonlocal ai_thinking
        if winner_text:
            return
        turn = game_state.current_player()
        if (turn == "attacker" and ai_plays_attacker) or \
           (turn == "defender" and ai_plays_defender):
            if not ai_thinking:
                ai_thinking  = True
                ai_result[0] = None
                t = threading.Thread(target=_run_ai, args=(game_state, turn), daemon=True)
                t.start()

    # ── Board callback ────────────────────────────────────────────────────────
    def on_move(from_pos, to_pos):
        """Called by BoardScreen when the human clicks a valid destination."""
        nonlocal game_state, winner_text

        if winner_text or ai_thinking:
            return  # ignore clicks while AI thinks or game is over

        turn = game_state.current_player()
        piece = game_state.board[from_pos[0]][from_pos[1]]

        # Validate it belongs to current player
        if turn == "attacker" and piece != ATTACKER_P:
            return
        if turn == "defender" and piece not in (DEFENDER_P, KING_P):
            return

        _apply_move((from_pos, to_pos))

    def _apply_move(move):
        nonlocal game_state, winner_text

        from_pos, to_pos = move
        new_state = game_state.apply_move(move)

        # Update capture counts in HUD
        hud_state.captures["attacker"] += (
            new_state.attacker_captures - game_state.attacker_captures
        )
        hud_state.captures["defender"] += (
            new_state.defender_captures - game_state.defender_captures
        )

        game_state = new_state

        # Update HUD turn display
        hud_state.turn = "Defender" if game_state.current_player() == "defender" else "Attacker"

        # Update last-move highlight in board screen
        board_screen.last_move = (from_pos, to_pos)

        # Check for game over
        w = game_state.get_winner()
        if w:
            winner_text = f"{'Defenders win!' if w == 'defender' else 'Attackers win!'}"

        # Kick off AI for next turn if needed
        _start_ai_if_needed()

    # ── Legal-moves wrapper (what BoardScreen needs) ──────────────────────────
    def get_legal_moves_fn(board, pos):
        """BoardScreen calls this to get highlight squares."""
        return game_state.get_legal_moves_for_pos(pos)

    # ── UI objects ────────────────────────────────────────────────────────────
    board_screen = BoardScreen(on_move_callback=on_move)

    def on_resign():
        nonlocal winner_text
        w = "defender" if game_state.current_player() == "attacker" else "attacker"
        winner_text = f"{'Defenders win!' if w == 'defender' else 'Attackers win!'} (resign)"

    def on_save():
        _save_replay()

    hud   = HUDPanel(on_resign=on_resign, on_save_replay=on_save)
    ai_viewer = AIViewer() if hud_state.ai_mode else None

    # Font for winner overlay
    pygame.font.init()
    font_big   = pygame.font.SysFont("segoeui", 40, bold=True)
    font_small = pygame.font.SysFont("segoeui", 22)

    # ── Replay saving ─────────────────────────────────────────────────────────
    replay_moves: list = []   # accumulate {from, to, board} dicts

    def _record_move(from_pos, to_pos, board):
        replay_moves.append({
            "from": list(from_pos),
            "to":   list(to_pos),
            "board": [row[:] for row in board],
        })

    original_apply = _apply_move
    def _apply_move_recording(move):
        from_pos, to_pos = move
        original_apply(move)
        _record_move(from_pos, to_pos, game_state.board)
    _apply_move = _apply_move_recording  # shadow with recording version

    # Re-point on_move closure to the recording version
    def on_move(from_pos, to_pos):
        if winner_text or ai_thinking:
            return
        turn  = game_state.current_player()
        piece = game_state.board[from_pos[0]][from_pos[1]]
        if turn == "attacker" and piece != ATTACKER_P:
            return
        if turn == "defender" and piece not in (DEFENDER_P, KING_P):
            return
        _apply_move_recording((from_pos, to_pos))

    board_screen.on_move = on_move

    def _save_replay():
        import json, datetime
        data = {
            "agent_attacker": hud_state.agent_names["attacker"],
            "agent_defender": hud_state.agent_names["defender"],
            "winner": winner_text or "In progress",
            "moves": replay_moves,
        }
        fname = f"replay_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fname, "w") as fh:
            json.dump(data, fh)
        print(f"[Replay] Saved to {fname}")

    # ── Kick off AI for the very first move if needed ─────────────────────────
    _start_ai_if_needed()

    # ── Main loop ─────────────────────────────────────────────────────────────
    running = True
    while running:

        # Check if AI has a result ready
        if not ai_thinking and ai_result[0] is not None:
            move = ai_result[0]
            ai_result[0] = None
            _apply_move_recording(move)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Only pass clicks to board if it's a human turn
            if event.type == pygame.MOUSEBUTTONDOWN:
                turn = game_state.current_player()
                human_turn = (
                    (turn == "attacker" and not ai_plays_attacker) or
                    (turn == "defender" and not ai_plays_defender)
                )
                if human_turn and not winner_text:
                    board_screen.handle_click(
                        event.pos, game_state.board,
                        ATTACKER_P if turn == "attacker" else DEFENDER_P,
                        get_legal_moves_fn,
                        offset=BOARD_OFFSET,
                    )

            board_screen.handle_keydown(event.key if event.type == pygame.KEYDOWN else -1)
            hud.handle_event(event, hud_state)
            if ai_viewer:
                ai_viewer.handle_event(event)

        # Draw
        window.fill((30, 30, 30))
        board_screen.render(window, game_state.board, offset=BOARD_OFFSET)
        hud.draw(window, hud_state)
        if ai_viewer:
            ai_viewer.draw(window, hud_state)

        # "AI thinking" indicator
        if ai_thinking:
            surf = font_small.render("AI thinking…", True, (200, 200, 100))
            window.blit(surf, (10, WINDOW_H - 28))

        # Winner overlay
        if winner_text:
            _draw_winner_overlay(window, winner_text, font_big, font_small)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


def _draw_winner_overlay(window, text, font_big, font_small):
    overlay = pygame.Surface((660, 100), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    window.blit(overlay, (0, 280))
    surf = font_big.render(text, True, (255, 220, 50))
    rect = surf.get_rect(center=(330, 310))
    window.blit(surf, rect)
    hint = font_small.render("Press Save Replay to keep this game", True, (180, 180, 180))
    hrect = hint.get_rect(center=(330, 355))
    window.blit(hint, hrect)


if __name__ == "__main__":
    main()