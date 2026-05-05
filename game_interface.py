"""
game_interface.py
=================
Rules engine for Hnefatafl (11×11 Fetlar variant).
Exposes exactly what agent_mcts_hnefatafl.py imports:

    from game_interface import HnefataflState, eval_state, best_move_heuristic

Board encoding (integers, matching ui/pieces.py):
    0 = EMPTY
    1 = ATTACKER
    2 = DEFENDER
    3 = KING

Players:   "attacker" | "defender"
Attackers win  → capture the king (surround on 4 sides, or 3 sides + throne/corner)
Defenders win  → king reaches any corner square
"""

from __future__ import annotations
import copy
from typing import List, Optional, Tuple

# ── Constants (must match ui/pieces.py) ──────────────────────────────────────

EMPTY      = 0
ATTACKER_P = 1
DEFENDER_P = 2
KING_P     = 3

SIZE = 11

THRONE = (5, 5)
CORNERS = {(0, 0), (0, 10), (10, 0), (10, 10)}
# Squares where only the king may stand (corners + throne)
RESTRICTED = CORNERS | {THRONE}

# King-capture helpers: these squares act as hostile pieces when checking
# whether the king is captured.
HOSTILE_TO_KING = CORNERS | {THRONE}   # empty throne/corners count as captors

# ── Starting board ────────────────────────────────────────────────────────────

def _make_start_board() -> List[List[int]]:
    """Return the canonical Fetlar 11×11 starting position."""
    b = [[EMPTY] * SIZE for _ in range(SIZE)]

    # Attackers — 24 pieces arranged in four arms
    attacker_positions = [
        # top arm
        (0, 3), (0, 4), (0, 5), (0, 6), (0, 7),
        (1, 5),
        # bottom arm
        (10, 3), (10, 4), (10, 5), (10, 6), (10, 7),
        (9, 5),
        # left arm
        (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
        (5, 1),
        # right arm
        (3, 10), (4, 10), (5, 10), (6, 10), (7, 10),
        (5, 9),
    ]
    for r, c in attacker_positions:
        b[r][c] = ATTACKER_P

    # Defenders — 12 pieces around the throne
    defender_positions = [
        (3, 5), (4, 4), (4, 5), (4, 6),
        (5, 3), (5, 4),       (5, 6), (5, 7),
        (6, 4), (6, 5), (6, 6),
        (7, 5),
    ]
    for r, c in defender_positions:
        b[r][c] = DEFENDER_P

    # King
    b[5][5] = KING_P

    return b

STARTING_BOARD = _make_start_board()


# ── Utility ───────────────────────────────────────────────────────────────────

def _in_bounds(r: int, c: int) -> bool:
    return 0 <= r < SIZE and 0 <= c < SIZE


def _copy_board(board: List[List[int]]) -> List[List[int]]:
    return [row[:] for row in board]


# ── Legal-move generation ─────────────────────────────────────────────────────

def get_legal_moves(board: List[List[int]], pos: Tuple[int, int]) -> List[Tuple[int, int]]:
    """
    Return all squares reachable by the piece at `pos`.
    Pieces slide any number of squares orthogonally (rook-style).
    Non-king pieces cannot land on restricted squares.
    """
    r, c = pos
    piece = board[r][c]
    if piece == EMPTY:
        return []

    is_king = (piece == KING_P)
    moves: List[Tuple[int, int]] = []

    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        while _in_bounds(nr, nc):
            if board[nr][nc] != EMPTY:
                break  # blocked by any piece
            dest = (nr, nc)
            if dest in RESTRICTED and not is_king:
                nr += dr
                nc += dc
                continue  # non-king cannot land here, but can pass through? No — restricted means no landing.
                # Actually in Fetlar rules restricted squares cannot be *entered*
                # by non-king pieces at all; the slide stops before them.
                # The break happens implicitly since we continue — but we must
                # stop sliding if the path goes *through* restricted? No:
                # restricted only prevents landing, not passing through.
                # ↑ Correction applied below via restructured logic.
            moves.append(dest)
            nr += dr
            nc += dc

    return moves


def _get_legal_moves_corrected(board: List[List[int]], pos: Tuple[int, int]) -> List[Tuple[int, int]]:
    """
    Correct slide logic:
    - pieces slide through empty squares (restricted squares are empty but
      non-king pieces cannot *land* on them — they can slide past them).
    """
    r, c = pos
    piece = board[r][c]
    if piece == EMPTY:
        return []

    is_king = (piece == KING_P)
    moves: List[Tuple[int, int]] = []

    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        while _in_bounds(nr, nc):
            cell = board[nr][nc]
            if cell != EMPTY:
                break  # blocked by a piece
            dest = (nr, nc)
            if not (dest in RESTRICTED and not is_king):
                moves.append(dest)
            nr += dr
            nc += dc

    return moves


# Replace the first (wrong) version with the corrected one
get_legal_moves = _get_legal_moves_corrected


def get_all_legal_moves(board: List[List[int]], player: str) -> List[Tuple[Tuple[int,int], Tuple[int,int]]]:
    """Return list of (from_pos, to_pos) for every legal move of `player`."""
    result = []
    own = _own_pieces(player)
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] in own:
                for dest in get_legal_moves(board, (r, c)):
                    result.append(((r, c), dest))
    return result


