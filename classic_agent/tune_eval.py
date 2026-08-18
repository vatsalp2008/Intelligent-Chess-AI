#!/usr/bin/env python3
"""
Search for better evaluation weights instead of guessing at them.

Hand tuning a weight and then playing a self-play match costs several
minutes per value, which is too slow to explore more than a couple of
settings. This scores a candidate far more cheaply: for a fixed set of
positions, count how often the engine picks the move Stockfish prefers.

Candidates are scored by how much Stockfish thinks our chosen move gives
away, summed over the positions. Counting exact move matches was tried
first and turned out to have too little resolution: every weight in a
plausible range scored identically, because a change of 10 or 20
centipawns rarely flips which move a depth-3 search prefers. Centipawn
loss still moves when the choice does not.

That is a proxy, not the real objective, so treat a win here as a
candidate worth confirming with selfplay.py rather than as proof. It is
useful precisely because it is fast enough to sweep a range of values.

    python3 tune_eval.py --list
    python3 tune_eval.py --weight ROOK_OPEN_FILE_BONUS --values 0 10 20 30 40
    python3 tune_eval.py --all --quick

Needs a Stockfish binary; see requirements-dev.txt.
"""

import argparse
import os
import shutil
import sys

import chess
import chess.engine

import knightmare_bot

# Weights worth sweeping, with a plausible range for each
TUNABLE = {
    "BISHOP_PAIR_BONUS": [0, 15, 30, 50],
    "DOUBLED_PAWN_PENALTY": [0, 8, 15, 25],
    "ISOLATED_PAWN_PENALTY": [0, 6, 12, 20],
    "ROOK_OPEN_FILE_BONUS": [0, 10, 20, 35],
    "ROOK_HALF_OPEN_FILE_BONUS": [0, 5, 10, 20],
    "KING_SHIELD_PENALTY": [0, 6, 12, 25],
}

# Positions to judge on: middlegames where evaluation actually decides.
# Sampled from real played games rather than written by hand, so every FEN
# is legal by construction. Hand written ones were repeatedly malformed.
POSITIONS = [
    "r2qkb1r/ppp1nppp/2npb3/1B2p3/4P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 1 6",
    "r2qkb1r/ppp1nppp/2n1b3/1B2N3/4p3/2NPB3/PPP2PPP/R2QK2R w KQkq - 0 8",
    "r3kb1r/p1p1nppp/2p1b3/1B1q4/4N3/3PB3/PPP2PPP/R2QK2R w KQkq - 0 10",
    "r1bqkb1r/ppp2ppp/2n2n2/3p4/3P4/2N2N2/PP2PPPP/R1BQKB1R w KQkq - 2 6",
    "r2qk2r/ppp2ppp/2n2n2/3p1b2/1b1P1B2/2N1PN2/PP3PPP/R2QKB1R w KQkq - 1 8",
    "r2q1rk1/ppp2ppp/2n5/3p1b2/1b1PnB2/1QN2N2/PP3PPP/R3KB1R w KQ - 0 10",
    "r1bqkbnr/pp2pppp/3p4/8/3nP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
    "r2qkbnr/pp1b1ppp/3p4/4p3/3QPB2/2N5/PPP2PPP/R3KB1R w KQkq - 0 8",
    "r2qkb1r/pp1bnppp/8/4Q3/4P3/2N5/PPP2PPP/R3KB1R w KQkq - 1 10",
    "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2P1P3/2NP1N2/PP3PPP/R1BQKB1R w KQkq - 0 6",
    "r1bq1rk1/ppp2ppp/2np1n2/3Np1B1/1bP1P3/3P1N2/PP3PPP/R2QKB1R w KQ - 4 8",
    "r1bq1rk1/ppp2ppp/2np1n2/4p1B1/Q1P1P3/3P1N2/PP3PPP/R3KB1R w KQ - 2 10",
]

OUR_DEPTH = 3
NO_TIME_LIMIT = 600.0

# Depth Stockfish is asked for its opinion at
REFERENCE_DEPTH = 12


def find_stockfish():
    """Locate the Stockfish binary, or return None"""
    configured = os.environ.get("STOCKFISH_PATH")
    if configured and os.path.isfile(configured):
        return configured

    found = shutil.which("stockfish")
    if found:
        return found

    for path in ("/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish",
                 "/usr/bin/stockfish", "/usr/games/stockfish"):
        if os.path.isfile(path):
            return path
    return None


