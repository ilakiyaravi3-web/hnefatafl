"""
plot_results.py
===============
Reads results/tournament_results.json and produces a full analysis figure set.

Charts produced
---------------
  1. Overall leaderboard — horizontal bar chart of win rates
  2. Head-to-head heatmap — win rate of row agent vs col agent
  3. Ablation impact — how much each removed component hurts vs mcts_full
  4. Role breakdown — attacker vs defender win rate per agent (grouped bars)
  5. Game length distribution — violin/box by winner type
  6. MCTS ablation radar — spider chart across 5 heuristic components

All saved to  results/plots/  as high-res PNGs and one combined PDF.

Usage
-----
    python plot_results.py                          # reads default results file
    python plot_results.py --file results/smoke_test_results.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch

# ── Style ─────────────────────────────────────────────────────────────────────

PALETTE = {
    "mcts_full":      "#2E86AB",   # steel blue
    "mcts_no_escape": "#A23B72",   # dark rose
    "mcts_no_corner": "#F18F01",   # amber
    "mcts_no_prox":   "#C73E1D",   # red
    "mcts_no_piece":  "#8EA604",   # olive
    "mcts_no_mob":    "#6B4226",   # brown
    "minimax":        "#3BB273",   # green
    "heuristic":      "#7B2D8B",   # purple
    "random":         "#9E9E9E",   # grey
}

DISPLAY_NAMES = {
    "mcts_full":      "MCTS (full)",
    "mcts_no_escape": "MCTS (no escape)",
    "mcts_no_corner": "MCTS (no corner dist)",
    "mcts_no_prox":   "MCTS (no proximity)",
    "mcts_no_piece":  "MCTS (no piece count)",
    "mcts_no_mob":    "MCTS (no mobility)",
    "minimax":        "Minimax α-β (d=3)",
    "heuristic":      "Heuristic Greedy",
    "random":         "Random",
}

ABLATION_AGENTS = [
    "mcts_full", "mcts_no_escape", "mcts_no_corner",
    "mcts_no_prox", "mcts_no_piece", "mcts_no_mob",
]
COMPONENT_LABELS = {
    "mcts_no_escape": "Escape Lanes",
    "mcts_no_corner": "Corner Distance",
    "mcts_no_prox":   "Atk Proximity",
    "mcts_no_piece":  "Piece Count",
    "mcts_no_mob":    "King Mobility",
}

plt.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        11,
    "axes.titlesize":   13,
    "axes.labelsize":   11,
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "figure.dpi":       120,
    "savefig.dpi":      180,
    "savefig.bbox":     "tight",
})

PLOTS_DIR = os.path.join("results", "plots")


# ══════════════════════════════════════════════════════════════════════════════
# Data loading & aggregation
# ══════════════════════════════════════════════════════════════════════════════

def load_results(path: str) -> List[dict]:
    with open(path) as f:
        data = json.load(f)
    # smoke_test wraps in {"results": [...], "failures": [...]}
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data   # full tournament is a plain list


def agent_order(results: List[dict]) -> List[str]:
    """Return agents sorted by overall win rate (descending)."""
    names = sorted({r["attacker"] for r in results} | {r["defender"] for r in results})
    wr = overall_win_rates(results, names)
    return sorted(names, key=lambda n: -wr.get(n, 0))


def overall_win_rates(results: List[dict], agents: List[str]) -> Dict[str, float]:
    stats = {a: {"wins": 0, "games": 0} for a in agents}
    for r in results:
        atk, dfn, winner = r["attacker"], r["defender"], r["winner"]
        for name in [atk, dfn]:
            if name not in stats:
                continue
            stats[name]["games"] += 1
            if (winner == "attacker" and name == atk) or \
               (winner == "defender" and name == dfn):
                stats[name]["wins"] += 1
    return {
        a: s["wins"] / s["games"] if s["games"] else 0.0
        for a, s in stats.items()
    }


def head_to_head_matrix(results: List[dict], agents: List[str]) -> np.ndarray:
    """
    Returns NxN matrix where mat[i,j] = win rate of agents[i]
    when playing as attacker against agents[j] as defender.
    NaN where no games played.
    """
    n   = len(agents)
    idx = {a: i for i, a in enumerate(agents)}
    wins   = np.zeros((n, n))
    totals = np.zeros((n, n))

    for r in results:
        atk, dfn, winner = r["attacker"], r["defender"], r["winner"]
        if atk not in idx or dfn not in idx:
            continue
        i, j = idx[atk], idx[dfn]
        totals[i, j] += 1
        if winner == "attacker":
            wins[i, j] += 1

    with np.errstate(invalid="ignore"):
        mat = np.where(totals > 0, wins / totals, np.nan)
    return mat


def role_stats(results: List[dict], agents: List[str]) -> Dict[str, Dict]:
    """Win rate split by role (attacker / defender)."""
    stats = {a: {"atk_wins": 0, "atk_games": 0,
                 "def_wins": 0, "def_games": 0} for a in agents}
    for r in results:
        atk, dfn, winner = r["attacker"], r["defender"], r["winner"]
        if atk in stats:
            stats[atk]["atk_games"] += 1
            if winner == "attacker":
                stats[atk]["atk_wins"] += 1
        if dfn in stats:
            stats[dfn]["def_games"] += 1
            if winner == "defender":
                stats[dfn]["def_wins"] += 1
    return stats


def game_lengths_by_winner(results: List[dict]):
    lengths = {"attacker": [], "defender": [], "draw": []}
    for r in results:
        key = r["winner"] if r["winner"] else "draw"
        lengths[key].append(r["move_count"])
    return lengths


# ══════════════════════════════════════════════════════════════════════════════
# Individual plots
# ══════════════════════════════════════════════════════════════════════════════

def plot_leaderboard(results, agents, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(9, 5))

    wr   = overall_win_rates(results, agents)
    vals = [wr.get(a, 0) * 100 for a in agents]
    cols = [PALETTE.get(a, "#555") for a in agents]
    labs = [DISPLAY_NAMES.get(a, a) for a in agents]

    bars = ax.barh(labs, vals, color=cols, edgecolor="white", linewidth=0.8)
    ax.set_xlabel("Win Rate (%)")
    ax.set_title("Overall Leaderboard — Win Rate by Agent")
    ax.set_xlim(0, 100)
    ax.axvline(50, color="#aaa", lw=0.8, ls="--")

    for bar, v in zip(bars, vals):
        ax.text(bar.get_width() + 0.8, bar.get_y() + bar.get_height() / 2,
                f"{v:.1f}%", va="center", fontsize=10)

    if standalone:
        fig.tight_layout()
        return fig


def plot_heatmap(results, agents, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 8))

    mat  = head_to_head_matrix(results, agents)
    labs = [DISPLAY_NAMES.get(a, a) for a in agents]

    im = ax.imshow(mat, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(agents))); ax.set_xticklabels(labs, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(agents))); ax.set_yticklabels(labs, fontsize=9)
    ax.set_xlabel("Defender"); ax.set_ylabel("Attacker")
    ax.set_title("Head-to-Head Win Rate (row=Attacker, col=Defender)")

    for i in range(len(agents)):
        for j in range(len(agents)):
            v = mat[i, j]
            if not np.isnan(v):
                txt = f"{v:.2f}"
                col = "white" if v < 0.25 or v > 0.75 else "black"
                ax.text(j, i, txt, ha="center", va="center", fontsize=8, color=col)

    plt.colorbar(im, ax=ax, label="Attacker win rate")
    if standalone:
        fig.tight_layout()
        return fig


def plot_ablation_impact(results, agents, ax=None):
    """Bar chart: how much win rate drops when each component is removed."""
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(8, 4))

    wr       = overall_win_rates(results, agents)
    full_wr  = wr.get("mcts_full", 0.5)

    abl_names  = [a for a in ABLATION_AGENTS if a != "mcts_full" and a in wr]
    drops      = [(full_wr - wr[a]) * 100 for a in abl_names]
    comp_labs  = [COMPONENT_LABELS.get(a, a) for a in abl_names]
    cols       = [PALETTE.get(a, "#888") for a in abl_names]

    order = np.argsort(drops)[::-1]
    abl_names  = [abl_names[i]  for i in order]
    drops      = [drops[i]      for i in order]
    comp_labs  = [comp_labs[i]  for i in order]
    cols       = [cols[i]       for i in order]

    bars = ax.bar(comp_labs, drops, color=cols, edgecolor="white", linewidth=0.8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("Win-rate drop vs MCTS (full)  (pp)")
    ax.set_title("Ablation: Win-Rate Drop When Each Heuristic Component Is Removed")

    for bar, v in zip(bars, drops):
        y = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                y + 0.3 if y >= 0 else y - 1.5,
                f"{v:+.1f}pp", ha="center", fontsize=10,
                color="black")

    ax.set_xlabel("Removed Component")
    if standalone:
        fig.tight_layout()
        return fig


def plot_role_breakdown(results, agents, ax=None):
    """Grouped bars — attacker win rate vs defender win rate per agent."""
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(11, 5))

    rs   = role_stats(results, agents)
    labs = [DISPLAY_NAMES.get(a, a) for a in agents]

    atk_wr = [rs[a]["atk_wins"] / rs[a]["atk_games"] * 100
               if rs[a]["atk_games"] else 0 for a in agents]
    def_wr = [rs[a]["def_wins"] / rs[a]["def_games"] * 100
               if rs[a]["def_games"] else 0 for a in agents]

    x   = np.arange(len(agents))
    w   = 0.38
    ax.bar(x - w/2, atk_wr, w, label="As Attacker", color="#E07B54", edgecolor="white")
    ax.bar(x + w/2, def_wr, w, label="As Defender", color="#5B8DB8", edgecolor="white")

    ax.set_xticks(x); ax.set_xticklabels(labs, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate by Role — Attacker vs Defender")
    ax.set_ylim(0, 105)
    ax.axhline(50, color="#aaa", lw=0.8, ls="--")
    ax.legend(frameon=False)

    if standalone:
        fig.tight_layout()
        return fig


def plot_game_length(results, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(7, 4))

    lengths = game_lengths_by_winner(results)
    labels  = ["Attacker wins", "Defender wins", "Draw"]
    data    = [lengths["attacker"], lengths["defender"], lengths["draw"]]
    colors  = ["#E07B54", "#5B8DB8", "#9E9E9E"]

    parts = ax.violinplot(
        [d for d in data if d],
        positions=[i for i, d in enumerate(data) if d],
        showmedians=True, showextrema=True,
    )
    used_labels = [labels[i] for i, d in enumerate(data) if d]
    for i, (pc, col) in enumerate(zip(parts["bodies"], colors)):
        pc.set_facecolor(col); pc.set_alpha(0.7)
    parts["cmedians"].set_color("white"); parts["cmedians"].set_linewidth(2)

    ax.set_xticks(range(len(used_labels)))
    ax.set_xticklabels(used_labels)
    ax.set_ylabel("Game Length (moves)")
    ax.set_title("Game Length Distribution by Outcome")

    if standalone:
        fig.tight_layout()
        return fig


def plot_radar(results, agents, ax=None):
    """
    Spider chart: for each ablation agent, show how it performs
    against MCTS_full as a fraction of full-MCTS performance.
    One spoke per removed component (how much was lost).
    """
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

    wr      = overall_win_rates(results, agents)
    full_wr = wr.get("mcts_full", 0.5)

    abl = [a for a in ABLATION_AGENTS if a != "mcts_full" and a in wr]
    if not abl:
        if standalone:
            ax.set_title("Not enough ablation data")
            return fig
        return

    n      = len(abl)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    # Normalised win rate: 1.0 = same as full, 0.0 = no wins
    values = [wr[a] / full_wr if full_wr > 0 else 0 for a in abl]
    values += values[:1]

    labs = [COMPONENT_LABELS.get(a, a) for a in abl]

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labs, fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=8)

    ax.plot(angles, values, "o-", lw=2, color="#2E86AB")
    ax.fill(angles, values, alpha=0.25, color="#2E86AB")

    # Reference ring for full MCTS = 1.0
    ax.plot(angles, [1.0] * (n + 1), "--", lw=1, color="#aaa")

    ax.set_title("Ablation Radar\n(1.0 = matches MCTS full)", pad=15)

    if standalone:
        fig.tight_layout()
        return fig


# ══════════════════════════════════════════════════════════════════════════════
# Combined figure
# ══════════════════════════════════════════════════════════════════════════════

def plot_all(results_path: str):
    os.makedirs(PLOTS_DIR, exist_ok=True)

    results = load_results(results_path)
    if not results:
        print("No results found — run the tournament first.")
        return

    agents = agent_order(results)
    print(f"Loaded {len(results)} games, {len(agents)} agents: {agents}")

    # ── Individual plots ───────────────────────────────────────────────────────

    fig1 = plot_leaderboard(results, agents)
    p1   = os.path.join(PLOTS_DIR, "01_leaderboard.png")
    fig1.savefig(p1)
    print(f"  Saved: {p1}")
    plt.close(fig1)

    fig2 = plot_heatmap(results, agents)
    p2   = os.path.join(PLOTS_DIR, "02_heatmap.png")
    fig2.savefig(p2)
    print(f"  Saved: {p2}")
    plt.close(fig2)

    fig3 = plot_ablation_impact(results, agents)
    p3   = os.path.join(PLOTS_DIR, "03_ablation_impact.png")
    fig3.savefig(p3)
    print(f"  Saved: {p3}")
    plt.close(fig3)

    fig4 = plot_role_breakdown(results, agents)
    p4   = os.path.join(PLOTS_DIR, "04_role_breakdown.png")
    fig4.savefig(p4)
    print(f"  Saved: {p4}")
    plt.close(fig4)

    fig5 = plot_game_length(results)
    p5   = os.path.join(PLOTS_DIR, "05_game_length.png")
    fig5.savefig(p5)
    print(f"  Saved: {p5}")
    plt.close(fig5)

    fig6 = plot_radar(results, agents)
    p6   = os.path.join(PLOTS_DIR, "06_radar.png")
    fig6.savefig(p6)
    print(f"  Saved: {p6}")
    plt.close(fig6)

    # ── Combined 2×3 dashboard ────────────────────────────────────────────────

    fig = plt.figure(figsize=(22, 16))
    gs  = GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.38)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, 0:2])
    ax5 = fig.add_subplot(gs[1, 2])

    plot_leaderboard(results, agents, ax=ax1)
    plot_heatmap(results, agents, ax=ax2)
    plot_ablation_impact(results, agents, ax=ax3)
    plot_role_breakdown(results, agents, ax=ax4)
    plot_game_length(results, ax=ax5)

    fig.suptitle("Hnefatafl AI — Tournament Analysis Dashboard", fontsize=18, fontweight="bold", y=0.98)

    dashboard_path = os.path.join(PLOTS_DIR, "dashboard.png")
    fig.savefig(dashboard_path)
    print(f"  Saved: {dashboard_path}")
    plt.close(fig)

    # ── Radar as separate (polar axes don't embed well in GridSpec) ───────────
    fig_r = plot_radar(results, agents)
    fig_r.savefig(p6)
    print(f"  Saved: {p6}")
    plt.close(fig_r)

    print(f"\nAll plots saved to: {PLOTS_DIR}/")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot Hnefatafl tournament results")
    parser.add_argument(
        "--file", default=os.path.join("results", "tournament_results.json"),
        help="Path to results JSON (default: results/tournament_results.json)"
    )
    args = parser.parse_args()
    plot_all(args.file)