def _own_pieces(player: str):
    if player == "attacker":
        return {ATTACKER_P}
    return {DEFENDER_P, KING_P}


# ── Move application + capture logic ─────────────────────────────────────────

def _is_hostile(board: List[List[int]], pos: Tuple[int, int], to_piece: int) -> bool:
    """
    Return True if `pos` is hostile to `to_piece`.
    Hostile means:
      - an enemy piece occupies the square, OR
      - the square is the throne (empty counts as hostile for captures), OR
      - the square is a corner (always hostile)
    """
    if pos in CORNERS:
        return True
    r, c = pos
    occupant = board[r][c]
    if occupant == EMPTY:
        # Empty throne is hostile to all
        return pos == THRONE
    # Occupied: hostile if enemy
    if to_piece == ATTACKER_P:
        return occupant in (DEFENDER_P, KING_P)
    else:  # DEFENDER or KING
        return occupant == ATTACKER_P


def _check_captures_after_move(board: List[List[int]], moved_to: Tuple[int, int], mover_player: str) -> List[Tuple[int, int]]:
    """
    After `mover_player` places a piece at `moved_to`, check whether any
    enemy pieces are now sandwiched (custodian capture).
    Returns list of captured positions.
    """
    enemy_pieces = _own_pieces("defender" if mover_player == "attacker" else "attacker")
    captured = []

    r, c = moved_to
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if not _in_bounds(nr, nc):
            continue
        target = board[nr][nc]
        if target not in enemy_pieces:
            continue
        # The king is captured differently (needs 4-side surround), handled separately
        if target == KING_P:
            continue
        # Check the far side
        fr, fc = nr + dr, nc + dc
        if not _in_bounds(fr, fc):
            continue
        if _is_hostile(board, (fr, fc), target):
            captured.append((nr, nc))

    return captured


def _is_king_captured(board: List[List[int]], king_pos: Tuple[int, int]) -> bool:
    """
    King is captured when surrounded on all 4 orthogonal sides by
    attackers or hostile squares (throne, corners).
    Special case: on the throne, needs all 4 sides hostile.
    Adjacent to throne: 3 attackers + throne counts.
    Everywhere else: 2 attackers sandwiching (normal custodian).
    
    We use the simple Fetlar rule: king needs 4 hostile neighbors.
    """
    r, c = king_pos
    hostile_count = 0
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if not _in_bounds(nr, nc):
            hostile_count += 1   # board edge is not a capture side in standard rules, skip
            # Actually in standard Fetlar the king cannot be captured against the edge —
            # revert: edge is NOT hostile.
            hostile_count -= 1
            continue
        pos = (nr, nc)
        occ = board[nr][nc]
        if occ == ATTACKER_P:
            hostile_count += 1
        elif pos in HOSTILE_TO_KING and occ == EMPTY:
            hostile_count += 1

    return hostile_count >= 4


def apply_move(board: List[List[int]], from_pos: Tuple[int,int], to_pos: Tuple[int,int], player: str) -> Tuple[List[List[int]], int, int]:
    """
    Apply a move to the board (returns a new board).
    Returns (new_board, attacker_captures, defender_captures).
    """
    new_board = _copy_board(board)
    r1, c1 = from_pos
    r2, c2 = to_pos

    piece = new_board[r1][c1]
    new_board[r2][c2] = piece
    new_board[r1][c1] = EMPTY

    atk_captures = 0
    def_captures = 0

    captured = _check_captures_after_move(new_board, to_pos, player)
    for pos in captured:
        new_board[pos[0]][pos[1]] = EMPTY
        if player == "attacker":
            def_captures += 1
        else:
            atk_captures += 1

    return new_board, atk_captures, def_captures


def find_king(board: List[List[int]]) -> Optional[Tuple[int, int]]:
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] == KING_P:
                return (r, c)
    return None


