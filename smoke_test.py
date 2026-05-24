"""
smoke_test.py
=============
Quick sanity checks for agent correctness without a full round-robin.

Modes
-----
coverage (default): each agent plays one game as attacker and one as defender
                    against a baseline opponent (18 games total for 9 agents)
pairs:              full pairwise round-robin (still small but larger)

Usage
-----
    python smoke_test.py
    python smoke_test.py --mode coverage --baseline random
    python smoke_test.py --mode pairs --games 1 --time 0.15

On success you will see:
    [PASS] All X matchups completed without errors.
    Results saved to results/smoke_test_results.json (+ CSV)

On failure the traceback tells you exactly which matchup failed.
"""

import argparse
import json
import os
import sys
import time
import traceback

SMOKE_GAMES = 1          # games per side per matchup (pairs mode)
SMOKE_TIME  = 0.20       # very short MCTS budget (keeps it fast)
DEFAULT_MODE = "coverage"
DEFAULT_BASELINE = "random"
RESULTS_DIR = "results"
SMOKE_FILE  = os.path.join(RESULTS_DIR, "smoke_test_results.json")
SMOKE_CSV   = os.path.join(RESULTS_DIR, "smoke_test_results.csv")

# We import from tournament.py so the same agent code is tested
sys.path.insert(0, os.path.dirname(__file__))

from tournament import build_agents, run_game, CSV_COLUMNS
from itertools import combinations


def _pick_baseline(agent_name: str, baseline: str, agents) -> str:
    if agent_name != baseline:
        return baseline
    for name in agents.keys():
        if name != agent_name:
            return name
    return baseline


def _coverage_matchups(agents, baseline: str):
    agent_names = list(agents.keys())
    if baseline not in agents:
        raise ValueError(f"Baseline '{baseline}' not found. Options: {agent_names}")

    matchups = []
    for name in agent_names:
        agent = agents[name]
        opp_name = _pick_baseline(name, baseline, agents)
        opponent = agents[opp_name]
        matchups.append((agent, opponent))  # agent as attacker
        matchups.append((opponent, agent))  # agent as defender
    return matchups


def _pairs_matchups(agents):
    agent_list = list(agents.keys())
    pairs = list(combinations(agent_list, 2))
    matchups = []
    for a1, a2 in pairs:
        matchups.append((agents[a1], agents[a2]))
        matchups.append((agents[a2], agents[a1]))
    return matchups


def run_smoke_test(
    games_per_side: int = SMOKE_GAMES,
    time_budget: float = SMOKE_TIME,
    mode: str = DEFAULT_MODE,
    baseline: str = DEFAULT_BASELINE,
):
    print("=" * 60)
    print("Hnefatafl — Smoke Test")
    print(f"  mode={mode}  games={games_per_side}  time={time_budget}s/move")
    print("=" * 60)

    agents     = build_agents(time_budget=time_budget)
    agent_list = list(agents.keys())

    if mode == "coverage":
        matchups = _coverage_matchups(agents, baseline)
        total = len(matchups) * games_per_side
        print(f"\nAgents ({len(agent_list)}): {', '.join(agent_list)}")
        print(f"Coverage baseline: {baseline}   |   Total games: {total}\n")
    elif mode == "pairs":
        matchups = _pairs_matchups(agents)
        total = len(matchups) * games_per_side
        print(f"\nAgents ({len(agent_list)}): {', '.join(agent_list)}")
        print(f"Pairs:  {len(matchups)//2} unique   |   Total games: {total}\n")
    else:
        raise ValueError("mode must be 'coverage' or 'pairs'")

    results  = []
    failures = []
    t0       = time.time()
    game_num = 0

    for atk, dfn in matchups:
        for g in range(games_per_side):
            game_num += 1
            label = f"[{game_num:>3}/{total}] {atk.name:<22} vs {dfn.name:<22}"
            print(label, end="  ", flush=True)

            try:
                t_start = time.time()
                result  = run_game(atk, dfn)
                elapsed = time.time() - t_start

                print(f"winner={str(result['winner']):<10} "
                      f"moves={result['move_count']:>3}  "
                      f"({elapsed:.1f}s)")
                results.append(result)

            except Exception as e:
                print(f"FAILED — {e}")
                failures.append({
                    "attacker": atk.name,
                    "defender": dfn.name,
                    "game":     g + 1,
                    "error":    traceback.format_exc(),
                })

    elapsed_total = time.time() - t0
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(SMOKE_FILE, "w") as f:
        json.dump({"results": results, "failures": failures}, f, indent=2)

    if results:
        import csv
        with open(SMOKE_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)

    print("\n" + "=" * 60)
    if failures:
        print(f"[FAIL] {len(failures)} matchup(s) failed:")
        for fl in failures:
            print(f"  {fl['attacker']} vs {fl['defender']} game {fl['game']}")
            print(fl["error"])
        sys.exit(1)
    else:
        print(f"[PASS] All {game_num} games completed without errors.")
        print(f"       Total time: {elapsed_total:.1f}s  "
              f"({elapsed_total/game_num:.2f}s per game)")
        print(f"       Results: {SMOKE_FILE}")
        if results:
            print(f"       CSV: {SMOKE_CSV}")
        _print_summary(results, agent_list)


def _print_summary(results, agents):
    stats = {a: {"wins": 0, "games": 0} for a in agents}
    for r in results:
        atk, dfn, winner = r["attacker"], r["defender"], r["winner"]
        for name in [atk, dfn]:
            stats[name]["games"] += 1
            if (winner == "attacker" and name == atk) or \
               (winner == "defender" and name == dfn):
                stats[name]["wins"] += 1

    print("\nSmoke-test win rates:")
    rows = sorted(stats.items(), key=lambda x: -x[1]["wins"] / max(x[1]["games"], 1))
    for name, s in rows:
        g  = s["games"]
        wr = s["wins"] / g if g else 0.0
        print(f"  {name:<22}  {s['wins']:>2}/{g:<2}  ({wr*100:.0f}%)")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quick smoke test for Hnefatafl agents")
    parser.add_argument("--mode", choices=["coverage", "pairs"], default=DEFAULT_MODE,
                        help="coverage=one game per agent per role vs baseline; pairs=all pairs")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE,
                        help="Baseline opponent for coverage mode (default: random)")
    parser.add_argument("--games", type=int, default=SMOKE_GAMES,
                        help="Games per side per matchup (default: 1)")
    parser.add_argument("--time", type=float, default=SMOKE_TIME,
                        help="MCTS time budget per move in seconds (default: 0.20)")
    args = parser.parse_args()

    run_smoke_test(
        games_per_side=args.games,
        time_budget=args.time,
        mode=args.mode,
        baseline=args.baseline,
    )
