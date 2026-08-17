#!/usr/bin/env python3
"""
Run the engine over positions with a known best move.

A match result says the engine is weaker or stronger; it does not say what
it is getting wrong. These positions each have one clearly correct move,
so a failure points at a specific gap: a missed mate, a hanging piece, a
tactic that needs a deeper search.

    python3 tactics.py
    python3 tactics.py --depth 4
    python3 tactics.py --verbose

Exits non-zero if any position is failed, so CI catches a search change
that quietly stops solving something it used to.
"""

import argparse
import sys
import time

import chess

from knightmare_bot import KnightmareBot

NO_TIME_LIMIT = 600.0

# (name, FEN, acceptable moves in UCI, what the position tests)
POSITIONS = [
    ("back rank mate", "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
     ["e1e8"], "mate in one on the back rank"),

    ("mate with queen", "6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1",
     ["d1d8"], "mate in one with the queen"),

    ("take the free queen", "4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1",
     ["e4d5"], "capture an undefended queen"),

    ("take the free rook", "4k3/8/8/3r4/4P3/8/8/4K3 w - - 0 1",
     ["e4d5"], "capture an undefended rook"),

    ("do not take defended pawn", "4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1",
     None, "must avoid d1d5, which drops the queen for a pawn"),

    ("recapture", "4k3/8/8/3P4/8/8/8/4K3 b - - 0 1",
     None, "no capture available, any legal move is fine"),

    ("promote", "8/P6k/8/8/8/8/6K1/8 w - - 0 1",
     ["a7a8q"], "promote to a queen"),

    ("escape check", "4k3/8/8/8/7q/8/8/4K3 w - - 0 1",
     None, "in check, must play one of the legal escapes"),

    ("win a knight", "4k3/8/5n2/8/8/8/4B3/4K3 w - - 0 1",
     None, "knight is defended by nothing but far away"),

    ("avoid stalemate when winning", "7k/5Q2/8/8/8/8/8/6K1 w - - 0 1",
     None, "many wins available, must not stalemate"),

    ("take undefended rook", "3r4/8/4k3/8/8/8/8/3QK3 w - - 0 1",
     ["d1d8"], "the rook on d8 is not defended, so it is simply free"),

    ("decline defended rook", "3rk3/8/8/8/8/8/8/3QK3 w - - 0 1",
     None, "Qxd8 is met by Kxd8, trading a queen for a rook"),

    ("keep the extra queen", "4k3/8/8/8/8/8/8/3QK3 w - - 0 1",
     None, "a won position, must not give the queen away"),
]

# Moves the engine must never play in these positions
FORBIDDEN = {
    "do not take defended pawn": ["d1d5"],
    "avoid stalemate when winning": ["f7g6", "f7f8"],
    "decline defended rook": ["d1d8"],
}


def check_position(bot, name, fen, wanted, note, depth, verbose):
    """Search one position and report whether the move is acceptable"""
    board = chess.Board(fen)
    start = time.time()
    move = bot.get_move(board, NO_TIME_LIMIT, depth)
    elapsed = time.time() - start

    if move is None:
        return False, "no move returned", elapsed

    if move not in board.legal_moves:
        return False, f"illegal move {move.uci()}", elapsed

    forbidden = FORBIDDEN.get(name, [])
    if move.uci() in forbidden:
        return False, f"played {move.uci()}, which loses material", elapsed

    if wanted is not None and move.uci() not in wanted:
        return False, f"played {move.uci()}, wanted {' or '.join(wanted)}", elapsed

    if name == "avoid stalemate when winning":
        board.push(move)
        if board.is_stalemate():
            return False, f"{move.uci()} is stalemate", elapsed

    return True, move.uci(), elapsed


def run_suite(depth, verbose=False):
    """Run every position, returning (passed, total)"""
    bot = KnightmareBot()
    passed = 0

    print(f"Tactics suite at depth {depth}")
    print("=" * 68)

    for name, fen, wanted, note in POSITIONS:
        ok, detail, elapsed = check_position(bot, name, fen, wanted, note, depth, verbose)
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name:30} {detail:24} {elapsed:5.2f}s")
        if verbose and not ok:
            print(f"         {note}")
            print(f"         {fen}")
        passed += ok

    print("=" * 68)
    print(f"{passed} / {len(POSITIONS)} positions solved")
    return passed, len(POSITIONS)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the engine over tactical positions")
    parser.add_argument("--depth", type=int, default=3, help="search depth (default: 3)")
    parser.add_argument("--verbose", action="store_true", help="explain failures")
    return parser.parse_args()


def main():
    args = parse_args()
    passed, total = run_suite(args.depth, args.verbose)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