def check_winner(board: List[List[int]]) -> Optional[str]:
    """
    Return "attacker", "defender", or None.
    Defender wins if king is on any corner.
    Attacker wins if king is captured.
    """
    king_pos = find_king(board)
    if king_pos is None:
        return "attacker"   # king was captured
    if king_pos in CORNERS:
        return "defender"
    if _is_king_captured(board, king_pos):
        return "attacker"
    return None


# ── HnefataflState (interface required by MCTS agent) ────────────────────────

class HnefataflState:
    """
    Immutable-style game state.
    The MCTS agent calls:
        state.get_legal_moves(player)  → list of (from_pos, to_pos)
        state.apply_move(move)         → new HnefataflState
        state.is_terminal()            → bool
        state.get_winner()             → "attacker" | "defender" | None
        state.current_player()         → "attacker" | "defender"
    """

    def __init__(
        self,
        board: Optional[List[List[int]]] = None,
        turn: str = "attacker",
        move_count: int = 0,
        attacker_captures: int = 0,
        defender_captures: int = 0,
    ):
        self.board: List[List[int]] = board if board is not None else _make_start_board()
        self._turn = turn
        self.move_count = move_count
        self.attacker_captures = attacker_captures
        self.defender_captures = defender_captures
        self._winner: Optional[str] = check_winner(self.board)

    # ── MCTS interface ────────────────────────────────────────────────────────

    def get_legal_moves(self, player: str) -> List[Tuple[Tuple[int,int], Tuple[int,int]]]:
        return get_all_legal_moves(self.board, player)

    def apply_move(self, move: Tuple[Tuple[int,int], Tuple[int,int]]) -> "HnefataflState":
        from_pos, to_pos = move
        new_board, atk_cap, def_cap = apply_move(self.board, from_pos, to_pos, self._turn)
        next_turn = "defender" if self._turn == "attacker" else "attacker"
        return HnefataflState(
            board=new_board,
            turn=next_turn,
            move_count=self.move_count + 1,
            attacker_captures=self.attacker_captures + atk_cap,
            defender_captures=self.defender_captures + def_cap,
        )

    def is_terminal(self) -> bool:
        if self._winner is not None:
            return True
        # Draw by move limit (prevents infinite games in MCTS rollouts)
        if self.move_count >= 200:
            return True
        # No legal moves = loss for that player
        return len(get_all_legal_moves(self.board, self._turn)) == 0

    def get_winner(self) -> Optional[str]:
        if self._winner is not None:
            return self._winner
        if self.move_count >= 200:
            return None  # draw
        if len(get_all_legal_moves(self.board, self._turn)) == 0:
            # Current player has no moves — they lose
            return "defender" if self._turn == "attacker" else "attacker"
        return None

    def current_player(self) -> str:
        return self._turn

    # ── Convenience helpers used by main.py ──────────────────────────────────

    def get_legal_moves_for_pos(self, pos: Tuple[int,int]) -> List[Tuple[int,int]]:
        """Destinations only — for click-highlight in the UI."""
        return get_legal_moves(self.board, pos)

    @property
    def turn(self) -> str:
        return self._turn

    def __repr__(self):
        return f"HnefataflState(turn={self._turn}, move={self.move_count})"


# ── Evaluation function (used by MCTS progressive bias) ──────────────────────

