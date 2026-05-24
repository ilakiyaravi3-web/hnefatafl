"""
tournament.py
=============
Round-robin ablation tournament for Hnefatafl.

Agents
------
  mcts_full        MCTS with all 5 heuristic components
  mcts_no_escape   MCTS missing escape-lane component
  mcts_no_corner   MCTS missing king-distance-to-corner component
  mcts_no_prox     MCTS missing attacker-proximity component
  mcts_no_piece    MCTS missing piece-count component
  mcts_no_mob      MCTS missing king-mobility component
  minimax          Minimax with alpha-beta pruning, depth 3
  random           Uniform random legal move

Each pair plays N games with each side (attacker / defender).
Results are saved to  results/tournament_results.json
and printed as a live leaderboard.

Usage
-----
    # Full run (2100 games, ~hours)
    python tournament.py

    # Quick smoke test (2 games per pair per side)
    python tournament.py --games 2 --time 0.3

    # Resume after a crash  (skips already-recorded matchups)
    python tournament.py --resume
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import time
from itertools import combinations
from typing import Dict, List, Optional, Tuple

# ── Engine ────────────────────────────────────────────────────────────────────
from game_interface import (
    HnefataflState,
    eval_state,
    best_move_heuristic,
    get_all_legal_moves,
    find_king,
    CORNERS,
    _escape_lane_score,
    get_legal_moves,
    ATTACKER_P, DEFENDER_P, KING_P,
    SIZE,
)

# ── Config ────────────────────────────────────────────────────────────────────
RESULTS_DIR  = "results"
RESULTS_FILE = os.path.join(RESULTS_DIR, "tournament_results.json")

DEFAULT_GAMES_PER_SIDE = 100   # per matchup per role
DEFAULT_TIME_BUDGET    = 0.85  # seconds per MCTS move
MINIMAX_DEPTH          = 3
MAX_GAME_MOVES         = 200   # draw limit


# ══════════════════════════════════════════════════════════════════════════════
# Ablated evaluation functions
# Each variant removes exactly one component from eval_state.
# ══════════════════════════════════════════════════════════════════════════════

def _base_components(state: HnefataflState):
    """Compute all raw components. Returns dict of floats."""
    board    = state.board
    king_pos = find_king(board)

    if king_pos is None:
        return None   # terminal — caller handles

    kr, kc = king_pos

    min_corner_dist = min(abs(kr - cr) + abs(kc - cc) for cr, cc in CORNERS)
    corner_score    = (10 - min_corner_dist) / 10.0

    king_moves    = len(get_legal_moves(board, king_pos))
    mobility_score = min(king_moves / 8.0, 1.0)

    atk_count = sum(1 for r in range(SIZE) for c in range(SIZE) if board[r][c] == ATTACKER_P)
    def_count = sum(1 for r in range(SIZE) for c in range(SIZE) if board[r][c] == DEFENDER_P)
    piece_score = (atk_count - def_count) / 12.0

    if atk_count > 0:
        total_dist = sum(
            abs(kr - r) + abs(kc - c)
            for r in range(SIZE) for c in range(SIZE)
            if board[r][c] == ATTACKER_P
        )
        proximity_score = (10 - total_dist / atk_count) / 10.0
    else:
        proximity_score = 0.0

    escape_score = _escape_lane_score(board, king_pos)

    return {
        "corner":    corner_score,
        "mobility":  mobility_score,
        "piece":     piece_score,
        "proximity": proximity_score,
        "escape":    escape_score,
    }


def _make_ablated_eval(disabled: str):
    """Return an eval function with one component zeroed out."""
    WEIGHTS = {
        "corner":    -3.0,
        "piece":     +1.5,
        "proximity": +2.0,
        "mobility":  -1.5,
        "escape":    -1.5,
    }

    def ablated_eval(state: HnefataflState, player: str) -> float:
        board    = state.board
        king_pos = find_king(board)

        if king_pos is None:
            return 7.0 if player == "attacker" else -7.0
        if king_pos in CORNERS:
            return -7.0 if player == "attacker" else 7.0

        comps = _base_components(state)
        if comps is None:
            return 0.0

        raw = sum(
            w * comps[k]
            for k, w in WEIGHTS.items()
            if k != disabled          # ← the ablation
        )
        return raw if player == "attacker" else -raw

    ablated_eval.__name__ = f"eval_no_{disabled}"
    return ablated_eval


# ══════════════════════════════════════════════════════════════════════════════
# Agent implementations
# ══════════════════════════════════════════════════════════════════════════════

class RandomAgent:
    name = "random"

    def choose_move(self, state: HnefataflState, player: str):
        moves = get_all_legal_moves(state.board, player)
        return random.choice(moves) if moves else None


class HeuristicAgent:
    """Pure greedy — picks the best-eval move with no search."""
    name = "heuristic"

    def choose_move(self, state: HnefataflState, player: str):
        return best_move_heuristic(state, player)


# ── MCTS (self-contained, no global state so ablations are safe) ──────────────

class _MctsNode:
    __slots__ = ("state", "player", "parent", "move",
                 "visits", "value", "untried", "children", "h_val")

    def __init__(self, state, player, parent=None, move=None, eval_fn=None):
        self.state   = state
        self.player  = player
        self.parent  = parent
        self.move    = move
        self.visits  = 0
        self.value   = 0.0
        self.children: Dict = {}

        if state.is_terminal():
            self.untried = []
            self.h_val   = 1.0 if state.get_winner() == player else 0.0
        else:
            self.untried = list(state.get_legal_moves(player))
            self.h_val   = eval_fn(state, player) if eval_fn else 0.0

    def is_fully_expanded(self): return len(self.untried) == 0
    def is_terminal(self):       return self.state.is_terminal()

    def opponent(self):
        return "defender" if self.player == "attacker" else "attacker"

    def ucb(self, move, c=0.70, pb_w=5.0):
        child = self.children.get(move)
        if child is None or child.visits == 0:
            return float("inf")
        exploit   = child.value / child.visits
        explore   = c * math.sqrt(math.log(self.visits + 1) / child.visits)
        h_norm    = max(0.0, min(1.0, (child.h_val + 7.0) / 12.0))
        prog_bias = pb_w * h_norm / (child.visits + 1)
        return exploit + explore + prog_bias

    def best_child(self):
        best_sc, best_m, best_c = float("-inf"), None, None
        for m, ch in self.children.items():
            sc = self.ucb(m)
            if sc > best_sc:
                best_sc, best_m, best_c = sc, m, ch
        return best_m, best_c

    def best_final(self):
        if not self.children:
            fb = self.state.get_legal_moves(self.player)
            return fb[0] if fb else None
        return max(self.children, key=lambda m: self.children[m].visits)


class MCTSAgent:
    def __init__(self, name: str, eval_fn=None, time_budget: float = DEFAULT_TIME_BUDGET):
        self.name        = name
        self.eval_fn     = eval_fn or eval_state
        self.time_budget = time_budget

    def choose_move(self, state: HnefataflState, player: str):
        root     = _MctsNode(state, player, eval_fn=self.eval_fn)
        deadline = time.time() + self.time_budget

        while time.time() < deadline:
            node = self._select(root)
            if not node.is_terminal() and not node.is_fully_expanded():
                node = self._expand(node)
            result = self._simulate(node)
            self._backprop(node, result)

        return root.best_final()

    def _select(self, node):
        while not node.is_terminal() and node.is_fully_expanded() and node.children:
            _, node = node.best_child()
        return node

    def _expand(self, node):
        move     = node.untried.pop()
        opp      = node.opponent()
        opp_move = best_move_heuristic(node.state, opp)
        nxt      = node.state.apply_move(move)
        if opp_move and not nxt.is_terminal():
            nxt = nxt.apply_move(opp_move)
        child = _MctsNode(nxt, node.player, parent=node, move=move, eval_fn=self.eval_fn)
        node.children[move] = child
        return child

    def _simulate(self, node):
        state  = node.state
        player = node.player
        if state.is_terminal():
            return 1.0 if state.get_winner() == player else 0.0
        raw = self.eval_fn(state, player)
        return max(0.3, min(0.7, 0.3 + 0.4 * (max(-7.0, min(5.0, raw)) + 7.0) / 12.0))

    def _backprop(self, node, result):
        cur = node
        while cur:
            cur.visits += 1
            cur.value  += result
            cur         = cur.parent


# ── Minimax with alpha-beta ───────────────────────────────────────────────────

class MinimaxAgent:
    name = "minimax"

    def __init__(self, depth: int = MINIMAX_DEPTH):
        self.depth = depth

    def choose_move(self, state: HnefataflState, player: str):
        moves = get_all_legal_moves(state.board, player)
        if not moves:
            return None

        best_score = float("-inf")
        best_move  = moves[0]

        for move in moves:
            nxt   = state.apply_move(move)
            score = self._minimax(nxt, self.depth - 1, float("-inf"), float("inf"),
                                  False, player)
            if score > best_score:
                best_score = score
                best_move  = move

        return best_move

    def _minimax(self, state, depth, alpha, beta, maximising, root_player):
        if state.is_terminal() or depth == 0:
            return eval_state(state, root_player)

        moves = get_all_legal_moves(state.board, state.current_player())
        if not moves:
            return eval_state(state, root_player)

        if maximising:
            val = float("-inf")
            for move in moves:
                nxt = state.apply_move(move)
                val = max(val, self._minimax(nxt, depth - 1, alpha, beta, False, root_player))
                alpha = max(alpha, val)
                if alpha >= beta:
                    break
            return val
        else:
            val = float("inf")
            for move in moves:
                nxt = state.apply_move(move)
                val = min(val, self._minimax(nxt, depth - 1, alpha, beta, True, root_player))
                beta = min(beta, val)
                if alpha >= beta:
                    break
            return val


# ══════════════════════════════════════════════════════════════════════════════
# Agent registry
# ══════════════════════════════════════════════════════════════════════════════

def build_agents(time_budget: float = DEFAULT_TIME_BUDGET) -> Dict[str, object]:
    ablations = {
        "escape":    "mcts_no_escape",
        "corner":    "mcts_no_corner",
        "proximity": "mcts_no_prox",
        "piece":     "mcts_no_piece",
        "mobility":  "mcts_no_mob",
    }

    agents = {
        "mcts_full": MCTSAgent("mcts_full", eval_fn=eval_state,  time_budget=time_budget),
        "minimax":   MinimaxAgent(depth=MINIMAX_DEPTH),
        "heuristic": HeuristicAgent(),
        "random":    RandomAgent(),
    }

    for component, agent_name in ablations.items():
        fn = _make_ablated_eval(component)
        agents[agent_name] = MCTSAgent(agent_name, eval_fn=fn, time_budget=time_budget)

    return agents


# ══════════════════════════════════════════════════════════════════════════════
# Single game runner
# ══════════════════════════════════════════════════════════════════════════════

def run_game(attacker_agent, defender_agent) -> dict:
    """Play one game. Returns result dict."""
    import datetime
    state    = HnefataflState()
    agents   = {"attacker": attacker_agent, "defender": defender_agent}
    t_start  = time.time()

    while not state.is_terminal():
        player = state.current_player()
        agent  = agents[player]
        move   = agent.choose_move(state, player)
        if move is None:
            break
        state = state.apply_move(move)

    winner   = state.get_winner()
    elapsed  = round(time.time() - t_start, 2)
    return {
        "attacker":        attacker_agent.name,
        "defender":        defender_agent.name,
        "winner":          winner,           # "attacker" | "defender" | None
        "attacker_won":    1 if winner == "attacker" else 0,
        "defender_won":    1 if winner == "defender" else 0,
        "draw":            1 if winner is None else 0,
        "move_count":      state.move_count,
        "duration_s":      elapsed,
        "timestamp":       datetime.datetime.now().isoformat(timespec="seconds"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tournament runner
# ══════════════════════════════════════════════════════════════════════════════

def load_existing_results() -> List[dict]:
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []


CSV_FILE = os.path.join(RESULTS_DIR, "tournament_results.csv")

CSV_COLUMNS = [
    "attacker", "defender", "winner",
    "attacker_won", "defender_won", "draw",
    "move_count", "duration_s", "timestamp",
]


def save_results(results: List[dict]):
    """Save full results as JSON + flat CSV for easy analysis in pandas/Excel/R."""
    import csv
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def _already_done(results: List[dict], atk: str, dfn: str) -> int:
    """Count how many games of this exact (attacker, defender) pair are logged."""
    return sum(
        1 for r in results
        if r["attacker"] == atk and r["defender"] == dfn
    )


def print_leaderboard(results: List[dict], agents: List[str]):
    """Print a simple win-rate table to stdout."""
    stats: Dict[str, Dict] = {a: {"wins": 0, "losses": 0, "draws": 0, "games": 0}
                               for a in agents}

    for r in results:
        atk, dfn, winner = r["attacker"], r["defender"], r["winner"]
        for name in [atk, dfn]:
            if name not in stats:
                continue
            stats[name]["games"] += 1
            if winner is None:
                stats[name]["draws"] += 1
            elif (winner == "attacker" and name == atk) or \
                 (winner == "defender" and name == dfn):
                stats[name]["wins"] += 1
            else:
                stats[name]["losses"] += 1

    rows = []
    for name, s in stats.items():
        g = s["games"]
        wr = s["wins"] / g if g else 0.0
        rows.append((name, s["wins"], s["losses"], s["draws"], g, wr))

    rows.sort(key=lambda x: -x[5])

    print("\n" + "=" * 65)
    print(f"{'Agent':<22} {'W':>5} {'L':>5} {'D':>5} {'G':>5} {'WR%':>7}")
    print("-" * 65)
    for name, w, l, d, g, wr in rows:
        print(f"{name:<22} {w:>5} {l:>5} {d:>5} {g:>5} {wr*100:>6.1f}%")
    print("=" * 65 + "\n")


def run_tournament(games_per_side: int, time_budget: float, resume: bool):
    agents     = build_agents(time_budget)
    agent_names = list(agents.keys())

    results = load_existing_results() if resume else []
    if not resume and os.path.exists(RESULTS_FILE):
        # Back up old results
        backup = RESULTS_FILE.replace(".json", "_backup.json")
        os.rename(RESULTS_FILE, backup)
        print(f"Backed up previous results to {backup}")

    pairs = list(combinations(agent_names, 2))
    total_matchups = len(pairs) * 2   # each pair plays both sides
    total_games    = total_matchups * games_per_side

    print(f"\nTournament: {len(agent_names)} agents, {len(pairs)} unique pairs")
    print(f"           {total_games} total games ({games_per_side} per side per matchup)")
    print(f"           Time budget per MCTS move: {time_budget}s\n")

    game_num = 0
    t0 = time.time()

    for a1, a2 in pairs:
        for atk_name, dfn_name in [(a1, a2), (a2, a1)]:
            atk_agent = agents[atk_name]
            dfn_agent = agents[dfn_name]

            done = _already_done(results, atk_name, dfn_name) if resume else 0
            remaining = games_per_side - done

            if remaining <= 0:
                print(f"  Skipping {atk_name} vs {dfn_name} (already done)")
                game_num += games_per_side
                continue

            print(f"  {atk_name:<22} (ATK)  vs  {dfn_name:<22} (DEF)  —  {remaining} games")

            for g in range(remaining):
                game_num += 1
                result = run_game(atk_agent, dfn_agent)
                results.append(result)

                elapsed   = time.time() - t0
                per_game  = elapsed / game_num
                remaining_total = total_games - game_num
                eta_s     = per_game * remaining_total

                print(f"    [{game_num:>5}/{total_games}] "
                      f"winner={str(result['winner']):<10} "
                      f"moves={result['move_count']:>3}  "
                      f"ETA {eta_s/60:.1f}min", end="\r")

                # Save after every game (crash-safe)
                save_results(results)

            print()  # newline after \r progress

        print_leaderboard(results, agent_names)

    print("\nTournament complete.")
    print_leaderboard(results, agent_names)
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hnefatafl ablation tournament")
    parser.add_argument("--games",  type=int,   default=DEFAULT_GAMES_PER_SIDE,
                        help="Games per side per matchup (default 100)")
    parser.add_argument("--time",   type=float, default=DEFAULT_TIME_BUDGET,
                        help="MCTS time budget per move in seconds (default 0.85)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from existing results file")
    args = parser.parse_args()

    run_tournament(
        games_per_side=args.games,
        time_budget=args.time,
        resume=args.resume,
    )