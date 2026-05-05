from __future__ import annotations
import math
import time
from typing import Dict, List, Optional, Tuple

TIME_BUDGET_S      = 0.85
UCB_C              = 0.70
PROGRESSIVE_BIAS_W = 5.0

try:
    from game_interface import HnefataflState, eval_state, best_move_heuristic
    GAME_INTERFACE_READY = True
except ImportError:
    GAME_INTERFACE_READY = False

    class HnefataflState:
        def get_legal_moves(self, player: str) -> List:
            return ["up", "down", "left", "right"]
        def apply_move(self, move) -> "HnefataflState":
            return HnefataflState()
        def is_terminal(self) -> bool:
            return False
        def get_winner(self) -> Optional[str]:
            return None
        def current_player(self) -> str:
            return "attacker"

    def eval_state(state: HnefataflState, player: str) -> float:
        return 0.0

    def best_move_heuristic(state: HnefataflState, player: str):
        moves = state.get_legal_moves(player)
        return moves[0] if moves else None


class MctsNode:
    __slots__ = (
        "state", "player", "parent", "move",
        "visits", "value", "untried", "children", "heuristic_value",
    )

    def __init__(
        self,
        state: HnefataflState,
        player: str,
        parent: Optional[MctsNode] = None,
        move=None,
    ) -> None:
        self.state   = state
        self.player  = player
        self.parent  = parent
        self.move    = move
        self.visits  = 0
        self.value   = 0.0

        if state.is_terminal():
            self.untried         = []
            self.heuristic_value = 1.0 if state.get_winner() == player else 0.0
        else:
            self.untried         = list(state.get_legal_moves(player))
            self.heuristic_value = eval_state(state, player)

        self.children: Dict[any, MctsNode] = {}

    def is_fully_expanded(self) -> bool:
        return len(self.untried) == 0

    def is_terminal(self) -> bool:
        return self.state.is_terminal()

    def opponent(self) -> str:
        return "defender" if self.player == "attacker" else "attacker"

    def ucb_score(self, move, parent_visits: int) -> float:
        child = self.children.get(move)
        if child is None or child.visits == 0:
            return float("inf")
        exploit   = child.value / child.visits
        explore   = UCB_C * math.sqrt(math.log(parent_visits + 1) / child.visits)
        h_norm    = max(0.0, min(1.0, (child.heuristic_value + 7.0) / 12.0))
        prog_bias = PROGRESSIVE_BIAS_W * h_norm / (child.visits + 1)
        return exploit + explore + prog_bias

    def best_child(self) -> Tuple[any, "MctsNode"]:
        best_score        = float("-inf")
        best_move, best_c = None, None
        for m, child in self.children.items():
            sc = self.ucb_score(m, self.visits)
            if sc > best_score:
                best_score        = sc
                best_move, best_c = m, child
        return best_move, best_c

    def best_final_move(self):
        if not self.children:
            fallback = self.state.get_legal_moves(self.player)
            return fallback[0] if fallback else None
        return max(self.children, key=lambda m: self.children[m].visits)


class MCTS:
    def choose_move(self, state: HnefataflState, player: str):
        root       = MctsNode(state, player)
        deadline   = time.time() + TIME_BUDGET_S
        iterations = 0
        while time.time() < deadline:
            self._run_iteration(root)
            iterations += 1
        chosen = root.best_final_move()
        print(f"[MCTS] player={player} move={chosen} iterations={iterations} root_visits={root.visits}")
        return chosen

    def _run_iteration(self, root: MctsNode) -> None:
        node = self._select(root)
        if not node.is_terminal() and not node.is_fully_expanded():
            node = self._expand(node)
        result = self._simulate(node)
        self._backprop(node, result)

    def _select(self, node: MctsNode) -> MctsNode:
        while not node.is_terminal() and node.is_fully_expanded() and node.children:
            _, node = node.best_child()
        return node

    def _expand(self, node: MctsNode) -> MctsNode:
        move       = node.untried.pop()
        opp        = node.opponent()
        opp_move   = best_move_heuristic(node.state, opp)
        next_state = node.state.apply_move(move)
        if opp_move is not None and not next_state.is_terminal():
            next_state = next_state.apply_move(opp_move)
        child = MctsNode(state=next_state, player=node.player, parent=node, move=move)
        node.children[move] = child
        return child

    def _simulate(self, node: MctsNode) -> float:
        state  = node.state
        player = node.player
        if state.is_terminal():
            return 1.0 if state.get_winner() == player else 0.0
        raw    = eval_state(state, player)
        result = 0.3 + 0.4 * (max(-7.0, min(5.0, raw)) + 7.0) / 12.0
        return max(0.3, min(0.7, result))

    def _backprop(self, node: MctsNode, result: float) -> None:
        current = node
        while current is not None:
            current.visits += 1
            current.value  += result
            current         = current.parent


searcher = MCTS()


def get_mcts_move(state: HnefataflState, player: str):
    return searcher.choose_move(state, player)


if __name__ == "__main__":
    state  = HnefataflState()
    player = "attacker"
    move   = get_mcts_move(state, player)
    print(f"Chosen move: {move}")