def eval_state(state: HnefataflState, player: str) -> float:
    """
    Heuristic score in roughly [-7, +5] (per MCTS agent's normalisation).
    Positive = good for `player`.

    Components:
      1. King distance to nearest corner  (defender wants low)
      2. King mobility                    (defender wants high)
      3. Attacker count                   (attacker wants high)
      4. Defender count                   (attacker wants low)
      5. Attacker proximity to king       (attacker wants low)
      6. King escape path openness        (defender wants open)
    """
    board = state.board
    king_pos = find_king(board)

    if king_pos is None:
        # King captured — very bad for defender
        return 7.0 if player == "attacker" else -7.0

    if king_pos in CORNERS:
        return -7.0 if player == "attacker" else 7.0

    kr, kc = king_pos

    # 1. Min corner distance (0–10 range, normalised)
    min_corner_dist = min(abs(kr - cr) + abs(kc - cc) for cr, cc in CORNERS)
    corner_score = (10 - min_corner_dist) / 10.0  # high = king close to corner

    # 2. King mobility
    king_moves = len(get_legal_moves(board, king_pos))
    mobility_score = min(king_moves / 8.0, 1.0)

    # 3. Piece counts
    atk_count = sum(1 for r in range(SIZE) for c in range(SIZE) if board[r][c] == ATTACKER_P)
    def_count = sum(1 for r in range(SIZE) for c in range(SIZE) if board[r][c] == DEFENDER_P)
    piece_score = (atk_count - def_count) / 12.0  # positive = attacker advantage

    # 4. Attacker proximity to king (mean Manhattan distance to attackers, inverted)
    if atk_count > 0:
        total_dist = sum(
            abs(kr - r) + abs(kc - c)
            for r in range(SIZE) for c in range(SIZE)
            if board[r][c] == ATTACKER_P
        )
        mean_dist = total_dist / atk_count
        proximity_score = (10 - mean_dist) / 10.0  # high = attackers close to king
    else:
        proximity_score = 0.0

    # 5. Open escape lanes: number of unblocked paths king can take towards corners
    escape_score = _escape_lane_score(board, king_pos)

    # Combine — raw score from attacker's perspective
    raw_attacker = (
        - 3.0 * corner_score      # king far from corner = good for attacker
        + 1.5 * piece_score
        + 2.0 * proximity_score
        - 1.5 * mobility_score
        - 1.5 * escape_score
    )

    return raw_attacker if player == "attacker" else -raw_attacker


def _escape_lane_score(board: List[List[int]], king_pos: Tuple[int, int]) -> float:
    """Fraction of the 4 orthogonal directions that have an open path to a corner."""
    kr, kc = king_pos
    open_lanes = 0

    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = kr + dr, kc + dc
        blocked = False
        while _in_bounds(nr, nc):
            if board[nr][nc] == ATTACKER_P:
                blocked = True
                break
            nr += dr
            nc += dc
        if not blocked:
            open_lanes += 1

    return open_lanes / 4.0


# ── Greedy heuristic move (used by MCTS expand step) ─────────────────────────

def best_move_heuristic(
    state: HnefataflState, player: str
) -> Optional[Tuple[Tuple[int,int], Tuple[int,int]]]:
    """
    Fast greedy move selection for MCTS rollout guidance.
    Priority order:
      1. Winning move (king to corner / king capture)
      2. Capture move
      3. King-safety / king-advance move
      4. Best heuristic delta move
      5. First legal move (fallback)
    """
    board = state.board
    moves = get_all_legal_moves(board, player)
    if not moves:
        return None

    king_pos = find_king(board)

    # 1. Check for immediate win
    for move in moves:
        from_pos, to_pos = move
        piece = board[from_pos[0]][from_pos[1]]
        if piece == KING_P and to_pos in CORNERS:
            return move  # king escapes

    # 2. Capture moves (defender: avoid; attacker: prefer)
    if player == "attacker":
        capture_moves = []
        for move in moves:
            from_pos, to_pos = move
            test_board = _copy_board(board)
            test_board[to_pos[0]][to_pos[1]] = test_board[from_pos[0]][from_pos[1]]
            test_board[from_pos[0]][from_pos[1]] = EMPTY
            caps = _check_captures_after_move(test_board, to_pos, player)
            if caps:
                # Bonus for capturing pieces adjacent to king
                priority = len(caps)
                if king_pos:
                    for cap in caps:
                        if abs(cap[0] - king_pos[0]) + abs(cap[1] - king_pos[1]) <= 1:
                            priority += 3
                capture_moves.append((priority, move))
        if capture_moves:
            capture_moves.sort(key=lambda x: -x[0])
            return capture_moves[0][1]

    # 3. Defender: advance king towards nearest corner
    if player == "defender" and king_pos is not None:
        kr, kc = king_pos
        best_corner = min(CORNERS, key=lambda p: abs(p[0]-kr) + abs(p[1]-kc))
        king_moves = [(from_pos, to_pos) for from_pos, to_pos in moves
                      if board[from_pos[0]][from_pos[1]] == KING_P]
        if king_moves:
            king_moves.sort(
                key=lambda m: abs(m[1][0] - best_corner[0]) + abs(m[1][1] - best_corner[1])
            )
            if king_moves[0][1] != king_pos:  # don't stay put
                return king_moves[0]

    # 4. Best heuristic delta
    best_score = float("-inf")
    best_move = moves[0]
    for move in moves:
        from_pos, to_pos = move
        new_board, _, _ = apply_move(board, from_pos, to_pos, player)
        dummy = HnefataflState(board=new_board, turn=player)
        score = eval_state(dummy, player)
        if score > best_score:
            best_score = score
            best_move = move

    return best_move