def score_for(engine, board, move, cache):
    """Stockfish's score for a position after move, from the mover's view

    Cached, because the same move gets proposed by many weight settings and
    each analysis is the expensive part.
    """
    key = (board.board_fen(), board.turn, move.uci())
    if key in cache:
        return cache[key]

    mover = board.turn
    board.push(move)
    try:
        info = engine.analyse(board, chess.engine.Limit(depth=REFERENCE_DEPTH))
        score = info["score"].pov(mover).score(mate_score=100000)
    finally:
        board.pop()

    cache[key] = score
    return score


def reference_scores(engine, positions, cache):
    """The best score available in each position, per Stockfish"""
    best = {}
    for fen in positions:
        board = chess.Board(fen)
        info = engine.analyse(board, chess.engine.Limit(depth=REFERENCE_DEPTH))
        pv = info.get("pv")
        if not pv:
            best[fen] = None
            continue
        best[fen] = score_for(engine, board, pv[0], cache)
    return best


def centipawn_loss(engine, positions, best, cache):
    """Total centipawns given away across the positions, lower is better"""
    loss = 0
    for fen in positions:
        if best[fen] is None:
            continue
        board = chess.Board(fen)
        # A fresh engine each time so no table carries over between settings
        bot = knightmare_bot.KnightmareBot()
        move = bot.get_move(board, NO_TIME_LIMIT, OUR_DEPTH)
        if move is None or move not in board.legal_moves:
            loss += 1000  # failing to move is worse than any bad move
            continue
        loss += max(0, best[fen] - score_for(engine, board, move, cache))
    return loss


def sweep_weight(engine, name, values, positions, best, cache, verbose=True):
    """Try each value for one weight, returning {value: centipawn_loss}"""
    original = getattr(knightmare_bot, name)
    losses = {}

    try:
        for value in values:
            setattr(knightmare_bot, name, value)
            loss = centipawn_loss(engine, positions, best, cache)
            losses[value] = loss
            if verbose:
                marker = "  (current)" if value == original else ""
                print(f"    {name} = {value:4}  gives away {loss:5} cp{marker}",
                      flush=True)
    finally:
        # Always put the module back the way it was
        setattr(knightmare_bot, name, original)

    return losses


def report(name, losses, original):
    """Say whether any value beat the one in the source"""
    # Ties go to the value already in the source
    best_value = min(losses, key=lambda v: (losses[v], v != original))
    if losses[best_value] < losses[original]:
        print(f"  {name}: {best_value} gives away {losses[best_value]} cp vs "
              f"{losses[original]} for the current {original} - worth confirming")
        return True
    print(f"  {name}: current value {original} is as good as anything tried")
    return False


def parse_args():
    parser = argparse.ArgumentParser(description="Sweep evaluation weights")
    parser.add_argument("--weight", help="sweep a single named weight")
    parser.add_argument("--values", type=int, nargs="+", help="values to try")
    parser.add_argument("--all", action="store_true", help="sweep every tunable weight")
    parser.add_argument("--list", action="store_true", help="list tunable weights and exit")
    parser.add_argument("--quick", action="store_true",
                        help="use half the positions, for a faster rough pass")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list:
        print("Tunable weights and their current values:")
        for name, values in TUNABLE.items():
            print(f"  {name:28} = {getattr(knightmare_bot, name):4}   try {values}")
        return 0

    path = find_stockfish()
    if path is None:
        print("Stockfish not found. Install it or set STOCKFISH_PATH.")
        return 1

    positions = POSITIONS[::2] if args.quick else POSITIONS

    if args.weight:
        targets = {args.weight: args.values or TUNABLE.get(args.weight)}
        if targets[args.weight] is None:
            print(f"No default values for {args.weight}; pass --values")
            return 1
    elif args.all:
        targets = TUNABLE
    else:
        print("Pass --weight NAME, --all, or --list")
        return 1

    cache = {}
    engine = chess.engine.SimpleEngine.popen_uci(path)
    try:
        print(f"Reference: Stockfish depth {REFERENCE_DEPTH} over "
              f"{len(positions)} positions")
        best = reference_scores(engine, positions, cache)

        print("=" * 64)
        improved = []
        for name, values in targets.items():
            original = getattr(knightmare_bot, name)
            if original not in values:
                values = sorted(set(values) | {original})
            print(f"  sweeping {name} (current {original})")
            losses = sweep_weight(engine, name, values, positions, best, cache)
            if report(name, losses, original):
                improved.append(name)
            print("-" * 64)
    finally:
        engine.quit()

    print("=" * 64)
    if improved:
        print("Candidates to confirm with selfplay.py:", ", ".join(improved))
    else:
        print("No weight beat its current value on this measure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
